"""FieldLensAI core: schedule import, tag grammar, work-step lexicon, linking rules,
activity ledger, learning, CPM impact and P6 export. No LLM in here - everything is
deterministic and auditable."""
import csv
import json
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).parent / "data"
TAG_RE = re.compile(r"\b([A-Z]{1,3})-(\d{2,4}[A-Z]?)\b")
DIGIT_WORDS = {"zero": "0", "oh": "0", "o": "0", "one": "1", "two": "2", "three": "3", "four": "4",
               "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"}
FLAG_TEXT = {
    "IMPLIED_FINISH": "Finish is only implied (e.g. quantity reached 100%), not stated",
    "FUTURE_DATE": "Event date is after the report date",
    "OUT_OF_SEQUENCE": "A predecessor activity has not started/finished yet",
    "CONFLICTS_WITH_RECORDED_FINISH": "Activity already has a different actual finish",
    "AFTER_RECORDED_FINISH": "Progress reported after the recorded finish",
    "GATED": "Gated activity (QA acceptance / milestone): needs planner sign-off",
    "SIMILAR_TAG": "Tag came from speech/handwriting and a near-identical tag exists",
    "SEVERAL_ACTIVITIES": "Several activities match this tag and work step",
    "UNKNOWN_STEP": "Work step not recognised",
    "NO_ACTIVITY_FOR_STEP": "Tag is known but no activity exists for this work step (possible new work)",
    "NO_TAG": "No tag in the report: matched by text search only",
    "PROVISIONAL_RULE": "Relies on a learned rule that is not yet confirmed",
    "ISSUE_REPORTED": "Report mentions a problem (failure, leak, rework, hold, damage)",
}
ISSUE_RE = re.compile(r"\b(fail\w*|leak\w*|reject\w*|rework\w*|repair\w*|damage\w*|stop(ped|page)?|on hold|not ok|punch\w*)\b", re.I)


def d(s):
    return date.fromisoformat(s) if s else None


def spoken_digits(s):
    """'one-oh-seven' -> '107' (only runs of two or more digit words, so 'one' stays a word)."""
    w = "|".join(DIGIT_WORDS)
    return re.sub(rf"\b(?:{w})(?:[\s\-]+(?:{w}))+\b",
                  lambda m: "".join(DIGIT_WORDS[x.lower()] for x in re.split(r"[\s\-]+", m[0])), s, flags=re.I)


