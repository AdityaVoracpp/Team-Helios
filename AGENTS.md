# Workspace rules — Helios hackathon

This workspace is for an AI-engineering hackathon. Treat the event's official rules and judging rubric as the top-priority specification.

## Always

- Load the `hackathon-ai-eng` skill before any planning, scoping, or build work here.
- Read `hackathon/RULES.md` first. If it still marks a field `OPEN`, ask rather than assume.
- Optimize for a demoable end-to-end path. Prefer a thin working slice over a broad unfinished one.
- Keep the demo path stable: never change it without saying so and confirming a fallback exists.
- Put new project code under `hackathon/`, and keep generated artifacts out of the skill directory.
- Ask before adding a dependency, a service, or a language — each one is a timebox risk.
- State the deadline-relative tradeoff when proposing work: what gets cut to pay for it.

## Never

- Commit API keys, tokens, or credentials. Use `.env` plus `.env.example`.
- Present unverified code as working. Run it, or label it untested.
- Fabricate benchmark numbers, accuracy claims, or sponsor integrations for the pitch.
- Delete or rewrite existing work to make room for new work without explicit approval.

## Conventions

- Decisions with lasting effect go in `hackathon/DECISIONS.md` as one line each: date, decision, reason.
- Demo narration lives in `hackathon/DEMO-SCRIPT.md` and stays in sync with what the code actually does.
- Report progress against the deadline clock in `hackathon/DAY-PLAN.md`, never in "hours remaining": what is demoable now, what is next, what is blocked.
- Keep `hackathon/TASKS.md` current when task ownership or status changes; it is the shared source of truth and judges read the repo.
