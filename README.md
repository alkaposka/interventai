# InterventorAI

A 5-agent SDLC pipeline that built a SENA interventoría management web app end-to-end. Built for the Kaggle AI Agents Capstone (Business Track).

## Live Demo
- URL: [PASTE YOUR CLOUD RUN URL HERE]
- Login: `admin` / `admin`

## Local Setup
```bash
pip install -r requirements.txt
uvicorn app:app --reload
# Open http://localhost:8000
```

## Run Tests
```bash
pytest test_app.py -v
```

## Architecture
5 agents ran sequentially in Antigravity:
1. **Analysis** - ERS, traceability matrix, user stories
2. **Design** - MVC + REST architecture, ER model, API spec
3. **Development** - app.py (FastAPI), static/index.html, test_app.py
4. **QA** - Test plan, defect report, quality certificate (PASS)
5. **Deployment** - Dockerfile, gcloud commands, user manual

## Stack
- Backend: Python 3.11 + FastAPI
- Frontend: Vanilla HTML/JS (no framework)
- DB: SQLite (interventai.db, auto-seeded on startup)
- Deploy: Google Cloud Run

## Concepts Demonstrated
- ADK multi-agent orchestration
- MCP-based spec handoff
- Agent skills with progressive disclosure
- Policy server and human-in-the-loop
- Spec-driven development
