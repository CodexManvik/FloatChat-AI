# Retired Streamlit apps

FloatChat's frontend is now the Next.js app in [`web/`](../../web). These are kept for reference:

- `app.py`: the interim Streamlit app that served as the showcase before the web app (Phases 1 and 2). It still works
  against the API:

  ```bash
  pip install -r legacy/streamlit/requirements.txt
  BACKEND_URL=http://localhost:8000 streamlit run legacy/streamlit/app.py
  ```

  On a hosted deployment it passes each visitor's IP with a shared `FRONTEND_TOKEN`, which the API still accepts.
- `streamlit_app.py`, `components/`, `styles/`, `utils/`: an earlier experimental dashboard
  (see `README_DASHBOARD.md`), with its tests in `tests/dashboard/`.
