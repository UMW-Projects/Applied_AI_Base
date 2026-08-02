"""
Discover and ingest energy-sector cybersecurity sources into Pinecone.

This script is for keeping the Critical Infrastructure Energy RAG corpus fresh.
It can discover URLs with SerpAPI, read URLs from a file, or ingest direct URLs.
Each scraped document is chunked, embedded, compared against existing Pinecone
vectors, and only novel chunks are upserted.

Examples:
  python -m scripts.06_ingest_web_sources
  python -m scripts.06_ingest_web_sources --query "CISA energy sector ICS advisory"
  python -m scripts.06_ingest_web_sources --urls-file urls.txt
  python -m scripts.06_ingest_web_sources --url https://www.cisa.gov/news-events/cybersecurity-advisories
  python -m scripts.06_ingest_web_sources --dry-run

Required environment:
  OPENAI_API_KEY
  PINECONE_API_KEY
  PINECONE_INDEX

Optional environment:
  SERPAPI_API_KEY or SERPAPI_KEY
  OPENAI_EMBED_MODEL
  PINECONE_NAMESPACE
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import io
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone
from PyPDF2 import PdfReader
from tqdm import tqdm

from control_families import detect_controls

try:
    from serpapi import GoogleSearch
except ImportError:
    try:
        from serpapi.google_search import GoogleSearch
    except ImportError:
        GoogleSearch = None


load_dotenv()

LOGGER = logging.getLogger("energy_web_ingest")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

EMBED_MODEL_DEFAULT = "text-embedding-3-small"
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 250
MIN_TEXT_LENGTH = 500
MAX_DOWNLOAD_BYTES = 35 * 1024 * 1024
REQUEST_TIMEOUT = 18
SIMILARITY_THRESHOLD = 0.88
SIMILARITY_TOP_K = 5
SEARCH_RESULTS_PER_QUERY = 10
UPSERT_BATCH_SIZE = 100
BACKOFF_MAX_SLEEP = 30

DEFAULT_SEARCH_QUERIES = [
    "CISA energy sector industrial control systems advisory",
    "CISA ICS advisory electric utility operational technology cybersecurity",
    "NIST SP 800-82 industrial control systems energy sector cybersecurity",
    "DOE C2M2 energy sector cybersecurity maturity model guidance",
    "DOE energy delivery systems cybersecurity roadmap OT ICS",
    "NERC CIP remote access supply chain cybersecurity guidance",
    "FERC NERC CIP cybersecurity reliability standard energy infrastructure",
    "INL PNNL energy sector OT cybersecurity threat mitigation",
    "electric sector cyber threat vulnerability analysis OT ICS",
    "critical infrastructure energy sector ransomware OT cybersecurity advisory",
]

PREFERRED_DOMAINS = (
    "cisa.gov",
    "energy.gov",
    "nist.gov",
    "ferc.gov",
    "nerc.com",
    "inl.gov",
    "pnnl.gov",
    "ornl.gov",
    "anl.gov",
    "epri.com",
    "regulations.gov",
    "congress.gov",
    "gao.gov",
)


def env_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def env_optional(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def backoff_sleep(attempt: int) -> None:
    time.sleep(min((2 ** attempt) + (0.2 * attempt), BACKOFF_MAX_SLEEP))


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def domain_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def is_allowed_url(url: str, allow_any_domain: bool = False) -> bool:
    if allow_any_domain:
        return True
    domain = domain_of(url)
    return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in PREFERRED_DOMAINS)


def infer_organization(url: str, title: str = "") -> str:
    haystack = f"{url} {title}".lower()
    mapping = {
        "cisa": "CISA",
        "nist": "NIST",
        "energy.gov": "DOE",
        "doe": "DOE",
        "ferc": "FERC",
        "nerc": "NERC",
        "inl": "INL",
        "pnnl": "PNNL",
        "ornl": "ORNL",
        "anl": "ANL",
        "epri": "EPRI",
    }
    for marker, org in mapping.items():
        if marker in haystack:
            return org
    return domain_of(url) or "External"


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    cleaned = normalize_space(text)
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks = []
    start = 0
    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start = max(end - overlap, start + 1)
    return chunks


def embedding_text(metadata: Dict[str, Any], text: str) -> str:
    return f"""
[ORG] {metadata.get("organization")}
[DOC] {metadata.get("document_title")}
[TYPE] {metadata.get("document_type")}
[SECTOR] {metadata.get("sector")}
[URL] {metadata.get("source_url")}

