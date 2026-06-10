# Project FM

Project FM is a live tactical reconstruction system for football clubs. It ingests match video as a stream, reconstructs a full-pitch 2D tactical state, and serves manager and analyst web views.

## First Slice

The first product slice runs on a MacBook Air with full-match files. It treats files as live streams, stores tactical state output, and renders the state in browser clients.

## Local Development

Backend:

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
uvicorn project_fm.api:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Data

Do not commit match videos, model weights, local caches, credentials, or private club/contact data.
