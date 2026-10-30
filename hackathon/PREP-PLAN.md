# Pre-event preparation

Everything here is done **before** the day. On the day, use `DAY-PLAN.md` — a six-hour event leaves no room for setup that could have happened earlier.

## Build a harness, not a project

Prepare one repo template you can clone in minute 1. It should contain:

- Frontend scaffold (React + Vite), a layout, one card list, one form, loading and empty states.
- Backend scaffold with a health endpoint, CORS configured, JSON error handling.
- `.env` loading plus `.env.example`.
- A `seed.py` / `seed.ts` that loads fixtures into the DB and can be re-run to reset.
- A component library wired up (Tailwind + shadcn, MUI, or similar). UI is a quarter of the score; do not hand-roll CSS at hour 4.
- A deploy config for the chosen target so deployment is a `git push`, not a research project.

Time yourself building a trivial app from this template. Under 45 minutes is good. That number is your real Sprint 1 baseline.

## Verify the boring things now

- API keys created, each one tested once, rate limits and cost per call known.
- Database account created (managed Postgres or Supabase) and a connection string successfully used.
- Deploy targets connected to the accounts you will actually use on the day. Test a hello-world deploy end to end.
- GitHub repo permissions, so every teammate can push.
- Dependencies pre-installed and caches warm, so the venue network is not a dependency.

## Decide these in advance

- Stack: one frontend, one backend, one DB, one deploy target. Once. In writing. No debate on the day.
- Lane ownership: who owns backend, who owns frontend, who owns the clock, who owns the demo path.
- Team norms: commit small and often; push to a shared branch at every checkpoint; one person merges.
- The pitch role: who speaks. A single confident speaker beats four nervous ones.

## Rehearsals worth doing

1. **Dry run the clock.** Take a throwaway idea and run the Sprint 0 → 1 sequence for 90 minutes. You will learn where your setup costs time.
2. **Deploy under pressure once.** Break something and restore it. Deployment bugs are the highest-variance failure mode.
3. **Pitch practice.** 3 minutes, recorded. Watch it back. Fix the opening line.
4. **Commit-and-reset drill.** Prove the repo can be cloned and run from scratch by someone else, following only the README.

## Kit

Laptop, charger, USB-C → HDMI adapter, extension cord, hotspot with data, headphones, water, snacks, notebook, ID. Charge everything the night before.

## Sleep

Non-negotiable. A tired team loses more in the last 90 minutes than it gains overnight, and Sprint 2 is where submissions are won or lost.

## Question to resolve before arrival

The problem statement. Sprint 0 assumes you receive it at the start; if it is published earlier, ideate before the day and walk in with two candidate framings. Do not pre-build — the theme may change and prior code may not be allowed.
