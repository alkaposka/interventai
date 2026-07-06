# AGENTS.md
# InterventorAI - 5-Agent SDLC Pipeline
## Stack
- Backend: Python 3.11 + FastAPI
- Frontend: vanilla HTML/JS (no framework)
- Database: SQLite for demo (file: interventai.db)
- Deploy: Google Cloud Run (single container)
## Conventions
- Agents run sequentially: Analysis -> Design -> Dev -> QA -> Deploy
- Each agent output is markdown, saved to handoffs/.md
- Code files only from Agent 3: app.py, static/index.html, test_app.py
- All endpoints under /api, all pages under /
## Hard Rules
1. No external CSS framework - inline CSS only
2. No external JS framework - vanilla fetch() only
3. Total codebase under 1000 lines
4. App must run with: uvicorn app:app --reload
5. Tests must run with: pytest test_app.py