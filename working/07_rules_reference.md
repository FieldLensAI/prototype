# 7 · Rules reference

Everything the deterministic core does, in one place. Code: `core.py`.

## Tag normalisation (`normalize_tag`, `spoken_digits`)

| Written / spoken | Becomes | How |
|---|---|---|
| `XX-107`, `xx107`, `XX 107` | XX-107 | Uppercase, optional dash |
| `24"-XX-107`, `line XX-107` | XX-107 | Size prefix and the word "line" removed |
| `Line 107`, `107` | XX-107 | Bare number matched against tag numbers (only if unique) |
| `one-oh-seven`, `one seven one` | 107, 171 | Runs of two or more digit words become digits |
| `P301A` | P-301A | Letters + digits split |
| learned nickname, e.g. `big exchanger` | E-201 | Learned tag rule (see Learning) |

Tags not in the schedule (e.g. `PR-3`, `TP-03`) are ignored.

## Work steps (`data/lexicon.json`)

| Step | Words |
|---|---|
| ERECT | erect, erected, erection, lifted, lift |
| WELD | weld, welded, welding, joints, jts |
| HYDROTEST | hydrotest, hydro test, hydrostatic test, pressure test |
| SET | set, setting, placed, positioned |
| GROUT | grout, grouting, grouted |
| ALIGN | align, aligned, alignment |
| EXCAVATE | excavate, excavation, excavated |
| CONCRETE | pour, poured, concrete, concreting |
| BACKFILL | backfill, backfilling, backfilled |
| LAY_CABLE | lay, laying, laid, pulling, pulled |
| TERMINATE | terminate, termination, terminated, glanding |
| MEGGER | megger, ir test, insulation resistance |
| QA_ACCEPT | qa acceptance |
| MC | mechanical completion |

"HT" is deliberately **not** in the list, so the demo can show the system learning it.

## Linking paths (`link`)

| Path | When | Can auto-accept? |
|---|---|---|
| ID | An activity ID appears in the text | Yes, if no hold-back rule fires |
| TAG+STEP | Tag found and exactly one activity has that tag and work step | Yes, if no hold-back rule fires |
| TAG+STEP (several) | Tag + step match more than one activity | No (SEVERAL_ACTIVITIES) |
| TAG | Tag found but the step is unknown | No (UNKNOWN_STEP) |
| TAG, no activity for step | Tag known, step known, but no such activity | No → **unmatched**, possible new work |
| TEXT | No tag: word-overlap search, top 3 above a similarity floor | **Never** (scores not calibrated) |
| none | Nothing above the floor | No → **unmatched** |

## Hold-back rules (`checks` + `link`)

| Flag | Fires when | Example |
|---|---|---|
| IMPLIED_FINISH | FINISH without an explicit completion statement | Spreadsheet row reaches 18/18 |
| FUTURE_DATE | Event date after the report date | — |
| OUT_OF_SEQUENCE | FINISH while a predecessor is unfinished, or START/PROGRESS while one is unstarted | Hydrotest done, welding 6/22 |
| CONFLICTS_WITH_RECORDED_FINISH | FINISH with a different date than the recorded finish | Duplicate report a day later |
| AFTER_RECORDED_FINISH | Progress dated after the recorded finish | — |
| GATED | FINISH on QA-… or M-… activities | QA acceptance, mechanical completion |
| SIMILAR_TAG | Voice/diary FINISH, and a tag with the same digits reordered or one digit different exists | 107 vs 170 |
| SEVERAL_ACTIVITIES | Tag + step match more than one activity | — |
| UNKNOWN_STEP | Work step not recognised | "HT" before it's learned |
| NO_ACTIVITY_FOR_STEP | Known tag, known step, no activity | "big exchanger hydro test" (E-201 has no hydrotest) |
| NO_TAG | Linked by text search only | Civil foundations reports |
| PROVISIONAL_RULE | Depends on a learned rule with fewer than 2 confirmations | Second "HT" report |

**Auto-accept = ID or TAG+STEP path, exactly one candidate, and no flag at all.**

## Ledger rules (`accept`, `state`)

- Append-only; nothing is overwritten.
- The same activity + event + date from two sources becomes **one event with two pieces of evidence**.
- Actual start = earliest accepted start/progress/finish date; **exact** only if a START was reported that day,
  otherwise "on or before".
- Actual finish = accepted finish date. Two different finish dates → consistency **CONFLICT**.

## Learning (`learn`)

| Taught by | Rule | Active after |
|---|---|---|
| A work-step phrase not in the vocabulary, resolved to an activity | phrase → that activity's work step | 2 confirmations |
| An object phrase with no tag, resolved to an activity with a tag | phrase → that tag | 2 confirmations |

A provisional rule can suggest candidates straight away, but anything relying on it is reviewed (PROVISIONAL_RULE)
until it's confirmed. Learning never loosens GATED, OUT_OF_SEQUENCE or any other safety check. Rules live in the
session (sidebar); a real system would store them per project with who taught them.

## Baselines used in the benchmark

| System | What it does |
|---|---|
| A · exact rules | Activity ID or exact tag string in the text; if several, the description's first word must appear. Accepts any unique match. |
| A+ · rules + normaliser | Our tag normaliser + work-step vocabulary. Accepts any unique match, **no hold-back rules**. |
| FieldLensAI | Everything above, with hold-back rules (with and without learning). |
