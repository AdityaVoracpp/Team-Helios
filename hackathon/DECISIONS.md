# Decisions log

One line per lasting decision: date, decision, reason. Append; do not rewrite history. This is what you cite when a judge asks why the architecture looks the way it does.

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-10-31 | Team task allocation set to 40% Backend/AI (Member 1), 40% Frontend/UX (Member 2), 20% Data/Evaluation/Pitch (Member 3) | Balances technical build with mandatory hackathon non-code deliverables (Evaluation Report, 3 worked examples, README) and 25% UX judging weight |
| 2026-10-31 | Skip standalone KB collection; streamline historical data schema to 10 core fields on tickets | Simplifies data curation for Member 3 and satisfies FR-03/FR-04 with a single schema |
| 2026-10-31 | Include `assignment_group`, `status`, `created_at` (FR-07) and `feedback_status` (FR-06) in ticket schema | Explicitly satisfies FR-06 reviewer feedback tracking and FR-07 multi-facet queue filtering |

## Open decisions

Track unresolved choices with a deadline so they do not drift into hour 30.

| Decision | Owner | Deadline | Blocked on |
| --- | --- | --- | --- |
|  |  |  |  |
