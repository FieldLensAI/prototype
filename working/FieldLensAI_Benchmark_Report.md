# FieldLensAI: Benchmark Report

**Question:** does FieldLensAI link field reports to the right Primavera activities more *safely* than plain rules?
**Answer on this benchmark:** yes. It made **1** wrong automatic update against **5** for the best rule-based
system, and after learning the site's vocabulary it sent only **38%** of week-4 events to the planner, against 75% without learning.

> **Read this first.** The schedule, the 61 reports and the answer key were all written by our team. The benchmark
> shows the mechanism works as designed; it is **not** a measurement of accuracy on OIL data. That needs a blind run
> on OIL's anonymised sample data, which is the first step of the proposed pilot.

Run: 24 Sep 2026 · Extraction model: `openai/gpt-oss-120b` via Groq (temperature 0, cached) ·
Code: `prototype/bench.py` · Data: `prototype/data/benchmark.jsonl`

---

## 1. What was tested

**The project:** a synthetic Oil & Gas schedule, "Unit-3 Pipe Rack PR-3", with 30 L5/L6 activities: six pipe lines
(erect → weld → hydrotest), civil foundations, an exchanger, a pump, a cable, a QA test-pack acceptance and the
mechanical-completion milestone. Baseline mechanical completion: 24 Sep.

**The reports:** 61 field statements dated 7 Sep – 2 Oct, as a contractor, a sub-contractor and a supervisor would
write or say them.

| Source | Count | | Difficulty | Count |
|---|---|---|---|---|
| DPR text | 47 | | Easy (ID or clean tag + step) | 23 |
| Discipline spreadsheet row | 7 | | Medium (no dash, "line 107", spoken tag, no tag, synonyms) | 11 |
| Supervisor voice (transcript) | 7 | | Hard (traps, see below) | 15 |
| | | | Learning ("HT" slang, equipment nickname) | 10 |
| | | | Gated (QA acceptance, milestone) | 2 |

**The traps in the "hard" set:**
- a speech mix-up ("one-oh-seven" meant line 170);
- 18/18 joints with "2 joints under repair";
- quantity-only finishes;
- a stale late report;
- a duplicate report with a different date;
- a premature QA sign-off before XX-112 was tested;
- "scheduled for Monday" (not an event);
- a genuine out-of-sequence megger test;
- a spoken tag with a near-identical twin;
- three pieces of new work (temporary support, scaffolding, painting).

**The answer key:** for each statement, the correct activity, event type (START / PROGRESS / FINISH) and date.
It contains 59 expected events plus 4 new-work items, and 2 statements should produce no event at all.

---

## 2. The systems compared

All four systems receive **exactly the same extracted events**. Only the linking and safety logic differs, so the
comparison isolates what the safety layer adds.

| System | How it links | When it acts alone |
|---|---|---|
| **A · exact rules** | Activity ID or exact tag string in the text; if several, the description's first word must appear | Any unique match |
| **A+ · rules + normaliser** | Our full tag normaliser ("xx107", "line 107", "one-oh-seven") and work-step vocabulary | Any unique match; **no hold-back rules** |
| **FieldLensAI (no learning)** | Same linking as A+ | Only if **no hold-back rule** fires |
| **FieldLensAI** | Same, plus learning from planner answers | Same |

A+ deliberately uses *our own* normaliser. It is the strongest rule-based system we could build, not a straw man.

---

## 3. How it was run

`bench.py` replays all 61 statements **in date order** for each system, starting from the same project state
(P6 status as of 6 Sep). For every extracted event:
1. The system links it.
2. **Auto-accepted** → written to the ledger, then compared with the answer key.
3. **Not auto-accepted** → a simulated planner enters the correct answer from the key (as a real planner would).
   With learning on, that answer also teaches vocabulary.

Replaying in order matters: sequence checks depend on what has already been recorded, as on a real project.

**Definitions**

| Metric | Meaning |
|---|---|
| **False update** | An auto-accepted event whose activity, event type or date does not match the answer key |
| Auto precision | Correct auto-accepts ÷ all auto-accepts |
| Sent to planner | Events the system did not accept on its own (review, unmatched or manual) |
| Right activity in top 3 | When reviewed, the correct activity was among the first three candidates shown |

---

## 4. Results

### Headline

