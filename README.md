# FieldLensAI prototype (SIH26122)

A small working slice of the proposal: messy field reports in, evidence-backed L5/L6 actuals out.

```
P6 schedule ─► tag index + work-step index
DPR / voice ─► LLM (Groq) extracts events (verbatim quotes) ─┐
Spreadsheet ─► deterministic parser ─────────────────────┼─► link: ID → tag + work step → text search
                                                         │   hold-back rules → AUTO / REVIEW / UNMATCHED
                                                         └─► ledger → CPM impact → P6 update CSV
```

## Run

1. Get a free Groq API key at https://console.groq.com/keys
2. Open `prototype/.env` and replace `paste-your-groq-key-here` with your key (no quotes, no spaces).
3. In Terminal:

```bash
cd ~/Desktop/Projects/FieldLensAI/prototype
uv run python test_core.py        # self-check, no API needed
uv run streamlit run app.py       # the demo (opens http://localhost:8501)
uv run python bench.py            # optional: benchmark table in the terminal
```

Every LLM result is cached in `data/extract_cache.json`. After one online run the demo works offline with
identical results; keep that file for presentation day. `.env` is git-ignored so the key is never committed.

## Deploy on Streamlit Community Cloud

1. share.streamlit.io → **Create app** → repo `FieldLensAI/prototype`, branch `main`, main file `app.py`.
2. **Advanced settings** → Python 3.12, and paste into **Secrets**:
   ```toml
   GROQ_API_KEY = "gsk_..."
   GROQ_MODEL = "openai/gpt-oss-120b"
   ```
   Streamlit exposes these as environment variables, which is what the code reads (`.env` stays local and is never pushed).
3. **Deploy.** The committed `data/extract_cache.json` means the demo day and benchmark run without calling Groq;
   only new text typed into the supervisor assistant uses the API.

## Demo script (≈5 min)

1. **Plan**: 30 activities; tags and work steps derived from descriptions; PIP-1842 has zero float.
2. **Reconcile 13-Sep**: one click. Erection of XX-107 auto-accepted; the Excel row becomes 6/22 progress;
   the voice note "hydro test on one-oh-seven done" is held back (welding on XX-107 isn't finished and XX-170
   is a near-identical tag); the temporary support is flagged as possible new work; "scheduled for Monday" produces no event.
3. **Planner review**: pick PIP-2210 (XX-170) for the voice note, accept.
4. **Supervisor assistant**: type `HT on line one-oh-one started` → it asks which activity → tap PIP-1832 → it learns "HT".
5. **Impact & export**: milestone forecast vs baseline, P6 update CSV, audit trail with the exact source words.
6. **Benchmark**: exact rules vs rules + normaliser vs FieldLensAI, false updates and the weekly review-rate curve.

## Documentation

Step-by-step explanation of every screen: [`working/`](working/README.md).

## Files

| File | What it does |
|---|---|
| `core.py` | Schedule import, tag grammar, work-step lexicon, linking + hold-back rules, ledger, learning, CPM, export |
| `extract.py` | LLM extraction via Groq (JSON mode + field validation, verbatim-quote check, disk cache); spreadsheet parser |
| `bench.py` | Four-week replay of 61 labelled statements for each system |
| `app.py` | Streamlit demo |
| `.env` | `GROQ_API_KEY` and `GROQ_MODEL`, loaded automatically |
| `data/` | Synthetic schedule, lexicon, demo-day reports, benchmark with answer key |

## Honest limits

- The schedule, benchmark statements and rules were written by the same team: the benchmark shows the mechanism, not OIL performance.
- The text-search path never auto-accepts, because its scores are not calibrated.
- CPM uses calendar days and FS links only; Primavera recalculates properly on import.
- Voice is a typed transcript; plugging in Whisper speech-to-text is the next step.
- Not built: embedding and LLM-only baselines (B, C in the proposal), photos, direct P6 integration.
