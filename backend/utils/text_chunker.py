def chunk_text(text: str, chunk_size: int = 3000, overlap: int = 500) -> list[str]:
    """
    Split text into overlapping chunks so no content is missed.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def find_relevant_chunks(text: str, keywords: list[str], max_chunks: int = 4) -> str:
    """
    Split full document into chunks, score each by keyword hits,
    return the top chunks concatenated.
    """
    chunks = chunk_text(text)
    scored = []
    for chunk in chunks:
        chunk_lower = chunk.lower()
        score = sum(chunk_lower.count(kw.lower()) for kw in keywords)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(reverse=True)
    top = [chunk for _, chunk in scored[:max_chunks]]
    return "\n---\n".join(top) if top else text[:3000]
