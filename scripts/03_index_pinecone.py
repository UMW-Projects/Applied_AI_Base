import json
import os
import time
from typing import Dict, Any, List

from dotenv import load_dotenv
from tqdm import tqdm

from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

from control_families import detect_controls

load_dotenv()

EMBED_MODEL_DEFAULT = "text-embedding-3-small"


# =========================================================
# IO
# =========================================================
def read_jsonl(path: str) -> List[Dict[str, Any]]:
    data = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))

    return data


# =========================================================
# PINECONE UTILITIES
# =========================================================
def list_index_names(pc: Pinecone) -> List[str]:
    li = pc.list_indexes()

    if hasattr(li, "names"):
        return list(li.names())

    if isinstance(li, dict) and "indexes" in li:
        return [x.get("name") for x in li["indexes"]]

    if isinstance(li, list):
        names = []
        for x in li:
            if isinstance(x, dict):
                names.append(x.get("name"))
            elif hasattr(x, "name"):
                names.append(x.name)
        return [n for n in names if n]

    return []


def ensure_index(pc, index_name, dimension, cloud, region):
    existing = [x["name"] if isinstance(x, dict) else x.name for x in pc.list_indexes()]

    if index_name not in existing:
        print(f"Creating index: {index_name}")

        pc.create_index(
            name=index_name,
            dimension=dimension,
            metric="cosine",
            spec=ServerlessSpec(
                cloud=cloud,
                region=region,
            ),
        )

        # 🔥 IMPORTANT: wait until index is ready
        while True:
            desc = pc.describe_index(index_name)
            status = desc.status if hasattr(desc, "status") else desc.get("status", {})

            if isinstance(status, dict):
                if status.get("ready"):
                    break
            else:
                # fallback for SDK differences
                break

            print("Waiting for index to be ready...")
            time.sleep(2)


def reset_index(index) -> None:
    index.delete(delete_all=True)


def batch(iterable, n: int):
    buf = []
    for x in iterable:
        buf.append(x)
        if len(buf) >= n:
            yield buf
            buf = []
    if buf:
        yield buf


# =========================================================
# METADATA SAFETY
# =========================================================
def clean_metadata(md: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pinecone supports only:
    str, int, float, bool, list[str]
    """

    cleaned = {}

    for k, v in md.items():

        if v is None:
            continue

        if isinstance(v, (str, int, float, bool)):
            cleaned[k] = v
            continue

        if isinstance(v, list) and all(isinstance(x, str) for x in v):
            cleaned[k] = v

    return cleaned


def validate_metadata(md: Dict[str, Any]) -> None:
    for k, v in md.items():
        valid = (
            isinstance(v, (str, int, float, bool))
            or (isinstance(v, list) and all(isinstance(x, str) for x in v))
        )

        if not valid:
            raise ValueError(f"Invalid metadata field '{k}': {type(v)}")


# =========================================================
# EMBEDDINGS
# =========================================================
def format_embedding_text(item: Dict[str, Any]) -> str:
    """
    Better structure = better retrieval in compliance corpora.
    """

    return f"""
[ORG] {item.get('organization')}
[DOC] {item.get('document_title')}
[TYPE] {item.get('document_type')}
[SECTOR] {item.get('sector')}

{item.get('text')}
""".strip()


# =========================================================
# MAIN INDEXING
# =========================================================
def main(chunks_path: str, reset: bool = False, namespace: str = ""):

    openai_key = os.getenv("OPENAI_API_KEY")
    pinecone_key = os.getenv("PINECONE_API_KEY")

    index_name = os.getenv("PINECONE_INDEX", "reviews-index")
    cloud = os.getenv("PINECONE_CLOUD", "aws")
    region = os.getenv("PINECONE_REGION", "us-east-1")

    embed_model = os.getenv("OPENAI_EMBED_MODEL", EMBED_MODEL_DEFAULT)

    if not openai_key or not pinecone_key:
        raise RuntimeError("Missing OPENAI_API_KEY or PINECONE_API_KEY")

    client = OpenAI(api_key=openai_key)
    pc = Pinecone(api_key=pinecone_key)

    chunks = read_jsonl(chunks_path)

    if not chunks:
        raise RuntimeError("No chunks found. Run preprocessing first.")

    print(f"Loaded chunks: {len(chunks)}")

    # =====================================================
    # Infer embedding dimension
    # =====================================================
    first_text = format_embedding_text(chunks[0])

    first_emb = client.embeddings.create(
        model=embed_model,
        input=[first_text],
    ).data[0].embedding

    dimension = len(first_emb)

    ensure_index(pc, index_name, dimension, cloud, region)

    index = pc.Index(index_name)
    pinecone_namespace = namespace


    if reset:
        print("⚠️ Resetting index...")
        reset_index(index)

    # =====================================================
    # Index stats
    # =====================================================
    owner_count = sum(1 for c in chunks if c.get("is_owner_response", False))

    print(f"Chunks: {len(chunks)} | Owner responses: {owner_count}")

    # =====================================================
    # Batching
    # =====================================================
    BATCH_SIZE = 100

    for batch_items in tqdm(list(batch(chunks, BATCH_SIZE)), desc="Indexing"):

        texts = [format_embedding_text(x) for x in batch_items]

        embeddings = client.embeddings.create(
            model=embed_model,
            input=texts,
        ).data

        vectors = []

        for item, emb in zip(batch_items, embeddings):

            controls, _ = detect_controls(item.get("text", ""))

            metadata = {
                "chunk_id": item["chunk_id"],
                "source_file": item["source_file"],
                "document_title": item["document_title"],
                "organization": item["organization"],
                "document_type": item["document_type"],
                "sector": item["sector"],
                "page_number": int(item.get("page_number", 0)),
                "chunk_index": int(item.get("chunk_index", 0)),
                "text": item.get("text", "")[:4000],  # prevent oversized payloads
                "controls": controls,  # 🔥 NEW: control-aware retrieval
            }

            metadata = clean_metadata(metadata)
            validate_metadata(metadata)

            source = item.get("source_file", "unknown")
            chunk = item.get("chunk_id", "no_chunk")
            vector_id = item.get("id") or f"{item['source_file']}::{item['chunk_id']}"


            vectors.append({
                "id": vector_id,
                "values": emb.embedding,
                "metadata": metadata,
            })

        # Upsert
        index.upsert(
            vectors=vectors,
            namespace=pinecone_namespace
        )

    stats = index.describe_index_stats()

    print("\n✅ Indexing complete.")
    print(stats)


# =========================================================
# CLI
# =========================================================
if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--chunks", required=True)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--namespace", default="")

    args = parser.parse_args()

    main(
        chunks_path=args.chunks,
        reset=args.reset,
        namespace=args.namespace,
    )