| System | Events | Auto-accepted | **False updates** | Auto precision | Sent to planner | Right activity in top 3 |
|---|---|---|---|---|---|---|
| A · exact rules | 63 | 30 | **4** | 87% | 33 | – |
| A+ · rules + normaliser | 63 | 40 | **5** | 88% | 23 | 84% |
| FieldLensAI (no learning) | 63 | 29 | **1** | 97% | 34 | 90% |
| **FieldLensAI** | 63 | **36** | **1** | **97%** | **27** | **91%** |

(63 events from 61 statements: the LLM split a few sentences into two events.)

### By difficulty

| Difficulty | Events | A+: auto / wrong | FieldLensAI: auto / wrong |
|---|---|---|---|
| Easy | 24 | 23 / 1 | 23 / 1 |
| Medium | 12 | 6 / 0 | 5 / 0 |
| **Hard** | 14 | **10 / 4** | **1 / 0** |
| Learning | 11 | 0 / 0 | 7 / 0 |
| Gated | 2 | 1 / 0 | 0 / 0 |

**This is the key table.** On easy and medium reports FieldLensAI automates as much as rules do. On the hard cases,
rules act alone on 10 and get 4 wrong; FieldLensAI acts alone on 1 and gets none wrong. The learning cases are where
FieldLensAI gains automation that rules can never reach.

### Review load by week

| System | W1 (7–13 Sep) | W2 (14–20 Sep) | W3 (21–27 Sep) | W4 (28 Sep – 2 Oct) |
|---|---|---|---|---|
| A · exact rules | 12/19 · 63% | 9/21 · 43% | 7/15 · 47% | 5/8 · 62% |
| A+ · rules + normaliser | 7/19 · 37% | 6/21 · 29% | 5/15 · 33% | 5/8 · 62% |
| FieldLensAI (no learning) | 11/19 · 58% | 8/21 · 38% | 9/15 · 60% | 6/8 · 75% |
| **FieldLensAI** | 11/19 · 58% | 6/21 · 29% | 7/15 · 47% | **3/8 · 38%** |

How to read it:
- **Lower isn't automatically better.** A+ is lowest because it accepts anything unique, including its 5 wrong updates.
- **The two FieldLensAI rows are identical in W1** (nothing learned yet) and split from W2 once planners have
  answered "HT = hydrotest" twice. In W4, 3 of the 6 items the no-learning version sent to the planner were HT reports; with learning, all 3 went through automatically.
- **W4's three remaining items all genuinely need a person:** QA acceptance of TP-07 (gated), the mechanical-completion
  certificate (no tag), and painting on XX-107 (new work).
- **The weeks are small** (W4 has 8 events; one item = 12.5 points). Read the direction, not the decimals.
- **W3 bumps up** because the hardest cases were placed there (genuine out-of-sequence megger test, twin tag 171,
  premature QA, scaffolding), plus two sentence fragments the LLM split off ("coupling fitted", "pressure held 2 hrs").

---

## 5. Every false update, explained

### Rules + normaliser (5)

| # | Report | What it recorded | Why it's wrong | FieldLensAI instead |
|---|---|---|---|---|
| b04 | "Exchanger E-201 set on foundation and levelled." | EQP-0501 PROGRESS | The exchanger was set (FINISH) | Same error (extraction, see below) |
| b10 | "XX-101 · Welding · 18 · 18 · 2 joints under repair" | PIP-1831 FINISH | Repairs pending: not finished | Held: finish only implied + repair mentioned |
| b18 | "hydro test on one-oh-seven done" | PIP-1844 FINISH (XX-107) | It was XX-170; XX-107 welding was only 6/22 | Held: out of sequence + twin tag; XX-170 offered 2nd |
| b40 | "XX-107 welding complete (22/22)" (report of 20 Sep) | PIP-1843 FINISH on 20 Sep | Already finished on 19 Sep; overwrites the date | Held: conflicts with recorded finish |
| b53 | "TP-07 QA acceptance signed." | QA-1845 FINISH | XX-112 not hydrotested yet; sign-off premature | Held: out of sequence + gated |

Exact rules (A) made the same errors on b04, b10, b40 and b53. It missed b18 only because it can't read spoken tags at all.

### FieldLensAI (1)

**b04:** "Exchanger E-201 set on foundation and levelled."
- The LLM classified "set on foundation" as PROGRESS rather than FINISH, so the ledger shows the setting as in progress
  on 8 Sep instead of finished.
- It also produced a second event quoting "Exchanger E-201 levelled", words that are not in the report. The
  **verbatim-quote check rejected it**, as designed.

