# 1 · Plan: the imported schedule

## What you see

A table of the 30 L5/L6 activities for the synthetic **Unit-3 Pipe Rack PR-3** project:

| Column | Where it comes from |
|---|---|
| Activity, Description, Planned | `data/schedule.csv`, standing in for a Primavera export |
| Work step, Tags | **Derived by FieldLensAI** from the description at import |
| Total float (d) | Calculated from the schedule logic (critical path method) |
| Actual start / finish | P6 status at import + everything already reconciled for 7–12 Sep |

The project: six pipe lines (XX-101, XX-104, XX-107, XX-112, XX-170, XX-171), each with Erect → Weld →
Hydrotest; civil foundations for a rack extension; exchanger E-201; pump P-301A; cable C-4401; QA acceptance
of test pack TP-07; and the **mechanical completion** milestone M-U3-MC, planned for **24-Sep**.

## What happens in the code

`core.Project.__init__` (called once when the app starts):

1. Reads each row of `schedule.csv`.
2. **Work step**: `lexicon_step(description)` finds the first vocabulary word from `data/lexicon.json` in the
   description. "Erect Line 24"-XX-107" → `ERECT`; "Megger test cable C-4401" → `MEGGER`.
3. **Tags**: the regex `TAG_RE` pulls identifiers out of the description. "Erect Line 24"-XX-107" → `XX-107`;
   "QA acceptance test pack TP-07 (XX-104, XX-107, XX-112)" → four tags.
4. Builds the **tag index** (tag → activities). XX-107 → PIP-1842 (Erect), PIP-1843 (Weld), PIP-1844 (Hydrotest), QA-1845.
5. Loads existing P6 actuals into the **ledger** as events marked `by: P6`.

`app.reset()` then applies the correct answers for all benchmark reports dated 7–12 Sep
(`Project.preload`), so the demo starts on the morning of 13-Sep with history already reconciled.

**Float** comes from `Project.cpm(actuals=False)`: a forward pass (earliest dates) and a backward pass
(latest dates) over the finish-to-start links. The self-check confirms that the calculated dates equal the
planned dates in the file, so the plan is internally consistent.

## Why it matters

- The schedule is the **source of planned structure**. Nothing about activities is invented by AI.
- Deriving tags and work steps once, at import, is what makes later linking deterministic.
- On a real project, tags may not be in activity descriptions. Then they would come from a line list or
  test-pack register instead. That's the first thing to check with OIL.

## Point out to the judges

- **PIP-1842, PIP-1843, PIP-1844 share the tag XX-107.** A tag alone can't pick the right activity; the work step can.
- **Zero-float chain:** PIP-1842 → PIP-1843 → PIP-1844 → QA-1845 → M-U3-MC is the critical path in the baseline.
- XX-112 erection (PIP-1861) was planned for 8–10 Sep and **hasn't started**. That matters in screen 5.

## Limits

- 30 activities, not 20,000. The algorithm doesn't change with size; candidate lookup is by tag, so it stays fast.
- Calendar days, finish-to-start links only. Primavera recalculates with real calendars and link types.
