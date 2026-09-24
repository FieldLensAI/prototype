"""Turn field evidence into structured events.

Free text (DPR lines, voice transcripts) -> an LLM on Groq, which must copy tags and work-step
words verbatim and quote the exact source phrase. Interpretation (which tag, which work step,
which activity) stays in core.py. Spreadsheets are parsed deterministically.

Settings come from prototype/.env (GROQ_API_KEY, GROQ_MODEL). Every LLM result is cached in
data/extract_cache.json, so after one online run the demo works offline and gives identical results."""
import csv
import hashlib
import io
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import groq
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
if os.environ.get("GROQ_API_KEY", "").startswith("paste-"):   # placeholder still in .env
    del os.environ["GROQ_API_KEY"]
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
CACHE_PATH = Path(__file__).parent / "data" / "extract_cache.json"
EVENT_TYPES = ("START", "PROGRESS", "FINISH", "HOLD")

SYSTEM = """You extract construction execution events from field progress reports (DPRs, supervisor voice \
transcripts, site diaries) for an Oil & Gas project-controls system.

Return one event per piece of work that the text says STARTED, PROGRESSED, FINISHED or was put ON HOLD. \
Split sentences that report two pieces of work into two events. Include ALL physical work, including \
temporary works, supports, scaffolding and anything that may not be in the schedule: the downstream system \
decides whether it is planned work.

Rules:
- span: copy the exact words from the report that state the event (verbatim, no paraphrase).
- tag_refs: equipment/line/cable/test-pack identifiers exactly as written, including spoken numbers \
("one-oh-seven") and bare numbers ("line 107"). Do not correct, complete or reformat them.
- object_phrase: the thing worked on, as written ("XX-107 spool", "big exchanger", "PR-3 grid 9-10 foundations").
- work_phrase: only the words naming the work step, as written ("erection", "welding", "HT", "grouting"), \
without status words. null if no work step is named.
- event_type: START, PROGRESS, FINISH or HOLD.
- completion_explicit: true only if the text states the work is complete/done/finished/passed/signed.
- qty_done / qty_total: numbers if a quantity is stated, else null.
- date: YYYY-MM-DD only if the text states or implies a specific day different from the report date \
("yesterday", "on 16-Sep", "late report for 16-Sep"), resolved against the report date. Otherwise null.
- Planned, scheduled or future work is not an event. Manpower, weather and safety lines are not events.
- Never invent tags, dates, quantities or completion that the text does not state.

Respond with JSON only, in exactly this shape:
{"events": [{"span": "...", "tag_refs": ["..."], "object_phrase": "...", "work_phrase": "..." or null,
  "event_type": "START" | "PROGRESS" | "FINISH" | "HOLD", "completion_explicit": true or false,
  "qty_done": number or null, "qty_total": number or null, "date": "YYYY-MM-DD" or null}]}
Return {"events": []} if the text reports no execution events."""

VERSION = hashlib.sha1((MODEL + SYSTEM).encode()).hexdigest()[:8]

_lock = threading.Lock()
_cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
_client = None


class ExtractionError(Exception):
    pass


def _key(text, source, report_date):
    return hashlib.sha1(f"{VERSION}|{source}|{report_date}|{text}".encode()).hexdigest()


def save_cache():
    with _lock:
        CACHE_PATH.write_text(json.dumps(_cache, indent=1, sort_keys=True))


def _clean(e):
    """JSON mode guarantees valid JSON, not our schema, so check every field before core.py sees it."""
    num = lambda x: x if isinstance(x, (int, float)) and not isinstance(x, bool) else None
    date = e.get("date")
    return {"span": str(e.get("span") or ""),
            "tag_refs": [str(t) for t in e.get("tag_refs") or [] if t],
            "object_phrase": str(e.get("object_phrase") or ""),
            "work_phrase": str(e["work_phrase"]) if e.get("work_phrase") else None,
            "event_type": str(e.get("event_type", "")).upper(),
            "completion_explicit": e.get("completion_explicit") is True,
            "qty_done": num(e.get("qty_done")), "qty_total": num(e.get("qty_total")),
            "date": date if isinstance(date, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) else None}


