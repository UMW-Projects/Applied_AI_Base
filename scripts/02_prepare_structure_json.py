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

# Phase 1 Chunking Configurations
MIN_CHUNK_SIZE = 600
MAX_CHUNK_SIZE = 900
OVERLAP_SIZE = 100
CHUNKING_VERSION = "retrieval-structure-v1"
# ------------------------


def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_section_title(text, current_title="General Context"):
    """
    Detects dynamic section headers in NERC CIP/Standard documents 
    (e.g., '1. Requirement', 'R1. Access Control', 'CIP-007-6 - Section A').
    """
    match = re.search(r'((?:R\d+|Requirement\s+\d+|Section\s+[A-Z\d]+|[0-9]+\.[0-9]*)\s*[-:]?\s*[^.\n]{3,60})', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return current_title


def chunk_text_structured(text, min_size=600, max_size=900, overlap=100):
    """
    Groups sentences into structure-aware chunks between 600 and 900 characters
    while maintaining a ~100 character overlap across neighboring chunks.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = ""

    for sent in sentences:
        if len(current_chunk) + len(sent) + 1 <= max_size:
            current_chunk = f"{current_chunk} {sent}".strip()
        else:
            if len(current_chunk) >= min_size:
                chunks.append(current_chunk)
                # Apply overlap by pulling the trailing characters of the previous chunk
                overlap_text = current_chunk[-overlap:] if len(current_chunk) >= overlap else current_chunk
                current_chunk = f"{overlap_text} {sent}".strip()
            else:
                # If current chunk is below min_size, append sentence to meet target size
                current_chunk = f"{current_chunk} {sent}".strip()

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


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
    active_section_title = "Document Header"

    for page_num, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        cleaned = clean_text(raw_text)

        if not cleaned:
            continue

        # Extract or update section heading context for this page
        active_section_title = extract_section_title(cleaned, active_section_title)

        chunks = chunk_text_structured(cleaned, MIN_CHUNK_SIZE, MAX_CHUNK_SIZE, OVERLAP_SIZE)

        for idx, chunk in enumerate(chunks):
            entry = {
                "chunk_id": f"energy-{chunk_counter:06d}",
                "source_file": pdf_name,
                "document_title": title_guess,
                "organization": ORGANIZATION,
                "sector": SECTOR,
                "document_type": DOCUMENT_TYPE,
                "regulation_family": REGULATION_FAMILY,
                "topic": title_guess,
                "section_title": active_section_title,
                "chunking_version": CHUNKING_VERSION,
                "chunk_char_count": len(chunk),
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

    print(f"\nDone! Structure-aware JSONL corpus saved to:\n{OUTPUT_FILE}")


if __name__ == "__main__":
    main()