# 5 · Impact & export: what the actuals mean, and what goes to Primavera

## What you see

1. **Three metrics**: mechanical completion baseline (24-Sep), forecast from accepted actuals, and how many
   actuals were accepted this session.
2. **Activities forecast to finish late**, with baseline finish, forecast finish, slip and baseline float.
3. **P6 update file**: one row per activity updated this session, with a **Download P6 update CSV** button.
4. **Audit trail**: every accepted event, who decided it, and the exact report words behind it.

## The numbers after screens 2 and 3

| | |
|---|---|
| Baseline mechanical completion | 24-Sep |
| Forecast | **28-Sep (+4 days)** |

Main slips in the forecast:

| Activity | Slip | Why |
|---|---|---|
| PIP-1861/1862/1863 (XX-112 erect/weld/test) | +6 | Erection planned 8–10 Sep has **not started** |
| QA-1845, M-U3-MC | +4 | Wait for XX-112's hydrotest |
| PIP-1842 (XX-107 erection) | +1 | Finished 13-Sep instead of 12-Sep |

**The insight to point out:** XX-107 is on the baseline critical path and finished a day late, but that is
**not** what moves the milestone. XX-112 not starting is. This is exactly why the schedule calculation comes
*after* reconciliation: better actuals show *which* slip matters.

## What happens in the code

### Forecast (`Project.cpm(actuals=True)` and `Project.impact()`)
- Activities with an actual finish keep it.
- Started activities run their planned duration from the actual start, but can't finish before the data date.
- Unstarted activities can't start before the day after the data date (you can't do work in the past).
- Everything else follows the finish-to-start logic. The baseline pass (`actuals=False`) is the same without actuals.
- The forecast is compared with the baseline for every activity.

### P6 update file (`Project.export_rows()`)
Only activities with events accepted **in this session** (not the preloaded history or P6's own status):

| Column | Meaning |
|---|---|
| activity_id | Primavera activity ID |
| actual_start | Earliest accepted start/progress date |
| start_is_exact | **Y** if a start was explicitly reported; **N (on or before)** if only progress was seen |
| actual_finish | Accepted finish date |
| physical_pct | 100 if finished, otherwise from reported quantities (e.g. 6/22 → 27) |
| evidence | Every quote behind the row, with its source |

Example rows:
```
PIP-1842, 2026-09-10, Y, 2026-09-13, 100, DPR 10-Sep "XX-107 spool erection started at 08:30." | … | "XX-107 spool erection completed at 17:15."
PIP-1843, 2026-09-13, N (on or before), , 27, "Line 107 | Welding | 6 | 22 | "
PIP-2210, 2026-09-10, Y, 2026-09-13, 100, … | voice: "hydro test on one-oh-seven done"
```

### Audit trail
Straight from the ledger: activity, event, date, decided by (auto / planner / supervisor), evidence.

## Why it matters

- **FieldLensAI never writes to Primavera.** The planner signs off this file and imports it, which avoids any
  integration dependency or governance problem.
- "On or before" dates show that uncertainty is kept, not hidden.
- Every date in the schedule can be traced back to who said it, where and when: useful for progress
  certification and contractor disputes.

## Limits

- Calendar days and finish-to-start links only; this is a stand-in so the demo can show impact.
  Primavera recalculates properly after import.
- The CSV columns are illustrative. The exact P6 import template is something to confirm with OIL.

## Point out to the judges

"The XX-107 slip is the one everyone reported, but the calculation shows XX-112 is what's actually moving
mechanical completion. And the file that goes to Primavera carries the evidence for every date."
