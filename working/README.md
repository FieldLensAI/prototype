# How the FieldLensAI prototype works

This folder explains the prototype one screen at a time: what you see, what to click, what happens
inside the code, and what to tell the judges.

| Doc | Screen |
|---|---|
| [01_plan.md](01_plan.md) | **1 · Plan**: the imported schedule |
| [02_reconcile.md](02_reconcile.md) | **2 · Reconcile 13-Sep**: one day of field reports turned into linked events |
| [03_planner_review.md](03_planner_review.md) | **3 · Planner review**: the items the system refused to decide alone |
| [04_supervisor_assistant.md](04_supervisor_assistant.md) | **4 · Supervisor assistant**: the chat that asks back |
| [05_impact_and_export.md](05_impact_and_export.md) | **5 · Impact & export**: schedule impact, P6 update file, audit trail |
| [06_benchmark.md](06_benchmark.md) | **6 · Benchmark**: FieldLensAI vs plain rules on 61 labelled statements |
| [07_rules_reference.md](07_rules_reference.md) | Every linking path, hold-back rule and learning rule in one place |

## The one-paragraph version

A Primavera schedule is imported and every activity gets a **tag** (XX-107, E-201, C-4401…) and a
**work step** (ERECT, WELD, HYDROTEST…) read from its description. Field reports arrive as a DPR,
a discipline spreadsheet and a supervisor voice note. An LLM turns free text into **events**
(what happened, to which thing, when) and must quote the report word for word; the spreadsheet
is parsed without any AI. Deterministic rules then **link** each event to an L5/L6 activity:
by activity ID, else by tag + work step, else by text search. **Hold-back rules** decide whether
the link is safe to accept automatically. Everything else goes to a **planner** (or back to the
supervisor as a question). Accepted events land in an **append-only ledger**, which drives the
schedule-impact calculation, the **P6 update file** and the **audit trail**. Planner and supervisor
answers teach the system the project's **vocabulary** ("HT" means hydrotest).

## Pipeline

```
data/schedule.csv ──► core.Project()                      tag index + work-step index + P6 actuals
                           │
DPR text ─────────► extract.extract_text()  ─┐            LLM on Groq, JSON output,
Voice transcript ─► extract.extract_text()  ─┤            every field validated, quote must be verbatim
Spreadsheet ──────► extract.extract_sheet() ─┤            deterministic, no LLM
                                             ▼
                               core.Project.link(event)    ID → TAG+STEP → TEXT, then hold-back checks
                                             │
                     ┌───────────────────────┼─────────────────────────┐
                   AUTO                    REVIEW                  UNMATCHED
                     │                       │                         │
                     ▼                       ▼                         ▼
             core.Project.accept()    planner / supervisor       planner: new work?
                     │                  accept → learn()
                     ▼
             ledger ──► core.Project.impact()  (CPM forecast vs baseline)
                    ──► core.Project.export_rows()  (P6 update CSV)
```

## Who decides what

| Decision | Made by | Why |
|---|---|---|
| What the report says happened | LLM (Groq), constrained to quote the text | Free text is messy; LLMs read it well |
| Which tag / work step that means | `core.py` rules + learned vocabulary | Must be deterministic and auditable |
| Which activity it belongs to | `core.py` linking | Same |
| Whether it is safe to accept | `core.py` hold-back rules | Same; the LLM never auto-accepts |
| Anything uncertain | Planner or supervisor | People who know the site |
| What goes into Primavera | Planner imports the CSV | FieldLensAI never writes to P6 |

## Setup

1. Free Groq key from https://console.groq.com/keys → paste into `prototype/.env` as `GROQ_API_KEY=...`
2. `GROQ_MODEL=openai/gpt-oss-120b` (listed for this key; change it in `.env` if Groq retires it)
3. From `prototype/`:
   ```bash
   uv run python test_core.py      # self-check, no API
   uv run streamlit run app.py     # the demo
   uv run python bench.py          # benchmark in the terminal
   ```
4. Free tier = about 8,000 tokens a minute, roughly six extraction calls. The code waits and retries
   automatically. Every result is saved in `data/extract_cache.json`, so after one full run the demo is
   instant and works offline. **Keep that file for presentation day.**

## Glossary

| Term | Meaning here |
|---|---|
| Tag | Physical identifier: line (XX-107), equipment (E-201, P-301A), cable (C-4401), test pack (TP-07) |
| Work step | What was done to it: ERECT, WELD, HYDROTEST, SET, GROUT, ALIGN, EXCAVATE, CONCRETE, BACKFILL, LAY_CABLE, TERMINATE, MEGGER, QA_ACCEPT, MC |
| Event | One extracted fact: tag(s), work step, START/PROGRESS/FINISH/HOLD, date, quantity, verbatim quote |
| Ledger | Append-only list of accepted events per activity; actual start/finish are derived from it |
| Data date | The status date: the day the latest reports describe (13-Sep in the demo) |
| Hold-back rule | A check that stops an automatic update (see 07) |
| Gated activity | QA acceptance and milestones: always need planner sign-off |
| Float | Days an activity can slip without moving the end date; zero float = critical path |

## Files

| File | Role |
|---|---|
| `core.py` | Everything deterministic: schedule import, tags, work steps, linking, rules, ledger, learning, CPM, export |
| `extract.py` | LLM extraction via Groq + spreadsheet parser + cache |
| `app.py` | The Streamlit screens |
| `bench.py` | Benchmark replay |
| `test_core.py` | Self-check (runs without an API key) |
| `data/schedule.csv` | Synthetic Unit-3 pipe-rack schedule, 30 activities, P6 status as of 6-Sep |
| `data/lexicon.json` | Work-step vocabulary, gated prefixes, confirmations needed for learning |
| `data/demo_day/` | The three 13-Sep reports |
| `data/benchmark.jsonl` | 61 statements, 7 Sep – 2 Oct, each with the correct answer |
| `data/extract_cache.json` | Saved LLM results |
| `.env` | Groq key and model (git-ignored) |
