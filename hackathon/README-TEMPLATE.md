# <Project name>

One line: for **[user]** who **[pain]**, this does **[action]** so they get **[outcome]**.

<!-- Sprint 0 deliverable: this README is the roadmap the team executes and the documentation judges read. Fill every section before D-5:00; refine at D-0:50. -->

## Problem

Two or three sentences. Name the user, the cost of the problem, and why the obvious existing solution fails.

## What it does

- The one flow, in numbered steps a judge can follow.
- The AI step: what the model receives, what it returns, and what happens when it fails.
- What is **real** today versus **mocked / hardcoded**. Be honest — judges notice, and honesty reads as competence.

## Live demo

- URL:
- Demo credentials, if any:
- Known limitations on the live instance:

## Architecture

```
React (Vite)  →  API (framework)  →  DB (engine)
                        ↓
                   LLM / model API
```

Three boxes maximum. One short paragraph on why this shape was chosen, and what it would take to scale.

## API contract

<!-- Agreed in Sprint 0 so frontend and backend build in parallel. Do not change after D-5:00 without updating this table. -->

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| GET | /api/health | — | `{"status":"ok"}` |
| POST | /api/<resource> | `{"field":"value"}` | `{"id":1,"result":"..."}` |
| GET | /api/<resource> | — | `[{"id":1,...}]` |

## How to run locally

```bash
git clone <url> && cd <repo>

# backend
cd backend && cp .env.example .env   # add your keys
pip install -r requirements.txt
python seed.py && uvicorn main:app --reload

# frontend
cd frontend && npm install && npm run dev
```

Reset demo data: `<one command>`.

## Stack

| Layer | Choice | Why |
| --- | --- | --- |
| Frontend |  |  |
| Backend |  |  |
| Database |  |  |
| AI |  |  |
| Deploy |  |  |

## Roadmap / task list

Link to `TASKS.md`, or inline the lane table from it.

## Limitations and next steps

- What breaks first at scale.
- What the next week of work would be.
- Costs per request, if known.

## Team

- Name — lane
- Name — lane