{text}
""".strip()


def embed_texts(client: OpenAI, texts: List[str], model: str, max_retries: int = 5) -> List[List[float]]:
    for attempt in range(max_retries):
        try:
            response = client.embeddings.create(model=model, input=texts)
            return [item.embedding for item in response.data]
        except Exception as exc:
            if attempt == max_retries - 1:
                raise
            LOGGER.warning("Embedding retry %s/%s after error: %s", attempt + 1, max_retries, exc)
            backoff_sleep(attempt)
    return []


def search_urls(query: str, limit: int) -> List[str]:
    api_key = env_optional("SERPAPI_API_KEY", "SERPAPI_KEY")
    if not api_key or GoogleSearch is None:
        return []

    try:
        result = GoogleSearch({
            "engine": "google",
            "q": query,
            "api_key": api_key,
            "num": limit,
            "hl": "en",
            "gl": "us",
        }).get_dict()
    except Exception as exc:
        LOGGER.warning("Search failed for %r: %s", query, exc)
        return []

    return [
        item.get("link")
        for item in result.get("organic_results", [])
        if item.get("link")
    ]


def content_type_for(url: str) -> str:
    try:
        response = requests.head(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        return response.headers.get("Content-Type", "").lower()
    except Exception:
        return ""


def download(url: str) -> Optional[requests.Response]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
    }
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, stream=True)
        response.raise_for_status()
        content = response.content
        if len(content) > MAX_DOWNLOAD_BYTES:
            LOGGER.warning("Skipping oversized response: %s", url)
            return None
        response._content = content
        return response
    except Exception as exc:
        LOGGER.warning("Download failed for %s: %s", url, exc)
        return None


def parse_pdf(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(pages)


def parse_html(content: bytes) -> Tuple[str, str]:
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    candidates = []
    for selector in ["article", "main", "div#content", "div.content", "div.article", "div.post"]:
        node = soup.select_one(selector)
        if not node:
            continue
        text = "\n".join(
            part.get_text(" ", strip=True)
            for part in node.find_all(["h1", "h2", "h3", "p", "li", "td"])
        )
        if len(text) >= MIN_TEXT_LENGTH:
            candidates.append(text)

    if candidates:
        return title, max(candidates, key=len)

    fallback = "\n".join(part.get_text(" ", strip=True) for part in soup.find_all(["p", "li"]))
    return title, fallback


def scrape_url(url: str) -> Optional[Dict[str, str]]:
    response = download(url)
    if response is None:
        return None

    content_type = response.headers.get("Content-Type", "").lower() or content_type_for(url)
    is_pdf = "application/pdf" in content_type or url.lower().split("?", 1)[0].endswith(".pdf")

    try:
        if is_pdf:
            text = parse_pdf(response.content)
            title = Path(urlparse(url).path).name or url
        else:
            title, text = parse_html(response.content)
            title = title or domain_of(url) or url
    except Exception as exc:
        LOGGER.warning("Parse failed for %s: %s", url, exc)
        return None

    text = normalize_space(text)
    if len(text) < MIN_TEXT_LENGTH:
        LOGGER.info("Skipping short/empty source: %s", url)
        return None

    return {"url": url, "title": title, "text": text}


def url_already_ingested(index: Any, url: str, dimension: int, namespace: str) -> bool:
    try:
        response = index.query(
            vector=[0.0] * dimension,
            top_k=1,
            include_metadata=True,
            filter={"source_url": {"$eq": url}},
            namespace=namespace,
        )
        return bool(getattr(response, "matches", []) or [])
    except Exception as exc:
        LOGGER.warning("URL lookup failed for %s: %s", url, exc)
        return False


def is_similar_to_existing(index: Any, embedding: List[float], threshold: float, top_k: int, namespace: str) -> bool:
    try:
        response = index.query(
            vector=embedding,
            top_k=top_k,
            include_values=False,
            include_metadata=True,
            namespace=namespace,
        )
        matches = getattr(response, "matches", []) or []
        if not matches:
            return False
        max_score = max(float(getattr(match, "score", 0.0)) for match in matches)
        return max_score >= threshold
    except Exception as exc:
        LOGGER.warning("Similarity check failed: %s", exc)
        return False


def stable_chunk_id(url: str, chunk_index: int, text: str) -> str:
    digest = hashlib.md5(f"{url}|{chunk_index}|{text[:500]}".encode("utf-8")).hexdigest()[:14]
    return f"web_{digest}_{chunk_index:03d}"


def build_vectors(
    scraped: Dict[str, str],
    chunks: List[str],
    embeddings: List[List[float]],
) -> List[Dict[str, Any]]:
    today = datetime.date.today().isoformat()
    organization = infer_organization(scraped["url"], scraped["title"])
    vectors = []

    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        controls, _ = detect_controls(chunk)
        chunk_id = stable_chunk_id(scraped["url"], idx, chunk)
        metadata = {
            "chunk_id": chunk_id,
            "source_file": scraped["url"],
            "document_title": scraped["title"][:250],
            "organization": organization,
            "document_type": "Web Source",
            "sector": "Energy",
            "page_number": 0,
            "chunk_index": idx,
            "text": chunk[:4000],
            "controls": controls,
            "source_url": scraped["url"],
            "retrieved_at": today,
            "is_external": True,
        }
        vectors.append({
            "id": chunk_id,
            "values": embedding,
            "metadata": metadata,
        })

    return vectors


def load_urls_from_file(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as handle:
        return [
            line.strip()
            for line in handle
            if line.strip() and not line.strip().startswith("#")
        ]


def unique_urls(urls: Iterable[str], allow_any_domain: bool) -> List[str]:
    seen = set()
    cleaned = []
    for url in urls:
        if not url or url in seen:
            continue
        seen.add(url)
        if not is_allowed_url(url, allow_any_domain=allow_any_domain):
            LOGGER.info("Skipping non-preferred domain: %s", url)
            continue
        cleaned.append(url)
    return cleaned


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest novel web sources into Pinecone for the Energy RAG bot.")
    parser.add_argument("--url", action="append", default=[], help="URL to ingest. Can be repeated.")
    parser.add_argument("--urls-file", help="File containing URLs, one per line.")
    parser.add_argument("--query", action="append", default=[], help="SerpAPI query. Can be repeated.")
    parser.add_argument("--no-default-search", action="store_true", help="Do not run default SerpAPI search queries.")
    parser.add_argument("--allow-any-domain", action="store_true", help="Allow ingestion from domains outside the preferred source list.")
    parser.add_argument("--threshold", type=float, default=SIMILARITY_THRESHOLD, help="Similarity threshold for duplicate skipping.")
    parser.add_argument("--top-k", type=int, default=SIMILARITY_TOP_K, help="Number of Pinecone neighbors for similarity checks.")
    parser.add_argument("--results-per-query", type=int, default=SEARCH_RESULTS_PER_QUERY, help="SerpAPI results per query.")
    parser.add_argument("--dry-run", action="store_true", help="Scrape and compare, but do not upsert.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    openai_key = env_required("OPENAI_API_KEY")
    pinecone_key = env_required("PINECONE_API_KEY")
    index_name = env_required("PINECONE_INDEX")
    namespace = os.getenv("PINECONE_NAMESPACE", "")
    embed_model = os.getenv("OPENAI_EMBED_MODEL", EMBED_MODEL_DEFAULT)

    client = OpenAI(api_key=openai_key)
    pc = Pinecone(api_key=pinecone_key)
    index = pc.Index(index_name)

    probe = client.embeddings.create(model=embed_model, input=["dimension probe"]).data[0].embedding
    dimension = len(probe)

    urls = list(args.url or [])
    if args.urls_file:
        urls.extend(load_urls_from_file(args.urls_file))

    queries = list(args.query or [])
    if not args.no_default_search and not urls:
        queries.extend(DEFAULT_SEARCH_QUERIES)

    if queries:
        if not env_optional("SERPAPI_API_KEY", "SERPAPI_KEY") or GoogleSearch is None:
            LOGGER.warning("SerpAPI unavailable; only explicit URLs will be ingested.")
        for query in queries:
            LOGGER.info("Searching: %s", query)
            urls.extend(search_urls(query, args.results_per_query))

    urls = unique_urls(urls, allow_any_domain=args.allow_any_domain)
    if not urls:
        LOGGER.info("No URLs to ingest.")
        return

    added_chunks = 0
    skipped_similar = 0
    skipped_existing_url = 0
    failed_urls = 0

    for url in tqdm(urls, desc="Sources"):
        if url_already_ingested(index, url, dimension, namespace):
            skipped_existing_url += 1
            continue

        scraped = scrape_url(url)
        if not scraped:
            failed_urls += 1
            continue

        chunks = chunk_text(scraped["text"])
        if not chunks:
            failed_urls += 1
            continue

        base_metadata = {
            "organization": infer_organization(scraped["url"], scraped["title"]),
            "document_title": scraped["title"],
            "document_type": "Web Source",
            "sector": "Energy",
            "source_url": scraped["url"],
        }
        embed_inputs = [embedding_text(base_metadata, chunk) for chunk in chunks]

        try:
            embeddings = embed_texts(client, embed_inputs, embed_model)
        except Exception as exc:
            LOGGER.warning("Embedding failed for %s: %s", url, exc)
            failed_urls += 1
            continue

        vectors = []
        all_vectors = build_vectors(scraped, chunks, embeddings)
        for vector in all_vectors:
            if is_similar_to_existing(index, vector["values"], args.threshold, args.top_k, namespace):
                skipped_similar += 1
                continue
            vectors.append(vector)

        if not vectors:
            LOGGER.info("No novel chunks for %s", url)
            continue

        if args.dry_run:
            added_chunks += len(vectors)
            LOGGER.info("Dry run: would add %s chunks from %s", len(vectors), url)
            continue

        for i in range(0, len(vectors), UPSERT_BATCH_SIZE):
            index.upsert(vectors=vectors[i:i + UPSERT_BATCH_SIZE], namespace=namespace)
        added_chunks += len(vectors)
        LOGGER.info("Added %s chunks from %s", len(vectors), url)

    print("\nIngestion summary")
    print(f"  URLs considered:       {len(urls)}")
    print(f"  Added chunks:          {added_chunks}")
    print(f"  Similar chunks skipped:{skipped_similar}")
    print(f"  Existing URLs skipped: {skipped_existing_url}")
    print(f"  Failed/short URLs:     {failed_urls}")
    print(f"  Similarity threshold:  {args.threshold}")
    print(f"  Pinecone index:        {index_name}")
    print(f"  Namespace:             {namespace or '(default)'}")
    if args.dry_run:
        print("  Mode:                  dry run")


if __name__ == "__main__":
    main()
