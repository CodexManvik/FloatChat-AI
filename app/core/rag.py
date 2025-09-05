from typing import Optional, List, Dict
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain.prompts import ChatPromptTemplate
from langchain_chroma import Chroma
from app.core import settings
from app.core.prompts import SYSTEM, render_user


# Build a reusable system + human prompt template
PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM),
    ("human", "{user_msg}")
])


def build_chain():
    """
    Build a Retrieval-Augmented Generation (RAG) chain using:
      - Chroma as the vectorstore
      - Ollama for embeddings and chat generation

    Returns:
        Callable `invoke(question: str, top_k: Optional[int]) -> dict`
    """

    # Initialize embeddings
    embeddings = OllamaEmbeddings(
        model=settings.EMB_MODEL,
        base_url=settings.OLLAMA_URL,
    )

    # Initialize Chroma vectorstore
    vs = Chroma(
        collection_name=settings.COLLECTION,
        persist_directory=str(settings.CHROMA_DIR),
        embedding_function=embeddings,
    )

    # Initialize LLM
    llm = ChatOllama(
        model=settings.GEN_MODEL,
        base_url=settings.OLLAMA_URL,
        temperature=0.2,
    )

    def invoke(question: str, top_k: Optional[int] = None) -> Dict[str, object]:
        """
        Ask a question to the RAG chain.

        Args:
            question (str): User query
            top_k (Optional[int]): Number of top documents to retrieve (defaults to settings.TOP_K)

        Returns:
            dict: {
                "answer": str,
                "contexts": List[{"source": str, "text": str}]
            }
        """

        retriever = vs.as_retriever(search_kwargs={"k": top_k or settings.TOP_K})
        docs = retriever.get_relevant_documents(question)

        if not docs:
            return {
                "answer": "❌ Sorry, I couldn’t find anything relevant in the knowledge base.",
                "contexts": [],
            }

        # Combine all docs content into a single context string
        context = "\n\n".join(d.page_content for d in docs)
        user_msg = render_user(question, context)

        # Query the LLM
        resp = llm.invoke(PROMPT.format(user_msg=user_msg))

        # Format answer with metadata (source, table/file)
        contexts: List[Dict[str, str]] = [
            {
                "source": d.metadata.get("source", d.metadata.get("path", "unknown")),
                "table": d.metadata.get("table", "N/A"),
                "text": d.page_content,
            }
            for d in docs
        ]

        return {
            "answer": resp.content,
            "contexts": contexts,
        }

    return invoke