def _create(text, source, report_date):
    return _client.chat.completions.create(
        model=MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": f"Report date: {report_date}\nSource: {source}\n\n<report>\n{text}\n</report>"}],
    )


def _call_llm(text, source, report_date):
    global _client
    if _client is None:
        if not os.environ.get("GROQ_API_KEY"):
            raise ExtractionError("No Groq API key. Put GROQ_API_KEY in prototype/.env and restart (cached results still work).")
        _client = groq.Groq(max_retries=2)
    for _ in range(30):
        try:
            resp = _create(text, source, report_date)
            break
        except groq.RateLimitError as e:   # free tier: ~8k tokens/min. Wait as long as Groq asks, then retry.
            m = re.search(r"try again in ([\d.]+)s", str(e))
            time.sleep(min(float(m[1]) if m else 10, 60) + 0.5)
    else:
        raise ExtractionError("Groq rate limit did not clear after repeated waits; try again later")
    choice = resp.choices[0]
    if choice.finish_reason == "length":
        raise ExtractionError("Extraction was cut off (output too long)")
    try:
        raw = json.loads(choice.message.content)["events"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ExtractionError(f"Model returned malformed JSON: {e}") from e
    return [c for c in (_clean(e) for e in raw if isinstance(e, dict)) if c["span"] and c["event_type"] in EVENT_TYPES]


def _norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def extract_text(text, source, report_date, ref):
    """-> (events, rejected_spans). Events whose span is not found verbatim in the text are rejected."""
    k = _key(text, source, report_date)
    if k not in _cache:
        raw = _call_llm(text, source, report_date)
        with _lock:
            _cache[k] = raw
        save_cache()   # keep every finished call, even if a later one fails
    events, rejected = [], []
    for e in _cache[k]:
        if _norm(e["span"]) not in _norm(text):
            rejected.append(e["span"])
            continue
        events.append(dict(e, date=e["date"] or report_date, date_stated=bool(e["date"]),
                           report_date=report_date, source=source, ref=ref))
    return events, rejected


def extract_sheet(csv_text, report_date, ref):
    """Discipline spreadsheet (Line, Activity, Done, Total, Remarks) -> events, no LLM."""
    events = []
    for row in csv.DictReader(io.StringIO(csv_text.strip())):
        done, total = float(row["Done"]), float(row["Total"])
        events.append({"span": " | ".join(row[k] for k in ("Line", "Activity", "Done", "Total", "Remarks")),
                       "tag_refs": [row["Line"]], "object_phrase": row["Line"], "work_phrase": row["Activity"],
                       "event_type": "FINISH" if done >= total else ("PROGRESS" if done else "START"),
                       "completion_explicit": False,   # a quantity reaching 100% is not a stated completion
                       "qty_done": done, "qty_total": total, "date": report_date, "date_stated": False,
                       "report_date": report_date, "source": "XLS", "ref": ref})
    return events


def extract_item(item):
    """A benchmark statement -> events."""
    if item["source"] == "XLS":
        line, act, done, total, remarks = [x.strip() for x in item["text"].split("|")]
        sheet = f"Line,Activity,Done,Total,Remarks\n{line},{act},{done},{total},{remarks}"
        evs = extract_sheet(sheet, item["date"], f'XLS {item["date"]}')
        for e in evs:
            e["span"] = item["text"]
        return evs, []
    return extract_text(item["text"], item["source"], item["date"], f'{item["source"]} {item["date"]} ({item["id"]})')


def extract_many(items, workers=1):   # free-tier token limits: one call at a time
    """Extract a batch in parallel; returns {item id: (events, rejected)}."""
    def safe(item):
        try:
            return extract_item(item)
        except ExtractionError as e:   # one bad statement shouldn't stop the benchmark
            return [], [f"extraction error: {e}"]
    with ThreadPoolExecutor(workers) as pool:
        results = dict(zip((it["id"] for it in items), pool.map(safe, items)))
    save_cache()
    return results
