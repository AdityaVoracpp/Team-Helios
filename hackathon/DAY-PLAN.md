# Day plan — one-day, three sprints

Anchor everything to the **deadline D**, not to the start time. Sprint lengths vary (S0 1-1.5h, S1 3-4h, S2 1h), so recompute the clock on arrival and write the real times on the whiteboard.

The table below assumes a 6-hour day. If you get 6.5 hours, add the extra 30 minutes to Sprint 1 only.

| Clock | Time left | Phase | What happens |
| --- | --- | --- | --- |
| D-6:00 | 6h | Sprint 0 | Read problem statement, framing sentence, rubric mapping |
| D-5:45 | 5h45 | Sprint 0 | Stack decision, repo scaffold, **placeholder deployed** |
| D-5:15 | 5h15 | Sprint 0 | API contract written into README, tasks listed by lane |
| D-5:00 | 5h | Sprint 1 | Both lanes start; frontend on mocks |
| D-4:00 | 4h | Sprint 1 | **Integration checkpoint: real UI, real API, seeded data** |
| D-3:15 | 3h15 | Sprint 1 | **Midpoint check-in with Chapter Members** (30-second status) |
| D-2:15 | 2h15 | Sprint 1 | Core feature complete; UI polish pass begins |
| D-1:45 | 1h45 | Sprint 1 | **Hardening only** — no new scope |
| D-1:30 | 1h30 | Sprint 2 | **Feature freeze.** Deploy the real app |
| D-1:10 | 1h10 | Sprint 2 | **Backup demo video recorded** |
| D-0:50 | 50m | Sprint 2 | README finalized: live link, real vs mocked, architecture |
| D-0:30 | 30m | Sprint 2 | **Submit** repo + live link + pitch. Screenshot confirmation |
| D-0:15 | 15m | Sprint 2 | Rehearse pitch twice on the presenting machine |
| D-0:00 | 0 | Deadline | Nothing left to do. That is the goal |

## The three hard stops

These are the only schedule rules that matter. Everything else is negotiable.

1. **D-5:00 — Sprint 0 ends.** A live placeholder URL and a written contract exist, or you are already behind. Stop ideating.
2. **D-1:30 — feature freeze.** No new endpoints, screens, or dependencies. Anything unmerged at this point is abandoned, not finished.
3. **D-0:30 — submitted.** Not "ready to submit". The form is filled and confirmed.

## Lane assignment

| Lane | Owns | Must not |
| --- | --- | --- |
| Backend | DB schema, seed data, contract endpoints, the AI call | Block the frontend on an unmerged endpoint |
| Frontend | One flow, all states (loading/empty/error), styling, deployment of the UI | Invent API shapes not in the contract |
| Demo owner | End-to-end path, integration at D-4:00, reset script, rehearsal | Build a third feature |
| Clock/pitch | Rubric mapping, README, slides, submission, time calls | Let a sprint overrun silently |

With 2-3 people, merge backend and demo ownership, and frontend with clock/pitch. Never leave the clock unowned.

## Midpoint check-in script (90 seconds)

You get one shot at useful feedback. Say exactly this, then stop talking:

1. "We are building X for Y, in one sentence."
2. "Here is the flow working right now" — show it, even if ugly.
3. "We are finishing Z by the deadline."
4. "Is the demo the right thing to show, or would you cut something?"

Ask about the demo, not the code. Chapter members judge like judges: they react to what they see on screen. Take at most one suggestion; more than one is a scope change you cannot afford.

## Contingency cuts, in order

Cut from the bottom when behind schedule:

1. Auth — unless it is scored or required, it is not demoable in 6 hours.
2. Second feature / second page.
3. Fancy AI technique (fine-tuning, multi-agent, custom eval).
4. Deployment — only if it is genuinely blocking; a downloaded video demo beats no demo.
5. Stylish animation — never cut the base UI polish, since UX is a quarter of the score.

Never cut: seeded data, the demo path, the backup video, the submission.

## End-of-day definition of done

- One flow works from a cold start, reproducibly.
- Live URL loads (if deployed).
- Backup video exists and plays offline.
- README complete: problem, setup, live link, architecture, real vs mocked.
- Submission confirmed with a screenshot.
- Pitch rehearsed twice, timed.
