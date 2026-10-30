# Team-Helios

> One line: for **[user]** who **[pain]**, this does **[action]** so they get **[outcome]**.

<!-- Sprint 0 deliverable. This README is both the team roadmap and the documentation judges read.
     Fill the bracketed sections before D-5:00, finalize at D-0:50. Delete these comments as you go. -->

## Problem

Two or three sentences. Name the user, the cost of the problem, and why the obvious existing solution fails.

## What it does

1. 
2. 
3. 

**AI step:** what the model receives, what it returns, and what happens when it fails.

**Real vs mocked:** be specific and honest. Judges notice, and honesty reads as competence.

## Live demo

- URL: _not deployed yet_
- Demo credentials: —
- Known limitations on the live instance: —

## Architecture

```
React (Vite)  →  API  →  Database
                    ↓
               LLM provider
```

One short paragraph on why this shape, and what would change at scale.

## API contract

<!-- Agreed in Sprint 0 so backend and frontend build in parallel. Do not change after D-5:00 without updating this table. -->

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| GET | `/api/health` | — | `{"status":"ok"}` |
|  |  |  |  |

## How to run locally

```bash
git clone <repo-url> && cd Team-Helios
cp .env.example .env   # then fill in your keys

# backend
cd backend && pip install -r requirements.txt && uvicorn main:app --reload

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

## Team

| Name | Lane |
| --- | --- |
|  |  |

## Event

One-day AI-engineering hackathon, three sprints. Planning docs and the deadline clock live in [`hackathon/`](hackathon/):

- [RULES.md](hackathon/RULES.md) — judging criteria and requirements
- [DAY-PLAN.md](hackathon/DAY-PLAN.md) — sprint clock and checkpoints
- [TASKS.md](hackathon/TASKS.md) — task board by lane
- [DECISIONS.md](hackathon/DECISIONS.md) — architecture decisions
- [DEMO-SCRIPT.md](hackathon/DEMO-SCRIPT.md) — pitch and demo plan
