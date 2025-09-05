from typing import Optional, List, Dict

# ------------------------------
# System prompt for the LLM
# ------------------------------
SYSTEM = (
    "You are FloatChat, an intelligent ocean data assistant. "
    "Answer questions only using the provided context. "
    "Do not hallucinate or guess beyond the context."
)

# ------------------------------
# User prompt renderer
# ------------------------------
def render_user(
    question: str,
    context: str,
    instructions: Optional[str] = None,
    max_context_length: Optional[int] = None
) -> str:
    """
    Build a user prompt including question, context, and optional instructions.
    
    Args:
        question (str): User's query
        context (str): Retrieved documents or database context
        instructions (Optional[str]): Extra instructions to the LLM
        max_context_length (Optional[int]): Limit length of context if too long
    
    Returns:
        str: Formatted user prompt ready for the LLM
    """

    # Truncate context if requested
    if max_context_length and len(context) > max_context_length:
        context = context[:max_context_length] + "\n\n[Truncated...]"

    prompt = f"Question:\n{question}\n\nContext:\n{context}"

    if instructions:
        prompt += f"\n\nInstructions:\n{instructions}"

    prompt += "\n\nAnswer using the Context only."

    return prompt

# ------------------------------
# Optional helper to format multi-table context
# ------------------------------
def format_context_from_docs(docs: List[Dict]) -> str:
    """
    Format retrieved documents into a readable context string for LLM.

    Args:
        docs (List[Dict]): Each dict contains 'source', 'table', and 'text'

    Returns:
        str: Combined context string
    """
    lines = []
    for doc in docs:
        source = doc.get("source", "unknown")
        table = doc.get("table", "N/A")
        text = doc.get("text", "")
        lines.append(f"[Source: {source} | Table: {table}]\n{text}")
    return "\n\n".join(lines)
