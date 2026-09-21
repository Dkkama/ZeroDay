# Architecture

ZeroDay is a clerk console: inbox → classify → SI vs draft BL compare → human review → audit.

```
Browser (Vite React)
    → Cloud Run FastAPI (same origin /api + SPA)
        → JSON workspace (emails, audit, jobs)
        → local / Cloud Storage attachment bytes
        → IMAP (optional fetch)
        → LLM adapter
            → Cursor Cloud Agents (test)
            → Vertex Gemini 3 Flash (production demo)
```

The 1.00 Flash run (`sdoc_eval/outputs/flash25_v2`) is loaded as the sample workspace so a judge can click through 520 emails without spending Vertex quota.

SI is always the source of truth. The seven compare fields are shipper, consignee, notify party, ports, container count, gross weight. Unreadable or wrong-type files escalate; they are not guessed as mismatches.
