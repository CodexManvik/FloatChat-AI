# Deploying FloatChat

FloatChat's live demo runs entirely on free tiers:

| Piece | Service | Why |
|---|---|---|
| Database (Postgres + pgvector) | [Neon](https://neon.com) free plan | 1 GB storage; suspends when idle |
| API (FastAPI container) | [Koyeb](https://www.koyeb.com) free instance | 512 MB / 0.1 vCPU; sleeps after 1 h idle |
| Keep-awake ping | [cron-job.org](https://cron-job.org) | calls `/ping` every 30 min |
| Data loading | GitHub Actions | backfill once, refresh daily at 02:00 UTC |
| LLM | [Groq](https://console.groq.com) | free API key |

You create every account and paste every secret yourself. Nothing secret goes in the repo.

## 1. Neon: database and roles

1. Sign up at neon.com and create a project named `floatchat`, **Postgres 16**, in the region you will
   also use on Koyeb (**Frankfurt** or **Washington, D.C.**).
2. On the project dashboard, open **Connect**, choose the `neondb` database and the owner role, and copy the
   connection string. This is the **admin URL**. It looks like
   `postgresql://neondb_owner:...@ep-...-pooler.<region>.aws.neon.tech/neondb?sslmode=require`.
3. Pick a strong password for the read-only API role (e.g. 24+ random characters) and keep it handy.
4. On your machine, in the repo folder, create the schema and the reader role:

   ```bash
   ADMIN_DATABASE_URL='<admin URL>' READER_PASSWORD='<reader password>' python -m pipeline create-reader
   ```

   Expected: `Reader role ready.`
5. Build the **reader URL**: the admin URL with `neondb_owner:<owner password>` replaced by
   `floatchat_reader:<reader password>`.

## 2. GitHub: secret and first data load

1. In the GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**:
   name `NEON_ADMIN_URL`, value = the admin URL.
2. **Actions → Backfill data → Run workflow** (leave the inputs blank). It loads the last 365 days
   (about 30–60 minutes). Expected last log line: `backfill: <N> profiles added, 0 removed`.
3. **Actions → Daily data refresh** runs every day at 02:00 UTC. Run it once by hand to check it works.

## 3. Koyeb: the API

1. Sign up at koyeb.com and create a **Web Service** from **GitHub**, selecting this repository and the
   `main` branch.
2. Builder: **Dockerfile**, path `Dockerfile.api`. Instance: **Free**. Region: the same as Neon.
3. Port: `8000`, protocol HTTP, public route `/`. Health check: HTTP `GET /ping`.
4. Environment variables (mark the database URL and key as **Secret**):

   | Name | Value |
   |---|---|
   | `DATABASE_URL` | the **reader URL** |
   | `LLM_BASE_URL` | `https://api.groq.com/openai/v1` |
   | `LLM_MODEL` | `llama-3.3-70b-versatile` (or any current Groq chat model) |
   | `LLM_API_KEY` | your Groq key |
   | `LLM_DAILY_BUDGET` | `2000` |
   | `ALLOWED_ORIGINS` | `http://localhost:3000` for now; add the Vercel URL in Phase 3 |

5. Deploy. When it is healthy, note the public URL, e.g. `https://floatchat-api-<name>.koyeb.app`.
6. Check it:

   ```bash
   python scripts/smoke_test.py https://floatchat-api-<name>.koyeb.app
   ```

   Expected: `All checks passed.`

## 4. cron-job.org: keep the API awake

1. Sign up at cron-job.org and create a cron job:
   - URL: `https://floatchat-api-<name>.koyeb.app/ping`
   - Schedule: every 30 minutes
2. `/ping` never touches the database, so Neon still suspends between real visits.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Koyeb build runs out of memory | Builds run on Koyeb's builders, not the free instance; retry. If it repeats, check the build log for a failing `pip install` |
| `/health` says `"database": "disconnected"` | Check `DATABASE_URL` uses `floatchat_reader` and the right password, and keeps `?sslmode=require` |
| `/health` says `"vector_index": "empty"` | The backfill has not run yet or failed: check **Actions → Backfill data** |
| LLM shows *missing or invalid LLM_API_KEY* | Re-paste the Groq key in Koyeb and redeploy |
| Daily refresh failed | Usually ERDDAP being slow or down; the site keeps serving the previous data. Re-run the workflow later |
| Koyeb's free tier changes | The API is a plain Docker image: Render (free, sleeps after 15 min) or any Docker host works with the same environment variables |
