# ZeroDay — shipping document desk

ZeroDay is a clerk console for the Averis × Monash 2026 use case. It classifies a shipping mailbox, compares a Shipping Instruction (the source of truth) to a draft Bill of Lading, escalates when it cannot decide, and keeps an audit trail.

The user is a documentation clerk. Finding the right email takes a full read of every message, and a document request that is never opened never reaches the check. Comparing the two documents by hand is repetitive: names, ports, quantities, and weight must match, and the same fact is often written under a different label (“Port of Loading” and “Load Port”). A missed discrepancy becomes a correction, a delay, and another round of email.

Product description: [`docs/ZeroDay_Product_Description.pdf`](docs/ZeroDay_Product_Description.pdf).  
Architecture, implementation, challenges, and roadmap: [`docs/ZeroDay_Documentation.pdf`](docs/ZeroDay_Documentation.pdf).

## Live desk

https://zeroday-316196081380.asia-southeast1.run.app

- Email: `clerk@zeroday.local`
- Password: `clerk123`

The inbox already loaded there is the Vertex classification of all 520 emails.

## Scores

Both runs use `sdoc_eval/prompts/v1.md` and the 520-email set. Category is weighted 30%, defect detection 20%, and exact planted-defect detection 50%.

| Run | Model | Final | Category | Planted defects |
|---|---|---|---|---|
| Model selection | `gemini-3-flash` via Cursor | 1.0000 | 1.0000 | 46 / 46 |
| Live desk | `gemini-3-flash-preview` on Vertex | 1.0000 | 1.0000 | 46 / 46 |

Selection evidence: `sdoc_eval/outputs/flash25_v2/score.json`. The live desk scored the same 520 emails on production.

## Local run

Requires Python 3.11+, Node, and `gcloud` application-default credentials if you classify with Vertex. Copy `.env.example` to `.env`. Do not commit `.env`.

```bash
python3 -m pip install -r app/backend/requirements.txt -r sdoc_eval/requirements.txt
cd app/frontend && npm install && npm run dev
```

In another terminal, from `app/backend`:

```bash
PYTHONPATH=. uvicorn main:app --host 127.0.0.1 --port 8080
```

Open http://127.0.0.1:5173. Vite proxies `/api` to port 8080.

`STORE_BACKEND=firestore` in `.env` uses the same Firestore database as production (`hackathon-2026-509207`, asia-southeast1). Leave it unset to keep a local JSON file at `app/backend/data/state.json`. The dashboard does not auto-load the sample. Settings → Load sample replaces the inbox with the 520-email set and the selection labels.

## Cloud Run

From the repo root:

```bash
gcloud run deploy zeroday --source . \
  --project hackathon-2026-509207 --region asia-southeast1 \
  --allow-unauthenticated --memory 2Gi --cpu 2 --timeout 300 \
  --update-env-vars GCP_PROJECT=hackathon-2026-509207,VERTEX_LOCATION=global,STORE_BACKEND=firestore,VERTEX_MAX_BATCH=2048
```

Cloud Run scales to zero when nobody is on the site. A long classification should not depend on a background thread inside one web request. IMAP polling only runs while an instance is awake. To fetch with nobody on the site, set `CRON_SECRET` and point Cloud Scheduler at `POST /api/cron/imap` with header `X-Cron-Secret`.

## Models

| Setting | Provider | How it runs |
|---|---|---|
| Test | Cursor Cloud Agents (`CURSOR_API_KEY`) | Three warm machines, eight emails per follow-up. Used to choose the model. |
| Production | Vertex `gemini-3-flash-preview` | Three prompts at once, eight emails in each prompt. One email is its own prompt. Nine is eight plus the leftover one. |

Drop a zip on the Dashboard or the Inbox. The file has to contain `inbox/*.json` and `attachments/`. Classification starts with whichever provider is selected in Settings.

## Pages

- **Dashboard** — volume, and how many document checks need a person. A dropped zip opens Settings and starts classification.
- **Inbox** — every email. The preview opens under the row. Export the current filter.
- **Review** — mismatches and escalations. One click opens the case. Pick the SI value, the BL value, or type one; Validate moves to the next case.
- **Audit** — program and human changes, with export.
- **Settings** — model, sample load, zip drop, IMAP, jobs, and the `submission.json` export.

## Repo notes

Do not commit `.env` or service-account keys. The comparison rules are `sdoc_eval/prompts/v1.md`.