class Project:
    def __init__(self, schedule=DATA / "schedule.csv", lexicon=DATA / "lexicon.json"):
        lex = json.loads(Path(lexicon).read_text())
        self.steps = lex["steps"]
        self.gated = tuple(lex["gated_prefixes"])
        self.confirm_n = lex["confirmations_needed"]
        self.acts, self.succs = {}, defaultdict(list)
        self.tag_index = defaultdict(list)
        self.ledger = []
        self.step_alias, self.tag_alias = {}, {}   # learned rules: phrase -> {"step"/"tag", "n"}
        with open(schedule, newline="") as f:
            for row in csv.DictReader(f):
                a = dict(row, ps=d(row["planned_start"]), pf=d(row["planned_finish"]),
                         preds=row["predecessors"].split(), step=self.lexicon_step(row["description"]),
                         tags=[f"{x}-{y}" for x, y in TAG_RE.findall(row["description"])])
                self.acts[a["id"]] = a
                for p in a["preds"]:
                    self.succs[p].append(a["id"])
                for t in a["tags"]:
                    self.tag_index[t].append(a["id"])
                for kind, when in (("START", row["actual_start"]), ("FINISH", row["actual_finish"])):
                    if when:
                        self.ledger.append({"activity": a["id"], "type": kind, "date": d(when), "exact": True,
                                            "qty": None, "evidence": ["P6 status at import"], "by": "P6"})
        self.data_date = max(e["date"] for e in self.ledger)

    # ---------- vocabulary ----------
    def lexicon_step(self, phrase):
        phrase = (phrase or "").lower()
        for step, words in self.steps.items():
            if any(re.search(rf"\b{re.escape(w)}\b", phrase) for w in words):
                return step
        return None

    def step_of(self, phrase):
        """-> (step, 'lexicon' | 'learned' | 'provisional') or (None, None)."""
        step = self.lexicon_step(phrase)
        if step:
            return step, "lexicon"
        phrase = (phrase or "").lower()
        for key, rule in self.step_alias.items():
            if re.search(rf"\b{re.escape(key)}\b", phrase):
                return rule["step"], "learned" if rule["n"] >= self.confirm_n else "provisional"
        return None, None

    def normalize_tag(self, raw):
        s = spoken_digits(raw).upper()
        s = re.sub(r"\bLINE\b", " ", s)
        s = re.sub(r"\d+\s*(\"|''|IN(CH)?)\s*-?", " ", s)          # 24"- size prefix
        m = re.search(r"\b([A-Z]{1,3})\s*-?\s*(\d{2,4}[A-Z]?)\b", s)
        if m and f"{m[1]}-{m[2]}" in self.tag_index:
            return {f"{m[1]}-{m[2]}"}
        m = re.search(r"\b(\d{2,4}[A-Z]?)\b", s)                      # bare "107"
        if m:
            return {t for t in self.tag_index if t.split("-", 1)[1] == m[1]}
        return set()

    def resolve_tags(self, ev):
        tags = set()
        for raw in ev.get("tag_refs", []):
            tags |= self.normalize_tag(raw)
        tags |= {t for t in (f"{x}-{y}" for x, y in TAG_RE.findall(spoken_digits(ev["span"]).upper()))
                 if t in self.tag_index}
        if tags:
            return tags, None
        text = f"{ev.get('object_phrase') or ''} {ev['span']}".lower()
        for key, rule in self.tag_alias.items():
            if re.search(rf"\b{re.escape(key)}\b", text):
                return {rule["tag"]}, "learned" if rule["n"] >= self.confirm_n else "provisional"
        return set(), None

    def similar_tags(self, tag):
        pfx, num = tag.split("-", 1)
        out = []
        for t in self.tag_index:
            p2, n2 = t.split("-", 1)
            if t != tag and p2 == pfx and len(n2) == len(num) and (
                    sorted(n2) == sorted(num) or sum(a != b for a, b in zip(n2, num)) == 1):
                out.append(t)
        return out

    # ---------- ledger ----------
    def state(self, aid):
        evs = [e for e in self.ledger if e["activity"] == aid]
        starts = [e["date"] for e in evs]
        finishes = sorted({e["date"] for e in evs if e["type"] == "FINISH"})
        exact_starts = {e["date"] for e in evs if e["type"] == "START"}
        a_s = min(starts) if starts else None
        qty = max((e["qty"] for e in evs if e["qty"]), default=None, key=lambda q: q[0] / max(q[1], 1))
        return {"as": a_s, "as_exact": a_s in exact_starts, "af": finishes[0] if finishes else None,
                "consistency": "CONFLICT" if len(finishes) > 1 else ("CONSISTENT" if evs else "INSUFFICIENT"),
                "qty": qty, "evidence": [x for e in evs for x in e["evidence"]]}

    def accept(self, ev, aid, by, event_type=None, when=None):
        kind, when = event_type or ev["event_type"], d(when) if isinstance(when, str) else (when or d(ev["date"]))
        ref = f'{ev.get("ref", "?")}: "{ev["span"]}"'
        for e in self.ledger:                      # duplicate report -> one event, two pieces of evidence
            if (e["activity"], e["type"], e["date"]) == (aid, kind, when):
                e["evidence"].append(ref)
                return e
        qty = (ev["qty_done"], ev["qty_total"]) if ev.get("qty_done") is not None and ev.get("qty_total") else None
        e = {"activity": aid, "type": kind, "date": when, "exact": kind == "START", "qty": qty,
             "evidence": [ref], "by": by}
        self.ledger.append(e)
        return e

    # ---------- linking ----------
    def checks(self, ev, aid):
        a, st, kind, when = self.acts[aid], self.state(aid), ev["event_type"], d(ev["date"])
        flags, extra = [], []
        if kind == "FINISH" and not ev.get("completion_explicit"):
            flags.append("IMPLIED_FINISH")
        if when and when > d(ev["report_date"]):
            flags.append("FUTURE_DATE")
        for p in a["preds"]:
            ps = self.state(p)
            if (kind == "FINISH" and not ps["af"]) or (kind in ("START", "PROGRESS") and not ps["as"]):
                flags.append("OUT_OF_SEQUENCE")
                break
        if st["af"] and kind == "FINISH" and when != st["af"]:
            flags.append("CONFLICTS_WITH_RECORDED_FINISH")
        if st["af"] and kind in ("START", "PROGRESS") and when and when > st["af"]:
            flags.append("AFTER_RECORDED_FINISH")
        if kind == "HOLD" or ISSUE_RE.search(ev["span"]):   # bad news always goes to a person
            flags.append("ISSUE_REPORTED")
        if aid.startswith(self.gated) and kind == "FINISH":
            flags.append("GATED")
        if ev["source"] in ("VOICE", "DIARY") and kind == "FINISH":
            for t in a["tags"]:
                for s in self.similar_tags(t):
                    extra += [x for x in self.tag_index[s] if self.acts[x]["step"] == a["step"]]
            if extra:
                flags.append("SIMILAR_TAG")
        return flags, extra

    def ranked(self, ev, step):
        words = lambda s: set(re.findall(r"[a-z0-9]+", s.lower())) - {"the", "of", "for", "at", "on", "and", "to", "a"}
        q = words(ev["span"])
        scored = []
        for aid, a in self.acts.items():
            text = words(a["description"])
            score = len(q & text) / max(len(q | text), 1) + (0.3 if step and a["step"] == step else 0)
            scored.append((round(score, 2), aid))
        scored.sort(reverse=True)
        return [aid for s, aid in scored[:3] if s >= 0.35]   # ponytail: hand-set floor, calibrate on labelled data

    def link(self, ev, policy="FL"):
        """policy: 'A' exact strings, 'A+' normaliser + lexicon, 'FL' full FieldLensAI with hold-back rules."""
        if policy == "A":
            return self._link_exact(ev)
        span, flags = ev["span"], []
        step, step_kind = self.step_of(ev.get("work_phrase") or "")
        tags, tag_kind = self.resolve_tags(ev)
        if "provisional" in (step_kind, tag_kind):
            flags.append("PROVISIONAL_RULE")
        ids = [aid for aid in self.acts if aid.lower() in span.lower()]
        if ids:
            path, cands = "ID", ids[:1]
        elif tags:
            pool = list(dict.fromkeys(aid for t in sorted(tags) for aid in self.tag_index[t]))
            same = [aid for aid in pool if step and self.acts[aid]["step"] == step]
            if len(same) == 1:
                path, cands = "TAG+STEP", same
            elif same:
                path, cands = "TAG+STEP", same
                flags.append("SEVERAL_ACTIVITIES")
            else:
                path, cands = "TAG", pool
                flags.append("NO_ACTIVITY_FOR_STEP" if step else "UNKNOWN_STEP")
        else:
            path, cands = "TEXT", self.ranked(ev, step)
            flags.append("NO_TAG")

        if policy == "A+":   # rules without hold-back: accept any unique match
            ok = path in ("ID", "TAG+STEP") and len(cands) == 1 and "PROVISIONAL_RULE" not in flags
            return self._decision(ev, path, cands, flags, "AUTO" if ok else "MANUAL")

        if len(cands) == 1 and path in ("ID", "TAG+STEP"):
            more, extra = self.checks(ev, cands[0])
            flags += more
            cands += [x for x in extra if x not in cands]
        if not cands or "NO_ACTIVITY_FOR_STEP" in flags:
            outcome = "UNMATCHED"
        else:
            outcome = "REVIEW" if flags else "AUTO"
        return self._decision(ev, path, cands, flags, outcome)

    def _link_exact(self, ev):
        span = ev["span"]
        ids = [aid for aid in self.acts if aid in span]
        pool = ids or list(dict.fromkeys(aid for t in self.tag_index if t in span for aid in self.tag_index[t]))
        if len(pool) > 1:
            pool = [aid for aid in pool if self.acts[aid]["description"].split()[0].lower() in span.lower()]
        return self._decision(ev, "EXACT", pool, [], "AUTO" if len(pool) == 1 else "MANUAL")

    def _decision(self, ev, path, cands, flags, outcome):
        return {"ev": ev, "path": path, "cands": cands, "flags": list(dict.fromkeys(flags)), "outcome": outcome,
                "why": {aid: self.explain(ev, aid) for aid in cands}}

    def explain(self, ev, aid):
        a, st = self.acts[aid], self.state(aid)
        step, _ = self.step_of(ev.get("work_phrase") or "")
        tags, _ = self.resolve_tags(ev)
        preds_ok = all(self.state(p)["af"] for p in a["preds"])
        return (f"tag {'✓' if tags & set(a['tags']) else '✗'} · step {'✓' if step and step == a['step'] else '✗'}"
                f" · predecessors {'finished ✓' if preds_ok else 'not finished ✗'}"
                + (f" · already finished {st['af']}" if st["af"] else ""))

    # ---------- learning ----------
    def learn(self, ev, aid):
        """A planner/supervisor resolution becomes a project vocabulary rule (confirmed after N uses)."""
        a, notes = self.acts[aid], []
        phrase = (ev.get("work_phrase") or "").strip().lower()
        if phrase and a["step"] and not self.lexicon_step(phrase):
            key = next((k for k in self.step_alias if re.search(rf"\b{re.escape(k)}\b", phrase)), phrase)
            rule = self.step_alias.get(key)
            if rule and rule["step"] == a["step"]:
                rule["n"] += 1
            else:
                rule = self.step_alias[key] = {"step": a["step"], "n": 1}
            notes.append(f'"{key}" → work step {a["step"]} ({min(rule["n"], self.confirm_n)}/{self.confirm_n} confirmations)')
        tags, kind = self.resolve_tags(ev)
        obj = (ev.get("object_phrase") or "").strip().lower()
        if obj and a["tags"] and (not tags or kind):
            key = next((k for k in self.tag_alias if re.search(rf"\b{re.escape(k)}\b", obj)), obj)
            rule = self.tag_alias.get(key)
            if rule and rule["tag"] in a["tags"]:
                rule["n"] += 1
            else:
                rule = self.tag_alias[key] = {"tag": a["tags"][0], "n": 1}
            notes.append(f'"{key}" → tag {rule["tag"]} ({min(rule["n"], self.confirm_n)}/{self.confirm_n} confirmations)')
        return notes

    # ---------- schedule impact ----------
    def cpm(self, actuals):
        """Forward pass in calendar days, FS links. With actuals=True, recorded actuals are
        fixed and unstarted work cannot start before the data date."""
        # ponytail: calendar days + FS only; P6 recalculates with real calendars and link types on import
        order, seen = [], set()
        def visit(x):
            if x not in seen:
                seen.add(x)
                for p in self.acts[x]["preds"]:
                    visit(p)
                order.append(x)
        for x in self.acts:
            visit(x)
        es, ef = {}, {}
        for x in order:
            a, dur = self.acts[x], (self.acts[x]["pf"] - self.acts[x]["ps"]).days + 1
            st = self.state(x) if actuals else {"as": None, "af": None}
            if st["af"]:
                es[x], ef[x] = st["as"] or st["af"], st["af"]
                continue
            if st["as"]:
                es[x] = st["as"]
                ef[x] = max(es[x] + timedelta(days=dur - 1), self.data_date)
                continue
            start = max([ef[p] + timedelta(days=1) for p in a["preds"]] or [a["ps"]])
            if actuals:
                start = max(start, self.data_date + timedelta(days=1))
            es[x], ef[x] = start, start + timedelta(days=dur - 1)
        finish = max(ef.values())
        lf = {}
        for x in reversed(order):
            ls_succ = [lf[s] - timedelta(days=(self.acts[s]["pf"] - self.acts[s]["ps"]).days + 1) for s in self.succs[x]]
            lf[x] = min(ls_succ) if ls_succ else finish
        return {x: {"es": es[x], "ef": ef[x], "float": (lf[x] - ef[x]).days} for x in order}

    def impact(self):
        base, fc = self.cpm(False), self.cpm(True)
        rows = [{"activity": x, "description": self.acts[x]["description"], "baseline_finish": base[x]["ef"],
                 "forecast_finish": fc[x]["ef"], "slip_days": (fc[x]["ef"] - base[x]["ef"]).days,
                 "baseline_float": base[x]["float"]} for x in self.acts]
        return rows, base, fc

    def export_rows(self):
        """P6 update file: one row per activity with actuals accepted in FieldLensAI."""
        rows = []
        for aid in self.acts:
            evs = [e for e in self.ledger if e["activity"] == aid and e["by"] not in ("P6", "history")]
            if not evs:
                continue
            st = self.state(aid)
            rows.append({"activity_id": aid,
                         "actual_start": st["as"].isoformat() if st["as"] else "",
                         "start_is_exact": "Y" if st["as_exact"] else "N (on or before)",
                         "actual_finish": st["af"].isoformat() if st["af"] else "",
                         "physical_pct": 100 if st["af"] else (round(100 * st["qty"][0] / st["qty"][1]) if st["qty"] else None),
                         "evidence": " | ".join(st["evidence"])})
        return rows

    def preload(self, items, before):
        """Apply the answer key of benchmark items dated before `before` as already-reconciled history."""
        for it in items:
            if it["date"] < before:
                for g in it["gold"]:
                    if g["a"] != "NEW":
                        ev = {"span": it["text"], "ref": f'{it["source"]} {it["date"]}', "event_type": g["e"],
                              "date": g["d"], "qty_done": None, "qty_total": None}
                        self.accept(ev, g["a"], by="history")
        self.data_date = max(self.data_date, d(before) - timedelta(days=1))


def load_benchmark():
    return [json.loads(line) for line in (DATA / "benchmark.jsonl").read_text().splitlines() if line.strip()]
