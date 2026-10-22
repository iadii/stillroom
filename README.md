# Stillroom

**A calm, reviewable document inbox.** Drop in the paperwork you keep postponing. Stillroom extracts text, asks an open-weight model to propose a title, category, date, and tags, then waits for your approval before moving anything. Every move can be undone.

Built during the Hacktoberfest 2026 Week 3 **Slow and Steady** challenge (October 19–25, 2026). The [challenge prompt](https://dev.to/challenges/hacktoberfest-week3-2026-10-19) specifically suggests a file and inbox tidier. Stillroom adds evidence-based suggestions and a human-controlled archive workflow.

[Read the Week 3 submission on DEV](https://dev.to/iadii/stillroom-a-document-inbox-that-does-the-sorting-and-waits-for-you-128k).

**[Watch the real 25-second walkthrough](docs/demo/stillroom-demo.webm)** · [See the source-backed proposal](docs/demo/proposal.png) · [See the activity trail](docs/demo/activity.png). The recording uses only a fictional sample document and a live Groq model response.

## What it does

- Import PDF, TXT, Markdown, and CSV files (up to 5 MB each); extract text locally and reject unreadable files.
- Ask Groq-hosted, open-weight `openai/gpt-oss-120b` for a structured proposal. The model must quote the source; the backend checks that quote and validates any extracted date.
- Edit the proposal, review the source alongside it, and explicitly approve the move. Bulk analysis and bulk filing are available for larger piles.
- Store originals in a local inbox until approval, then file into `year/category/date-title.ext`. Filename collisions receive numbered suffixes; identical uploads are rejected by SHA-256.
- Search the inbox or archive, download originals, undo moves, inspect the activity trail, and export an archive manifest as CSV.

## Run locally

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 20+, npm, and a [Groq API key](https://console.groq.com/keys). The model is open-weight, but this configuration uses Groq's hosted API. **Document text is sent to Groq when you press Analyze.** Upload and review remain local. Do not use this setup for confidential documents unless that data flow is acceptable to you.

```bash
cd stillroom
cp .env.example .env
# Put your key in .env: GROQ_API_KEY=gsk_...
cd backend && uv sync && cd ..
cd frontend && npm ci && npm run build && cd ..
cd backend && uv run uvicorn stillroom.api:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. The Python server serves the built Vue app and API from one local origin. For frontend development, run `npm run dev` in `frontend/` to rebuild on changes, then refresh the browser.

If you omit `GROQ_API_KEY`, upload and browsing work, while Analyze stays disabled. The sample documents in `docs/samples/` are fictional and can be used for a demo.

## Architecture

```text
Vue 3 frontend ──same-origin HTTP──> FastAPI
                                  ├── local PDF/text extraction
                                  ├── Groq GPT-OSS structured output
                                  └── SQLite metadata + event log
                                      local inbox/ and archive/
```

`backend/stillroom/ai.py` contains the model contract and evidence checks. `store.py` owns the state transitions and file moves. `files.py` validates files and constructs safe archive paths. `api.py` exposes the workflow. `frontend/src/` holds the Vue interface. `data/` is local runtime storage and is ignored by Git.

The state flow is `inbox → ready → archived`. Analyze creates a proposal; edits clear approval; approval is required before archive; Undo moves the file back to `ready` and clears approval. The archive operation holds a SQLite write transaction while moving the file and rolls the move back if the database operation fails. A sudden power loss between the filesystem move and database commit still needs manual recovery from `data/`; this is not a distributed transaction.

## Safety and limits

- Originals are copied to local storage on upload. Stillroom never reorganizes the directory you uploaded from.
- Only PDF, TXT, MD, and CSV are accepted. PDFs are limited to 30 pages; scanned PDFs need OCR first. Text sent to the model is limited to the first 30,000 characters.
- Model output is a proposal, not a decision. The evidence quote must appear in extracted text; dates without an exact source quote are discarded.
- Paths are generated from a fixed category set and a sanitized title. Existing files are never overwritten; archives are reversible.
- The local server is intended for one user on `127.0.0.1`. It has no account system or multi-user authorization. Do not expose it directly to the public internet.
- Multipart uploads have a request-size cap, and writes with a foreign browser Origin are rejected. CSV exports neutralize spreadsheet formulas.

## Verify

```bash
cd backend && uv run pytest -q
cd ../frontend && npm run format:check && npm run build
```

The tests cover the review/approval/undo lifecycle, collision handling, duplicate uploads, source quote validation, invalid files, local write protection, and safe CSV export. A live Groq classification requires a real key and is not faked in the UI.

GitHub Actions also runs the locked backend tests and frontend format/build checks on pushes and pull requests.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). This project is MIT licensed.