**What this shows:** the hold-back rules protect against *over-claiming* (a finish that didn't happen, the wrong line,
the wrong date). An *under-claim* like this passes through. It is the less harmful direction, since the activity simply
stays open until the next report, but it is a real limitation. The fix belongs in extraction (prompt or model).

---

## 6. Extraction quality

| Check | Result |
|---|---|
| Statements with an expected event but nothing extracted | **0** |
| Extracted events rejected by the verbatim-quote check | **1** (the invented "Exchanger E-201 levelled") |
| "Scheduled for Monday" (should produce nothing) | No event ✅ |
| "TP-07 QA acceptance signed" (premature) | Extracted correctly; held by rules ✅ |
| Sentences split into two events | Several, e.g. "Line 107 erection ongoing, 3 of 5 spools lifted" |

---

## 7. Limitations

- **Self-authored data.** We wrote the schedule, reports and answers, so we knew the traps. This proves the mechanism,
  not real-world accuracy. The proposal's evaluation plan uses report authors who never see the schedule, plus a blind
  run on OIL data.
- **Small sample.** 1 error in 36 auto-accepts is 97% on *this set*. It cannot demonstrate a 1% false-update rate;
  that would need roughly 300 auto-accepted items with no errors.
- **Simulated planner.** Reviewed items are resolved perfectly from the answer key, so planner mistakes aren't modelled.
- **One schedule, one model.** 30 activities, one extraction model. A different `GROQ_MODEL` re-extracts everything and
  can change the numbers.
- **Not compared:** embedding-only search and LLM-only activity selection (baselines B and C in the proposal).

---

## 8. Reproduce it

```bash
cd ~/Desktop/Projects/FieldLensAI/prototype
uv run python bench.py      # prints the headline table, weekly rates and every false update
```

The extractions are cached in `data/extract_cache.json`, so the run is identical, instant and offline.
The same results appear in the app under **6 · Benchmark**.

---

## Appendix: every statement

✅ correct automatic update · ❌ wrong automatic update · 👤 sent to a person · 🟣 unmatched / possible new work.
A cell with two lines means the LLM extracted two events from that sentence.

