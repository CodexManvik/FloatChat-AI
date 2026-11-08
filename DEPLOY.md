# Deploying FloatChat

FloatChat's live demo runs entirely on free tiers:

| Piece | Service | Why |
|---|---|---|
| Database (Postgres + pgvector) | [Neon](https://neon.com) free plan | 1 GB storage; suspends when idle |
| API (FastAPI container) | [Render](https://render.com) free web service | 512 MB / 0.1 CPU; sleeps after 15 min idle; 750 free hours a month |
| Keep-awake ping | [cron-job.org](https://cron-job.org) | calls `/ping` every 10 min so Render never sleeps |
| Data loading | GitHub Actions | backfill once, refresh daily at 02:00 UTC |
| LLM | [Groq](https://console.groq.com) | free API key |

You create every account and paste every secret yourself. Nothing secret goes in the repo.

## 1. Neon: database and roles

1. Sign up at neon.com and create a project named `floatchat` in **AWS Europe Central 1 (Frankfurt)**, the same
   region you will use on Render. Only the **Postgres database** service is needed.
2. On the project dashboard, open **Connect**, choose the `neondb` database and the owner role, **turn off
   connection pooling**, and copy the connection string. This is the **admin URL**. It looks like
   `postgresql://neondb_owner:...@ep-....eu-central-1.aws.neon.tech/neondb?sslmode=require`.
3. Generate a strong password for the read-only API role and keep it somewhere safe:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(24))"
   ```

4. In the repo folder, create the schema and the reader role (PowerShell shown; in bash use `export NAME=value`):

   ```powershell
   $env:ADMIN_DATABASE_URL = '<admin URL>'
   $env:READER_PASSWORD = '<reader password>'
   python -m pipeline create-reader
   ```

   Expected: `Reader role ready.`
5. Build the **reader URL**: the admin URL with `neondb_owner:<owner password>` replaced by
   `floatchat_reader:<reader password>`.

## 2. GitHub: secret and first data load

1. Add the admin URL as a repository secret named `NEON_ADMIN_URL`, either in **Settings → Secrets and variables →
   Actions**, or from the same terminal:

   ```powershell
   gh secret set NEON_ADMIN_URL --repo <owner>/<repo> --body $env:ADMIN_DATABASE_URL
   ```

2. **Actions → Backfill data → Run workflow** (leave the inputs blank). It loads the last 365 days
   (about 30–60 minutes). Expected last log line: `backfill: <N> profiles added, 0 removed`.
3. **Actions → Daily data refresh** runs every day at 02:00 UTC. Run it once by hand to check it works.

## 3. Render: the API

1. Sign up at dashboard.render.com and click **New → Web Service**, connecting this GitHub repository.
2. Settings:

   | Setting | Value |
   |---|---|
   | Language | **Docker** |
   | Branch | `main` |
   | Region | **Frankfurt (EU Central)** |
   | Instance type | **Free** |
   | Dockerfile Path (Advanced) | `Dockerfile.api` (the default `./Dockerfile` builds the Streamlit app instead) |
   | Docker Build Context | `.` |
   | Health Check Path (Advanced) | `/ping` |
   | Auto-Deploy | On Commit |

3. Environment variables:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the **reader URL** |
   | `LLM_BASE_URL` | `https://api.groq.com/openai/v1` |
   | `LLM_MODEL` | a current Groq chat model (see console.groq.com/docs/models), e.g. `openai/gpt-oss-120b` |
   | `LLM_API_KEY` | your Groq key |
   | `LLM_DAILY_BUDGET` | `2000` |
   | `ALLOWED_ORIGINS` | `http://localhost:3000` for now; add the Vercel URL in Phase 3 |

4. Click **Deploy web service**. Render passes the port in `$PORT`, which the image already uses. When the service
   is **Live**, check it:

   ```bash
   python scripts/smoke_test.py https://<your-service>.onrender.com
   ```

   Expected: `All checks passed.`

## 4. cron-job.org: keep the API awake

1. Sign up at cron-job.org and create a cron job:
   - URL: `https://<your-service>.onrender.com/ping`
   - Schedule: every 10 minutes
2. Render's free tier sleeps after 15 minutes without traffic and allows 750 instance hours a month, enough for one
   service running all month. `/ping` never touches the database, so Neon still suspends between real visits.

## 5. Streamlit Community Cloud: the web app (interim UI)

The Streamlit app (`app.py`) runs free on Streamlit Community Cloud and talks to the Render API. Streamlit's servers
call the API for every visitor, so the app passes each visitor's IP along with a shared secret (`FRONTEND_TOKEN`);
without it, all visitors would share one rate limit.

1. Generate the shared secret:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. In **Render → your service → Environment**, add `FRONTEND_TOKEN` with that value and save (Render redeploys).
3. Sign in at **https://share.streamlit.io** with GitHub, click **Create app → Deploy a public app from GitHub**:

   | Setting | Value |
   |---|---|
   | Repository | this repository |
   | Branch | `main` |
   | Main file path | `app.py` |
   | App URL | a short name, e.g. `floatchat` |

4. Open **Advanced settings**: choose Python **3.11** or newer, and paste into **Secrets**:

   ```toml
   BACKEND_URL = "https://<your-service>.onrender.com"
   FRONTEND_TOKEN = "<the same secret as on Render>"
   ```

5. Click **Deploy**. Streamlit installs `requirements.txt` (frontend packages only) and starts the app in a few
   minutes. The sidebar should show green dots for PostgreSQL, the vector index and the LLM.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Render builds the wrong app | Check **Settings → Dockerfile Path** is `Dockerfile.api` |
| `/health` says `"database": "disconnected"` | Check `DATABASE_URL` uses `floatchat_reader` and the right password, and keeps `?sslmode=require` |
| `/health` says `"vector_index": "empty"` | The backfill has not finished or failed: check **Actions → Backfill data** |
| LLM shows *missing or invalid LLM_API_KEY* | Re-paste the Groq key in Render's environment variables (it redeploys automatically) |
| The first request takes about a minute | The service went to sleep: check the cron-job.org job is enabled and succeeding |
| Daily refresh failed | Usually ERDDAP being slow or down; the site keeps serving the previous data. Re-run the workflow later |
| Streamlit app says it can't reach the API | Check `BACKEND_URL` in the app's **Settings → Secrets** (no trailing slash needed) and that the Render service is Live |
| Streamlit visitors hit "Too many questions" quickly | `FRONTEND_TOKEN` must be identical in Render and in the Streamlit secrets |
| Render's free tier changes | The API is a plain Docker image: any Docker host (Google Cloud Run, Hugging Face Spaces, Fly.io) works with the same environment variables |
