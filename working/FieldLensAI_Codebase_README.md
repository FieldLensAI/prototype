# FieldLensAI Prototype: How the Codebase Works

The whole prototype is about 990 lines of Python across five files. It all rests on one principle:
**the LLM reads, the rules decide.**

Code: `~/Desktop/Projects/FieldLensAI/prototype/` · Repo: `github.com/FieldLensAI/prototype`

---

## 1. What we're doing

Site teams report progress in messy ways, like "XX-107 spool erection completed at 17:15" or a voice note saying
"hydro test on one-oh-seven done". A planner has to work out, by hand, which of thousands of Primavera activities
each line refers to, whether it means started or finished, and on what date.

The prototype automates that matching:
- it uses an LLM **only** to turn free text into structured facts;
- it uses plain, auditable rules to link each fact to one schedule activity;
- it accepts the link automatically only when nothing looks risky, and sends everything else to a human.

Accepted facts go into a ledger, which drives a schedule-impact calculation and a Primavera import file.

---

## 2. The files

```
prototype/
├── core.py        345 lines  the brain: schedule, tags, work steps, linking, rules, ledger, learning, CPM, export
├── extract.py     185 lines  the reader: LLM (Groq) for free text, plain parser for spreadsheets, cache
├── app.py         266 lines  the screens: Streamlit UI with 6 tabs
├── bench.py       111 lines  the proof: replays 61 labelled reports through 3 systems and scores them
├── test_core.py    77 lines  self-checks (no API needed)
└── data/
    ├── schedule.csv          the "Primavera export": 30 invented activities
    ├── lexicon.json          work-step vocabulary + gating rules
    ├── demo_day/             the three 13-Sep reports
    ├── benchmark.jsonl       61 reports, each with the correct answer
    └── extract_cache.json    every LLM answer, saved
```

`core.py` never calls an AI. `extract.py` never decides anything. That separation is the design.

---

## 3. Follow one report through the code

This is the voice note **"hydro test on one-oh-seven done"**, from click to screen.

### Step 0 · The schedule is loaded once (`core.py:45`, `Project.__init__`)

Each row of `schedule.csv` becomes a dictionary. Two fields are *derived*:
- **work step**: `lexicon_step()` (`core.py:71`) scans the description for words from `lexicon.json`.
  "Hydrotest Line 24"-XX-107" → `HYDROTEST`.
- **tags**: the regex `TAG_RE` pulls identifiers from the description → `["XX-107"]`.

It then builds a **tag index**: `XX-107 → [PIP-1842 (Erect), PIP-1843 (Weld), PIP-1844 (Hydrotest), QA-1845]`.
Existing P6 actuals go into `self.ledger`, a plain list of accepted events.

### Step 1 · The LLM extracts (`extract.py:132`, `extract_text`)

1. It checks the cache first. The key (`_key`, line 70) is a hash of model + prompt + source + date + text, so the
   same text always gives the same answer.
2. On a cache miss, `_call_llm()` (line 103) sends the text to Groq with the `SYSTEM` prompt: copy tags and
   work-step words *exactly as written*, quote the source, never invent dates, and ignore planned work.
   JSON mode is on (`_create`, line 93).
3. It waits and retries if Groq says "rate limited".
4. `_clean()` (line 79) checks every field, because JSON mode only guarantees *valid* JSON, not the *right* fields.
5. **Verbatim check** (lines 140–143): if the quoted `span` isn't actually in the text, the event is rejected.
   This is the anti-hallucination guard.

Result:

```python
{"span": "hydro test on one-oh-seven done", "tag_refs": ["one-oh-seven"],
 "work_phrase": "hydro test", "event_type": "FINISH", "completion_explicit": True,
 "date": "2026-09-13", "source": "VOICE", ...}
```

The LLM *didn't* turn "one-oh-seven" into XX-107. Interpreting it is the rules' job.

### Step 2 · The rules normalise it (`core.py`)

- `spoken_digits()` (line 37): "one-oh-seven" → "107", using a regex over runs of two or more digit words.
- `normalize_tag()` (line 89): strips "line" and size prefixes like `24"-`, fixes dashes, and matches a bare "107"
  against tag numbers → `{"XX-107"}`.
- `step_of()` (line 78): "hydro test" → `HYDROTEST` from the lexicon. If a phrase isn't in the lexicon, it checks
  **learned** rules.

### Step 3 · The rules link it (`link()`, line 190)

The first path that applies wins:
1. **ID**: an activity ID like `PIP-1861` appears in the text → that activity.
2. **TAG+STEP**: activities with the tag *and* the work step. XX-107 + HYDROTEST → only **PIP-1844**.
3. **TEXT**: no tag, so word-overlap search (`ranked()`, line 179). This path never auto-accepts.

### Step 4 · Hold-back checks (`checks()`, line 151)

With one candidate, it asks:
- Is the finish only implied? Is the date after the report date?
- **Is a predecessor unfinished?** PIP-1844 needs PIP-1843 (welding) finished. `state("PIP-1843")` reads the
  ledger: only 6/22 progress → `OUT_OF_SEQUENCE`.