| # | Date | Source | Report | Correct answer | Rules + normaliser | FieldLensAI |
|---|---|---|---|---|---|---|
| b01 | 09-07 | DPR | PIP-1836: erection of line 6"-XX-104 started today. | PIP-1836 START | ✅ auto PIP-1836 | ✅ auto PIP-1836 |
| b02 | 09-07 | DPR | Excavation for pipe rack PR-3 grid 9-10 foundations commenced. | CIV-0410 START | 👤 manual | 👤 review (right one in top 3) |
| b03 | 09-08 | XLS | XX-170 \| Welding \| 20 \| 20 \|  | PIP-2209 FINISH | ✅ auto PIP-2209 | 👤 review (right one in top 3) |
| b04 | 09-08 | DPR | Exchanger E-201 set on foundation and levelled. | EQP-0501 FINISH | ❌ **wrong** auto EQP-0501 | ❌ **wrong** auto EQP-0501 |
| b05 | 09-08 | DPR | Line xx101 welding in progress, 12 of 18 joints completed. | PIP-1831 PROGRESS | ✅ auto PIP-1831 | ✅ auto PIP-1831 |
| b06 | 09-09 | VOICE | erection of one-oh-four is finished | PIP-1836 FINISH | ✅ auto PIP-1836 | 👤 review (right one in top 3) |
| b07 | 09-09 | DPR | PR-3 grid 9-10 excavation completed and handed over for concreting. | CIV-0410 FINISH | 👤 manual | 👤 review (right one in top 3) |
| b08 | 09-10 | DPR | XX-107 spool erection started at 08:30. | PIP-1842 START | ✅ auto PIP-1842 | ✅ auto PIP-1842 |
| b09 | 09-10 | DPR | HT of line XX-170 started, test pack TP-03. | PIP-2210 START | 👤 manual | 👤 review (right one in top 3) |
| b10 | 09-10 | XLS | XX-101 \| Welding \| 18 \| 18 \| 2 joints under repair | PIP-1831 PROGRESS | ❌ **wrong** auto PIP-1831 | 👤 review (right one in top 3) |
| b11 | 09-10 | DPR | Grouting of E-201 started. | EQP-0502 START | ✅ auto EQP-0502 | ✅ auto EQP-0502 |
| b12 | 09-11 | DPR | Concrete pour for PR-3 grid 9-10 foundations completed. | CIV-0411 FINISH | 👤 manual | 👤 review (right one in top 3) |
| b13 | 09-11 | VOICE | big exchanger grouting done | EQP-0502 FINISH | 👤 manual | 👤 review (right one in top 3) |
| b14 | 09-12 | DPR | Line 107 erection ongoing, 3 of 5 spools lifted. | PIP-1842 PROGRESS | ✅ auto PIP-1842<br>👤 manual | ✅ auto PIP-1842<br>👤 review |
| b15 | 09-12 | DPR | Temporary support fabricated near PR-3 grid 7. | new work | 👤 manual | 🟣 unmatched |
| b16 | 09-13 | DPR | XX-107 spool erection completed at 17:15. | PIP-1842 FINISH | ✅ auto PIP-1842 | ✅ auto PIP-1842 |
| b17 | 09-13 | XLS | Line 107 \| Welding \| 6 \| 22 \|  | PIP-1843 PROGRESS | ✅ auto PIP-1843 | ✅ auto PIP-1843 |
| b18 | 09-13 | VOICE | hydro test on one-oh-seven done | PIP-2210 FINISH | ❌ **wrong** auto PIP-1844 | 👤 review (right one in top 3) |
| b19 | 09-13 | DPR | Hydrotest of XX-104 scheduled for Monday. | no event | — no event | — no event |
| b20 | 09-14 | DPR | Backfilling at PR-3 grid 9-10 started. | CIV-0412 START | 👤 manual | 👤 review (right one in top 3) |
| b21 | 09-14 | DPR | Welding XX-104 in progress, 9/24 jts. | PIP-1837 PROGRESS | ✅ auto PIP-1837 | ✅ auto PIP-1837 |
| b22 | 09-14 | DPR | Pump P301A set on skid. | EQP-0510 FINISH | ✅ auto EQP-0510 | ✅ auto EQP-0510 |
| b23 | 09-14 | XLS | XX-101 \| Welding \| 18 \| 18 \| repairs cleared | PIP-1831 FINISH | ✅ auto PIP-1831 | 👤 review (right one in top 3) |
| b24 | 09-15 | VOICE | HT on line one-oh-one started | PIP-1832 START | 👤 manual | 👤 review (right one in top 3) |
| b25 | 09-15 | DPR | Erection of XX-112 completed. | PIP-1861 FINISH | ✅ auto PIP-1861 | ✅ auto PIP-1861 |
| b26 | 09-15 | DPR | Backfill complete at grid 9-10, area handed to piping. | CIV-0412 FINISH | 👤 manual | 👤 review (right one in top 3) |
| b27 | 09-16 | DPR | Cable C-4401 laying started from substation. | ELE-0701 START | ✅ auto ELE-0701 | ✅ auto ELE-0701 |
| b28 | 09-16 | DPR | Spool erection for XX-171 started on the rack extension. | PIP-2213 START | ✅ auto PIP-2213 | ✅ auto PIP-2213 |
| b29 | 09-16 | XLS | XX-112 \| Welding \| 4 \| 20 \|  | PIP-1862 PROGRESS | ✅ auto PIP-1862 | ✅ auto PIP-1862 |
| b30 | 09-17 | DPR | HT completed for line XX-101. | PIP-1832 FINISH | 👤 manual | ✅ auto PIP-1832 |
| b31 | 09-17 | VOICE | big exchanger hydro test done | new work | 👤 manual | 🟣 unmatched |
| b32 | 09-17 | DPR | Welding of line XX-107 continuing, 14 of 22 joints. | PIP-1843 PROGRESS | ✅ auto PIP-1843 | ✅ auto PIP-1843 |
| b33 | 09-18 | DPR | C-4401 cable pulling completed. | ELE-0701 FINISH | ✅ auto ELE-0701 | ✅ auto ELE-0701 |
| b34 | 09-18 | DPR | Alignment of pump P-301A started. | EQP-0511 START | ✅ auto EQP-0511 | ✅ auto EQP-0511 |
| b35 | 09-18 | DPR | PIP-1837 XX-104 welding completed today. | PIP-1837 FINISH | ✅ auto PIP-1837 | ✅ auto PIP-1837 |
| b36 | 09-19 | DPR | Termination of cable C-4401 started at MCC end. | ELE-0702 START | ✅ auto ELE-0702 | ✅ auto ELE-0702 |
| b37 | 09-19 | DPR | Line XX-107 welding 22/22 joints completed, NDT clear. | PIP-1843 FINISH | ✅ auto PIP-1843 | ✅ auto PIP-1843 |
| b38 | 09-20 | DPR | XX-104 HT started, TP-07. | PIP-1838 START | 👤 manual | ✅ auto PIP-1838 |
| b39 | 09-20 | DPR | (Late report for 16-Sep) Welding of line XX-107 in progress, 18 of 22 joints. | PIP-1843 PROGRESS | ✅ auto PIP-1843 | ✅ auto PIP-1843 |
| b40 | 09-20 | DPR | XX-107 welding complete (22/22). | PIP-1843 FINISH | ❌ **wrong** auto PIP-1843 | 👤 review (right one in top 3) |
| b41 | 09-21 | DPR | HT of line XX-107 started. | PIP-1844 START | 👤 manual | ✅ auto PIP-1844 |
| b42 | 09-21 | DPR | Megger test on C-4401 done, results OK. | ELE-0703 FINISH | ✅ auto ELE-0703 | 👤 review (right one in top 3) |
| b43 | 09-21 | VOICE | erection on one-seven-one done | PIP-2213 FINISH | ✅ auto PIP-2213 | 👤 review (right one in top 3) |
| b44 | 09-22 | DPR | XX-104 hydrotest passed, line drained. | PIP-1838 FINISH | ✅ auto PIP-1838 | ✅ auto PIP-1838 |
| b45 | 09-22 | DPR | Pump P-301A alignment completed, coupling fitted. | EQP-0511 FINISH | ✅ auto EQP-0511<br>👤 manual | ✅ auto EQP-0511<br>👤 review (right one in top 3) |
| b46 | 09-22 | XLS | XX-112 \| Welding \| 11 \| 20 \|  | PIP-1862 PROGRESS | ✅ auto PIP-1862 | ✅ auto PIP-1862 |
| b47 | 09-23 | DPR | HT done XX-107, pressure held 2 hrs. | PIP-1844 FINISH | 👤 manual<br>👤 manual | ✅ auto PIP-1844<br>🟣 unmatched |
| b48 | 09-23 | DPR | Welding XX-171 started. | PIP-2214 START | ✅ auto PIP-2214 | ✅ auto PIP-2214 |
| b49 | 09-23 | DPR | Scaffolding erected at PR-3 grid 4 for insulation access. | new work | 👤 manual | 👤 review |
| b50 | 09-24 | DPR | Termination of C-4401 completed. | ELE-0702 FINISH | ✅ auto ELE-0702 | ✅ auto ELE-0702 |
| b51 | 09-25 | XLS | XX-112 \| Welding \| 20 \| 20 \|  | PIP-1862 FINISH | ✅ auto PIP-1862 | 👤 review (right one in top 3) |
| b52 | 09-25 | DPR | XX-171 welding 50% done. | PIP-2214 PROGRESS | ✅ auto PIP-2214 | ✅ auto PIP-2214 |
| b53 | 09-26 | DPR | TP-07 QA acceptance signed. | no event | ❌ **wrong** auto QA-1845 | 👤 review |
| b54 | 09-28 | DPR | HT of XX-112 started. | PIP-1863 START | 👤 manual | ✅ auto PIP-1863 |
| b55 | 09-29 | VOICE | HT on one-one-two completed | PIP-1863 FINISH | 👤 manual | ✅ auto PIP-1863 |
| b56 | 09-29 | DPR | Welding XX-171 completed. | PIP-2214 FINISH | ✅ auto PIP-2214 | ✅ auto PIP-2214 |
| b57 | 09-30 | DPR | XX-171 HT started. | PIP-2215 START | 👤 manual | ✅ auto PIP-2215 |
| b58 | 09-30 | DPR | TP-07 QA acceptance completed and signed by OIL QA. | QA-1845 FINISH | ✅ auto QA-1845 | 👤 review (right one in top 3) |
| b59 | 10-01 | DPR | XX-171 hydrotest completed. | PIP-2215 FINISH | ✅ auto PIP-2215 | ✅ auto PIP-2215 |
| b60 | 10-01 | DPR | Mechanical completion certificate for PR-3 issued. | M-U3-MC FINISH | 👤 manual | 👤 review (right one in top 3) |
| b61 | 10-02 | DPR | Painting touch-up on XX-107 started. | new work | 👤 manual | 👤 review |
