from pathlib import Path
from typing import List
from langchain_community.document_loaders import UnstructuredHTMLLoader
from langchain.docstore.document import Document
import pandas as pd

def load_local_tree(root: str) -> List[Document]:
    docs: List[Document] = []
    for p in Path(root).rglob("*"):
        if not p.is_file():
            continue

        suffix = p.suffix.lower()

        # Plain text / markdown
        if suffix in {".txt", ".md"}:
            text = p.read_text(encoding="utf-8", errors="ignore")
            docs.append(Document(page_content=text, metadata={"path": str(p)}))

        # CSV files → load via pandas for structured text
        elif suffix == ".csv":
            try:
                df = pd.read_csv(p)
                # Turn into a readable string (you could refine this)
                text = df.to_string(index=False)
                docs.append(Document(page_content=text, metadata={"path": str(p)}))
            except Exception as e:
                print(f"Skipping {p}, error: {e}")

        # HTML files
        elif suffix in {".html", ".htm"}:
            loader = UnstructuredHTMLLoader(str(p))
            docs.extend(loader.load())

    return docs
