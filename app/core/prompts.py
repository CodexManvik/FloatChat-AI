SYSTEM = "You are FloatChat, an ocean data assistant. Answer using only the provided context."

def render_user(question: str, context: str) -> str:
    return f"Question:\n{question}\n\nContext:\n{context}\n\nAnswer using the Context only."
