import os
import json
import re
from pathlib import Path
from PyPDF2 import PdfReader


# -------- CONFIG --------
ROOT_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = ROOT_DIR / "data" / "pdf"
OUTPUT_FILE = ROOT_DIR / "data" / "critical_infra_corpus.jsonl"

SECTOR = "Energy"
ORGANIZATION = "NERC"
REGULATION_FAMILY = "NERC CIP"
DOCUMENT_TYPE = "Standard"

CHUNK_SIZE = 800  # characters per chunk
# ------------------------


def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def chunk_text(text, chunk_size=800):
    # naive sentence split on period, question mark, exclamation
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""

    for sent in sentences:
        if len(current) + len(sent) <= chunk_size:
            current += " " + sent
        else:
            if current.strip():
                chunks.append(current.strip())
            current = sent

    if current.strip():
        chunks.append(current.strip())

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

    for page_num, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        cleaned = clean_text(raw_text)

        if not cleaned:
            continue

        chunks = chunk_text(cleaned, CHUNK_SIZE)

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

