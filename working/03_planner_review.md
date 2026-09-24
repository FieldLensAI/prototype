# 3 · Planner review: what the system won't decide alone

## What you see

One card per held-back item, showing:
- the outcome (🟠 review or 🟣 unmatched), the source and file reference;
- the **exact quote** from the report;
- every **reason** it was held back, in plain words;
- an **Activity** dropdown: the candidates first, each with why it fits or doesn't
  ("tag ✓ · step ✓ · predecessors not finished ✗"), then every other activity;
- an **Event** dropdown (START / PROGRESS / FINISH) so the planner can correct the type;
- buttons: **Accept**, **New work (raise in P6)**, **Reject**.

## Try it

For the voice note "hydro test on one-oh-seven done":

| Candidate | Why |
|---|---|
| PIP-1844 Hydrotest XX-107 | tag ✓ · step ✓ · predecessors not finished ✗ |
| PIP-2210 Hydrotest XX-170 | tag ✗ · step ✓ · predecessors finished ✓ |
| PIP-1832 Hydrotest XX-101 | tag ✗ · step ✓ · predecessors not finished ✗ |

Pick **PIP-2210**, keep FINISH, click **Accept**. The supervisor said "one-oh-seven" but meant "one-seven-oh".
XX-170's welding is finished, so its hydrotest can be complete; XX-107's welding is only 6 of 22 joints.

For the temporary support, click **New work (raise in P6)**: it isn't in the schedule, so the planner adds
it in Primavera if it matters.

## What happens in the code

- **Accept** → `Project.accept(ev, activity, by="planner", event_type=...)` adds the event to the ledger,
  with the original quote as evidence and "planner" as the decision-maker.
- Then `Project.learn(ev, activity)` checks whether the answer teaches something new:
  - a **work-step phrase** not in the vocabulary (e.g. "HT") → a rule "HT → HYDROTEST";
  - an **object nickname** with no tag (e.g. "big exchanger") → a rule "big exchanger → E-201".
  
  A new rule is **provisional**. Items that rely on it are still reviewed until planners have confirmed it
  twice (`confirmations_needed` in `lexicon.json`). Learned rules appear in the sidebar with their count.
  (For this voice note nothing new is learned: "hydro test" is already in the vocabulary.)
- **New work / Reject** → the item leaves the queue; nothing enters the ledger.

## Why candidates, not a blank form

Showing the top candidates with reasons turns a 5-minute search through the schedule into a
one-click decision. The benchmark measures this as "right activity in top 3".

## Why it matters

- The system **refuses to guess**. Wrong automatic finishes are worse than slow ones: they make successors
  look free to start and can inflate contractor progress claims.
- The planner stays the owner of the schedule; FieldLensAI does the searching and cross-checking.
- Every decision is recorded with who made it, which gives the audit trail in screen 5.

## Point out to the judges

"The planner doesn't search the schedule. They get the quote, the reasons and three candidates, and click once.
A rules-only system would have recorded a false hydrotest finish here."