- Does it conflict with a recorded finish? Is it gated (QA-/M-)? Does it mention failure or leaks?
- **Voice report of a finish, with a near-identical tag?** `similar_tags()` (line 115) finds XX-170, with the same
  digits in a different order → `SIMILAR_TAG`, and PIP-2210 (XX-170's hydrotest) is added as a candidate.

Any flag means `REVIEW`. No candidates, or a known tag with no activity for that step, means `UNMATCHED`.
No flags at all means `AUTO`. `_decision()` (line 239) packages the event, path, candidates, flags and a
human-readable "why" for each candidate (`explain()`, line 243).

### Step 5 · Routing (`app.py:58`, `handle`)

`AUTO` goes straight into the ledger via `accept()`. Anything else is appended to the planner queue.

### Step 6 · A person resolves it (`app.py`, tab 3)

The planner picks PIP-2210 and clicks Accept. That calls:
- `accept()` (`core.py:137`), which appends `{activity, type, date, evidence: [the quote], by: "planner"}` to the
  ledger. If the same activity + event + date already exists, it just adds a second piece of evidence, so duplicate
  reports merge.
- `learn()` (line 253). If the answer taught something new (e.g. "HT" → HYDROTEST, or "big exchanger" → E-201),
  it stores a rule with a confirmation count. The rule stays **provisional** until confirmed twice, and anything
  using a provisional rule is still reviewed.

### Step 7 · Impact and export

- `state()` (line 126) derives each activity's actuals from the ledger. Actual start is the earliest event,
  "exact" only if a START was reported. Actual finish comes from a FINISH event, and two different finish dates are
  flagged as a conflict.
- `cpm()` (line 278) does a forward pass over the finish-to-start links, twice: once on the plan (baseline) and once
  with actuals fixed and unstarted work pushed after the data date (forecast). `impact()` (line 313) compares the two.
  That's where "XX-112 moves completion +4 days" comes from.
- `export_rows()` (line 320) builds the P6 update CSV: one row per activity touched this session, with the
  evidence quotes.

---

## 4. Each file, briefly

### `core.py`

One class, `Project`, holding the schedule, the ledger and the learned rules.

| Section | Functions | Job |
|---|---|---|
| Vocabulary | `lexicon_step`, `step_of`, `normalize_tag`, `resolve_tags`, `similar_tags` | Messy words → canonical tags and steps |
| Ledger | `state`, `accept` | Append-only event history; derived actuals |
| Linking | `checks`, `ranked`, `link`, `_link_exact`, `explain` | Candidates, hold-back rules, decision |
| Learning | `learn` | Planner/supervisor answers → vocabulary rules |
| Impact | `cpm`, `impact`, `export_rows` | Schedule forecast, P6 file |
| Demo setup | `preload` | Applies the correct answers for 7–12 Sep so the demo starts mid-project |

`link()` also takes a `policy` argument. `"A"` (exact strings) and `"A+"` (normaliser, but no hold-back rules) are
the benchmark baselines, so all three systems share the same code and differ only in the safety layer.

### `extract.py`

Two readers and a cache:
- `extract_text` for DPRs and voice (LLM).
- `extract_sheet` for spreadsheets: **no AI**. `Done < Total` means progress; `Done = Total` means finish with
  `completion_explicit=False`, because a quantity reaching 100% isn't someone saying "complete".
- `extract_many` for the benchmark, one call at a time on the free tier; a failure on one statement doesn't stop the run.
- Settings come from `.env` via `python-dotenv`.

### `app.py`

Streamlit reruns the **whole script from top to bottom on every click**. State that must survive a click lives in
`st.session_state` (`ss`): the `Project`, the planner queue, the log and the chat. `reset()` (line 23) builds a fresh
`Project` and preloads 7–12 Sep. Each tab is a `with tabs[i]:` block:

| Tab | Line | What it does |
|---|---|---|
| Plan | 90 | Shows the schedule + derived steps/tags + CPM float |
| Reconcile | 103 | Extracts the 3 demo files, links each event, routes via `handle()` |
| Planner review | 136 | One card per queued item; Accept → `accept()` + `learn()` |
| Supervisor assistant | 166 | Chat: extract → link → auto-record, or ask one question with candidate buttons; a tap re-runs `checks()` and either records it or passes it to the planner |
| Impact & export | 221 | `impact()` metrics, slipped activities, `export_rows()` + download, audit trail |
| Benchmark | 249 | Calls `bench.run()` and draws the table and the weekly chart |

`api_errors()` (line 37) turns any Groq failure into a friendly message instead of a crash.

### `bench.py`

For each system (exact rules, rules + normaliser, FieldLensAI with and without learning), `replay()` (line 29)
starts a fresh `Project` and walks the 61 statements in date order:
- If the system auto-accepts, the event goes into the ledger and `compatible()` (line 18) checks it against the
  answer key. A mismatch is a **false update**.
- Anything else goes to a simulated planner, who puts the correct answer into the ledger, and learns from it if
  learning is on.

Replaying in order matters: sequence checks depend on what's already been accepted, just as on a real project.

### `test_core.py`

Five checks that need no API:
- the plan is internally consistent;
- the four-event worked example behaves correctly;
- the baselines behave like plain rules;
- learning needs two confirmations;
- bad news goes to a person.

---

## 5. Things worth knowing

- **Determinism.** The same report always gives the same result: temperature 0, plus the cache, plus rules.
  Only a *new* text calls Groq.
- **Data lives in the session.** Refreshing the browser or clicking Reset clears the ledger. Production would use a
  database with an append-only table.
- **Everything is synthetic.** The schedule, reports and answer key were written by us, and the schedule is read from
  a CSV, not a real `.xer` file.
- **Adding a vocabulary word needs no code.** Edit `lexicon.json`. Changing which activities always need sign-off is
  `gated_prefixes` in the same file.

---

## 6. Run it

```bash
cd ~/Desktop/Projects/FieldLensAI/prototype
uv run python test_core.py      # self-check, no API needed
uv run streamlit run app.py     # the demo (needs GROQ_API_KEY in .env for new text; cached text works offline)
uv run python bench.py          # benchmark table in the terminal
```

The screen-by-screen version, with what to tell the judges, is in `prototype/working/`.
`working/07_rules_reference.md` lists every rule in one table.
