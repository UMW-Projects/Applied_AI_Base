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

CHUNK_SIZE = 900  # characters per chunk
CHUNK_OVERLAP = 100
CHUNKING_VERSION = "sentence-overlap-v1"
# ------------------------


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip() 


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        # Handle an unusually long sentence.
        if len(sentence) > chunk_size:
            # Save anything already accumulated.
            if current:
                chunks.append(current.strip())
                current = ""

            # Split the long sentence into overlapping windows.
            start = 0

            while start < len(sentence):
                end = min(start + chunk_size, len(sentence))
                piece = sentence[start:end].strip()

                if piece:
                    chunks.append(piece)

                # If this is the final piece, we're done.
                if end == len(sentence):
                    break

                # Move backward by the overlap amount for the next window.
                start = end - overlap

            continue

        # If this is the first sentence in the current chunk.
        if not current:
            current = sentence

        # Otherwise, try adding the sentence to the current chunk.
        elif len(current) + 1 + len(sentence) <= chunk_size:
            current += " " + sentence

        else:
            # Save the current chunk.
            chunks.append(current.strip())

            # Carry approximately 100 characters into the next chunk.
            overlap_text = current[-overlap:]

            # Add the new sentence after the overlap.
            current = overlap_text + " " + sentence

            # Safety check in case the overlap + sentence is too large.
            if len(current) > chunk_size:
                current = sentence

    # Save the final chunk.
    if current.strip():
        chunks.append(current.strip())

    # If the final chunk contains less text than the desired overlap,
    # shift its starting point backward into the previous chunk.
    if len(chunks) >= 2 and len(chunks[-1]) < overlap:
        final_chunk = chunks[-1]
        previous_chunk = chunks[-2]

        # Keep the final ending exactly where it is and move
        # the beginning backward, up to the maximum chunk size.
        available = chunk_size - len(final_chunk) - 1

        if available > 0:
            prefix = previous_chunk[-available:]
            chunks[-1] = (prefix + " " + final_chunk).strip()

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

        chunks = chunk_text(cleaned)

        for idx, chunk in enumerate(chunks):
            entry = {
                "chunk_id": f"energy-{chunk_counter:06d}",
                "source_file": pdf_name,
                "document_title": title_guess,
                "organization": ORGANIZATION,
                "sector": SECTOR,
                "document_type": DOCUMENT_TYPE,
                "regulation_family": REGULATION_FAMILY,
                "section_title": title_guess,
                "page_number": page_num,
                "chunk_index": idx,
                "text": chunk,
                "chunking_version": CHUNKING_VERSION,
                "chunk_char_count": len(chunk),
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
