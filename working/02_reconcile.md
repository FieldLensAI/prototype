# 2 · Reconcile 13-Sep: from field reports to linked events

## What you see

Three reports from 13-Sep, side by side:

| Report | Content |
|---|---|
| Contractor DPR | "XX-107 spool erection completed at 17:15." · "Temporary support fabricated near PR-3 grid 7." · "Hydrotest of XX-104 scheduled for Monday." · manpower / weather |
| Piping spreadsheet | `Line 107, Welding, 6, 22` |
| Supervisor voice note (transcript) | "hydro test on one-oh-seven done" |

Click **Extract and link**. A table shows every event with its link and outcome.

## The result (real output with `openai/gpt-oss-120b`)

| Source | Evidence (verbatim) | Link path | Activity | Outcome | Why |
|---|---|---|---|---|---|
| DPR | XX-107 spool erection completed at 17:15. | TAG+STEP | PIP-1842 | 🟢 Auto-accepted | tag ✓ step ✓ predecessors ✓, explicit finish |
| DPR | Temporary support fabricated near PR-3 grid 7. | TEXT | – | 🟣 Unmatched | No tag, and no activity is similar enough |
| XLS | Line 107 \| Welding \| 6 \| 22 | TAG+STEP | PIP-1843 | 🟢 Auto-accepted as progress (27%) | "Line 107" → XX-107, "Welding" → WELD |
| VOICE | hydro test on one-oh-seven done | TAG+STEP | PIP-1844, PIP-2210, … | 🟠 Planner review | Welding on XX-107 isn't finished; XX-170 is a near-identical tag |

"Hydrotest of XX-104 scheduled for Monday" produces **no event**: planned work is not progress.
Manpower and weather lines produce none either.

## What happens in the code, step by step

### Step 1: extraction (`extract.py`)

- **DPR and voice → `extract_text()`**. The text goes to Groq with the instructions in `SYSTEM`:
  copy tags and work-step words exactly as written, quote the exact span, don't invent dates, skip
  planned work. The model returns JSON (`response_format={"type": "json_object"}`).
- **`_clean()`** checks every field, because JSON mode guarantees valid JSON but not the right fields:
  event type must be START/PROGRESS/FINISH/HOLD, quantities must be numbers, dates must be YYYY-MM-DD.
- **Verbatim check**: if the quoted `span` is not found in the report, the event is **rejected**. This stops
  the model from paraphrasing or hallucinating a report line.
- **Spreadsheet → `extract_sheet()`**, no AI. `Done < Total` → PROGRESS; `Done = Total` → FINISH but with
  `completion_explicit = False`, because a quantity reaching 100% is not the same as someone saying "complete".
- Results are cached in `data/extract_cache.json` (key = model + prompt + text), so the same report gives the
  same result every time.

Example event for the voice note:
```json
{"span": "hydro test on one-oh-seven done", "tag_refs": ["one-oh-seven"],
 "work_phrase": "hydro test", "event_type": "FINISH", "completion_explicit": true, "date": "2026-09-13"}
```

### Step 2: linking (`core.Project.link`)

For each event:

1. **Normalise tags** (`normalize_tag`): "one-oh-seven" → 107 → XX-107; "Line 107" → XX-107; "xx101" → XX-101;
   "P301A" → P-301A.
2. **Work step** (`step_of`): "erection" → ERECT, "Welding" → WELD, "hydro test" → HYDROTEST.
3. **Pick candidates**, taking the first path that applies:
   - **ID**: an activity ID appears in the text.
   - **TAG+STEP**: activities with that tag *and* that work step. XX-107 + ERECT → only PIP-1842.
   - **TEXT**: no tag, so fall back to word-overlap search. It never auto-accepts, because its scores aren't calibrated.
4. **Hold-back checks** (`checks`) on a single candidate. Any one of them sends the item to review (full list in 07):
   - is the finish stated or only implied?
   - is the date after the report date?
   - are the predecessors started/finished?
   - does it conflict with a recorded finish?
   - is it a gated activity?
   - did the tag come from speech, with a near-identical tag in the schedule?

### Step 3: routing (`app.handle`)

- **AUTO** → `Project.accept()` adds the event to the ledger immediately.
- **REVIEW / UNMATCHED** → planner queue (screen 3).

## Walking through the four events

- **Erection of XX-107**: three activities share XX-107; the work step leaves one. Predecessors: none.
  Finish explicitly stated. No rule fires → **auto-accepted**. Actual finish 13-Sep, one day after plan.
- **Temporary support**: no tag. The text search finds nothing above the similarity floor → **unmatched**,
  flagged as possible new work. It is never silently dropped.
- **Spreadsheet row**: "Line 107" has no letters, but only one line ends in 107 → XX-107. WELD → PIP-1843.
  PROGRESS with 6 of 22 joints. Actual start recorded as **"on or before 13-Sep"**, because the sheet doesn't
  say when welding began.
- **Voice note**: "one-oh-seven" → XX-107, hydro test → PIP-1844. But:
  - PIP-1844's predecessor (welding, PIP-1843) is only 6/22 done → **OUT_OF_SEQUENCE**;
  - the tag came from speech and XX-170 has the same digits in a different order → **SIMILAR_TAG**, so XX-170's
    hydrotest (PIP-2210) is added as a candidate.
  → **planner review**.

## Why it matters

- The DPR line is the problem statement's own example, solved by a rule rather than by a guess.
- The voice note shows the safety model: a rules-only system (Baseline A+) would have recorded a false
  finish on PIP-1844.
- "Scheduled for Monday" shows **unknown stays unknown**.

## Point out to the judges

"Four events, two automatic, two sent to people, zero guesses. Every row keeps the exact words it came from."
