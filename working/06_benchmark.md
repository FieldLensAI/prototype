# 6 · Benchmark: does FieldLensAI beat plain rules?

## What you see

Click **Run benchmark**. A table compares four systems on the same field reports, a line chart shows how
many events went to the planner each week, and expanders list every false update.

The terminal version is `uv run python bench.py`.

## The data

`data/benchmark.jsonl`: **61 field statements** over four weeks (7 Sep – 2 Oct) from DPRs, spreadsheets and
voice notes, each labelled with the correct activity, event and date. They are deliberately messy:

| Kind | Examples |
|---|---|
| Easy | Activity ID written in the text; "XX-107 spool erection started at 08:30" |
| Medium | "xx101", "Line 107", "P301A", spoken "one-oh-four", reports with no tag |
| Hard | "HT" slang, a 107/170 speech mix-up, 18/18 joints but "2 joints under repair", a stale late report, a duplicate report with a different date, a premature QA sign-off, "scheduled for Monday", new work (temporary support, scaffolding, painting) |
| Gated | QA acceptance, mechanical completion |

## How it runs (`bench.py`)

For each system, a fresh project replays all statements **in date order**:
1. Extract events (LLM, cached; same extraction for every system, so only linking and safety differ).
2. Link each event with that system's rules.
3. **Auto-accepted** → into the ledger, then checked against the answer key.
4. **Anything else** → a simulated planner resolves it from the answer key, which puts the correct actual in
   the ledger (as a real planner would). With learning on, the planner's answer also teaches vocabulary.

**False update** = an auto-accepted event whose activity, event type or date doesn't match the answer key.

## Results (`openai/gpt-oss-120b` on Groq, 63 extracted events)

| System | Auto-accepted | False updates | Auto precision | Sent to planner | Right activity in top 3 |
|---|---|---|---|---|---|
| A · exact rules | 30 | **4** | 87% | 33 | – |
| A+ · rules + our normaliser | 40 | **5** | 88% | 23 | 84% |
| FieldLensAI (no learning) | 29 | **1** | 97% | 34 | 90% |
| **FieldLensAI** | **36** | **1** | **97%** | **27** | **91%** |

Share of events sent to the planner, by week:

| System | W1 | W2 | W3 | W4 |
|---|---|---|---|---|
| A · exact rules | 63% | 43% | 47% | 62% |
| A+ · rules + normaliser | 37% | 29% | 33% | 62% |
| FieldLensAI (no learning) | 58% | 38% | 60% | 75% |
| **FieldLensAI** | 58% | 29% | 47% | **38%** |

## What the numbers say

1. **Rules alone make confident mistakes.** A+ automates the most but records five false updates:
   - a finish on welding that still had repairs pending;
   - a hydrotest finish on the wrong line (the 107/170 mix-up);
   - a duplicate report that overwrote the real finish date;
   - a QA sign-off before XX-112 was even tested;
   - the extraction miss below.
2. **FieldLensAI's hold-back rules stop all four rule errors.** Each of those items went to the planner instead.
   Auto precision rises from 88% to 97%.
3. **The cost is more review at first**, and **learning pays it back**: by week 4, FieldLensAI sends 38% of
   events to the planner versus 75% without learning, because it learned "HT" = hydrotest from planner answers.
   It ends up close to A+'s automation (36 vs 40) with one false update instead of five.
4. **When it does ask, the answer is usually on screen**: the right activity is in the top 3 for 91% of
   reviewed items, so review is a click, not a search.
5. **A exact-match rules** miss "xx101", "Line 107" and spoken tags, and still make four false updates.

## The one FieldLensAI false update, and what it teaches

**b04**: "Exchanger E-201 set on foundation and levelled."
- The LLM returned **PROGRESS** for "set on foundation" instead of FINISH, so the ledger shows setting as
  in progress on 8-Sep when it had actually finished.
- It also returned a second event quoting "Exchanger E-201 levelled", words that aren't in the report. The
  **verbatim-quote check rejected it**, as designed.

The hold-back rules protect against the system **over-claiming** (a finish that didn't happen, a wrong line,
a wrong date). An extraction that **under-claims** (progress instead of finish) passes through. That's the less
harmful direction: the activity just stays open until the next report closes it. But it is a real limitation,
and the fix would be at the extraction step (a better prompt or model).

## Honest caveats (say these before a judge does)

- **The same team wrote the schedule, the statements, the rules and the answer key.** These numbers show the
  mechanism working, not accuracy on OIL data. The proposal's plan (authors who never see the schedule, OIL
  sample data run blind) is what would make the numbers credible.
- 61 statements is small. One false update in 36 auto-accepts is **97% precision on this set**; it is not
  evidence of a 1% false-update rate. Proving that needs about 300 auto-accepted test items with zero errors.
- The "planner" is simulated from the answer key.
- Extraction results depend on the model. Changing `GROQ_MODEL` re-extracts everything and changes the numbers.

## Point out to the judges

"Rules alone automate more, but five of their updates are wrong, including a hydrotest on the wrong line and a
QA sign-off before testing. FieldLensAI stops all of those, asks a person instead, and learns the site's
language so the asking falls week by week, from 75% to 38% of events by week 4."
