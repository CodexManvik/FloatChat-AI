from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain.prompts import ChatPromptTemplate
from langchain_chroma import Chroma
from app.core import settings
from app.core.prompts import SYSTEM, render_user

PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM),
    ("human", "{user_msg}")
])

def build_chain():
    """
    Builds a RAG chain using Chroma as vectorstore and Ollama as LLM.
    Returns a callable that takes a question (str) and optional top_k.
    """
    embeddings = OllamaEmbeddings(model=settings.EMB_MODEL, base_url=settings.OLLAMA_URL)
    vs = Chroma(
        collection_name=settings.COLLECTION,
        persist_directory=settings.CHROMA_DIR,
        embedding_function=embeddings,
    )
    llm = ChatOllama(model=settings.GEN_MODEL, base_url=settings.OLLAMA_URL, temperature=0.2)

    def invoke(question: str, top_k: int = None) -> dict:
        retriever = vs.as_retriever(search_kwargs={"k": top_k or settings.TOP_K})
        docs = retriever.get_relevant_documents(question)

        context = "\n\n".join(d.page_content for d in docs)
        user_msg = render_user(question, context)
        resp = llm.invoke(PROMPT.format(user_msg=user_msg))

        return {
            "answer": resp.content,
            "contexts": [
                {
                    "source": d.metadata.get("path", "unknown"),
                    "text": d.page_content
                }
                for d in docs
            ],
        }

    return invoke
