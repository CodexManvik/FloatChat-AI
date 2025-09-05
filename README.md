# Project Setup & Task Instructions

## 1️⃣ Python Environment
- Create a Python environment. I used **Python 3.13.5**.
- Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

---

## 2️⃣ Tasks & Assignments

### Nitu & Shashwat

- Work on **Chroma** or any other database integration.
- Keep track of **all changes** and push them to the **`updates`** branch.

---

### Archit & Nemat

- Store all `.csv` files in:

```
app/core/data/raw
```

- Verify the directory structure.
- Run the ingestion + app in PowerShell:

```powershell
python -m app.ingest.ingest && uvicorn app.core.main:app --reload
```

- After starting the app, open the browser at:

```
http://127.0.0.1:8000/docs
```

- Focus on **/api/ask** implementation.
- ⚠ **Do NOT start ingestion accidentally**, your PC cannot handle the full load in time.
- Push **all changes** to the **`updates`** branch.

---

### Khushi

- Work on the **frontend**.
- Push your initial changes directly to the **`main`** branch.
- After the initial change, push to updates
---

## 3️⃣ General Notes

- Ask me if you get stuck or face issues.

---

