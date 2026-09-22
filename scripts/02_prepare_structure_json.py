import os
import json
import re
from pathlib import Path
from PyPDF2 import PdfReader


# -------- CONFIG --------
ROOT_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = ROOT_DIR / "data" / "pdf"
OUTPUT_FILE = ROOT_DIR / "data" / "structure_corpus.jsonl"

SECTOR = "Energy"
ORGANIZATION = "NERC"
REGULATION_FAMILY = "NERC CIP"
DOCUMENT_TYPE = "Standard"

CHUNK_SIZE = 900
CHUNK_OVERLAP = 100
CHUNKING_VERSION = "sentence-overlap-v1"
# ------------------------


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    cleaned = clean_text(text)
    if not cleaned:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    chunks = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(sentence) > chunk_size:
            if current:
                chunks.append(current.strip())
                current = ""

            step = max(chunk_size - overlap, 1)
            start = 0
            while start < len(sentence):
                remaining = len(sentence) - start
                if remaining < overlap and chunks:
                    start = len(sentence) - chunk_size
                    remaining = chunk_size

                chunk = sentence[start:start + chunk_size].strip()
                if chunk:
                    chunks.append(chunk)

                if remaining <= chunk_size:
                    break
                start += step
            continue

        proposed = f"{current} {sentence}".strip()
        if current and len(proposed) > chunk_size:
            chunks.append(current.strip())
            overlap_text = current[-overlap:]
            combined = f"{overlap_text} {sentence}".strip()
            current = combined if len(combined) <= chunk_size else sentence
        else:
            current = proposed

    if current:
        chunks.append(current.strip())

    return [chunk.strip() for chunk in chunks if chunk.strip()]

def extract_keywords(text):
    words = re.findall(r'\b[a-zA-Z]{6,}\b', text.lower())
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1

    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [w for w, _ in sorted_words[:5]]


def process_pdf(pdf_path, chunk_id_start):
    reader = PdfReader(pdf_path)
    pdf_name = os.path.basename(pdf_path)
    title_guess = pdf_name.replace(".pdf", "").replace("_", " ")

    entries = []
    chunk_counter = chunk_id_start

    for page_num, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        cleaned = clean_text(raw_text)

        if not cleaned:
            continue

        chunks = chunk_text(cleaned)

        for idx, chunk in enumerate(chunks):
            entry = {
                "chunking_version": CHUNKING_VERSION,
                "chunk_char_count": len(chunk),
                "chunk_id": f"energy-{chunk_counter:06d}",
                "source_file": pdf_name,
                "document_title": title_guess,
                "organization": ORGANIZATION,
                "sector": SECTOR,
                "document_type": DOCUMENT_TYPE,
                "regulation_family": REGULATION_FAMILY,
                "page_number": page_num,
                "chunk_index": idx,
                "text": chunk,
                "keywords": extract_keywords(chunk)
            }
            entries.append(entry)
            chunk_counter += 1

    return entries, chunk_counter


def main():
    pdf_files = [f for f in BASE_DIR.glob("*.pdf")]
    all_entries = []
    chunk_id_counter = 1

    for pdf in pdf_files:
        print(f"Processing: {pdf.name}")
        entries, chunk_id_counter = process_pdf(pdf, chunk_id_counter)
        all_entries.extend(entries)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for entry in all_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"\nDone! JSONL corpus saved to:\n{OUTPUT_FILE}")


if __name__ == "__main__":
    main()
