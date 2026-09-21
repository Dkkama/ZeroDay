# ZeroDay — shipping document desk

Clerk console for the Averis × Monash 2026 use case: classify an inbox, compare a Shipping Instruction (source of truth) to a draft Bill of Lading, escalate when the system cannot decide, and keep an audit trail.

The checking model and prompt in `sdoc_eval/` scored **1.0000** on the 520-email v2 inbox (`gemini-3-flash`, `sdoc_eval/outputs/flash25_v2`). That run seeds this app so a demo does not burn Vertex quota.

## Demo login

- Email: `clerk@zeroday.local`
- Password: `clerk123`

## Local run

```bash
python3 -m pip install -r app/backend/requirements.txt -r sdoc_eval/requirements.txt
cd app/frontend && npm install && npm run dev
# other terminal
cd app/backend && PYTHONPATH=. uvicorn main:app --host 127.0.0.1 --port 8080
```

Open http://127.0.0.1:5173 (Vite proxies `/api` to port 8080).

First Dashboard load seeds the 520 sample emails from `sdoc-hackathon-docker/data_v2` plus the Flash labels. That can take about a minute.

## Cloud Run

From the repo root (do not commit `.env`). First request seeds the 520-email sample and can take about a minute.

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com --project hackathon-2026-509207

gcloud run deploy zeroday --source . --project hackathon-2026-509207 --region asia-southeast1 --allow-unauthenticated --memory 2Gi --cpu 2 --timeout 300 --set-env-vars GCP_PROJECT=hackathon-2026-509207,VERTEX_LOCATION=global
```

After it is up: Settings → **Load one email with attachments**, then **Process one email — Vertex**. Do not process the full 520 on Vertex.

Project used by the Vertex smoke test: `hackathon-2026-509207`.

## Models

| Setting | Provider | When to use |
|---|---|---|
| Test | Cursor Cloud Agents (`CURSOR_API_KEY`) | Volume processing. Large limit. |
| Production demo | Vertex `gemini-3-flash-preview` | A few live calls for judges. Refuses large batches. |

`hackathon/test_gemini.py` is the original Vertex health check.

## Pages

Left sidebar: Dashboard, Inbox, Comparison requests, Audit log. Footer: Settings.

- **Dashboard** — counts, warning for document-check volume, charts
- **Inbox** — every email; export results (choose succeeded / mismatched / review / categories)
- **Comparison requests** — human queue; double-click to Validate / Edit SI vs BL
- **Audit log** — program vs human, export N rows
- **Settings** — sample load, zip upload, IMAP, model toggle, jobs, scorer `submission.json`

## Decision log

- **FastAPI + Vite React** — one Cloud Run URL, Python reuse of `extract.py` and the Cursor runner.
- **Vertex now, not later** — teammate Docker already targeted `hackathon-2026-509207`.
- **Keep Cursor** — Vertex quota is demo-only; Cursor is the soak-test path.
- **Seed Flash 1.00** — judges can walk the product with zero live Gemini calls.
- **Escalate, do not OCR image-only gold files** — the contest key wants `unreadable`, not a guessed OK.
- **JSON workspace first** — Firestore is the production swap; prelim needs a working desk.
- **IMAP + zip** — mail ingest without pretending Gmail OAuth is finished.
- **Do not auto-run Vertex on 520** after deploy.

## Repo notes

Do not commit `.env` or service-account keys. Validation evidence: `sdoc_eval/prompts/v1.md` and `sdoc_eval/outputs/flash25_v2/`.
