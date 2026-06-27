import os
import PyPDF2
from dataclasses import dataclass

@dataclass
class ParsedDocument:
    filename: str
    witness_name: str
    statement_number: str
    date: str
    raw_text: str
    pages: int

def extract_text_from_pdf(filepath: str) -> str:
    """Extract all text from a PDF file."""
    with open(filepath, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text

def extract_metadata(text: str, filename: str) -> dict:
    """
    Pull witness name, statement number and date from the header.
    Falls back to filename if not found.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    witness_name = "Unknown"
    statement_number = filename.replace(".pdf", "")
    date = "Unknown"

    for line in lines[:20]:
        if "Witness Name:" in line:
            witness_name = line.replace("Witness Name:", "").strip()
        if "Statement No.:" in line:
            statement_number = line.replace("Statement No.:", "").strip()
        if "Dated:" in line:
            date = line.replace("Dated:", "").strip()

    return {
        "witness_name": witness_name,
        "statement_number": statement_number,
        "date": date
    }

def parse_document(filepath: str) -> ParsedDocument:
    """Parse a single PDF into a structured document object."""
    filename = os.path.basename(filepath)
    text = extract_text_from_pdf(filepath)
    metadata = extract_metadata(text, filename)

    with open(filepath, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        page_count = len(reader.pages)

    return ParsedDocument(
        filename=filename,
        witness_name=metadata["witness_name"],
        statement_number=metadata["statement_number"],
        date=metadata["date"],
        raw_text=text,
        pages=page_count
    )

def parse_all_documents(data_dir: str) -> list[ParsedDocument]:
    """Parse every PDF in the data/raw directory."""
    documents = []
    pdf_files = [f for f in os.listdir(data_dir) if f.lower().endswith(".pdf")]

    print(f"Found {len(pdf_files)} PDFs")

    for i, filename in enumerate(pdf_files):
        filepath = os.path.join(data_dir, filename)
        try:
            doc = parse_document(filepath)
            documents.append(doc)
            print(f"[{i+1}/{len(pdf_files)}] Parsed: {doc.witness_name} — {doc.pages} pages")
        except Exception as e:
            print(f"[{i+1}/{len(pdf_files)}] FAILED: {filename} — {e}")

    return documents
