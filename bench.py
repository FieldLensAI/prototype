"""Benchmark: replay four weeks of field reports in date order and compare
  A   exact ID / exact tag string rules
  A+  rules with our tag normaliser + work-step lexicon (no hold-back rules)
  FL  FieldLensAI (hold-back rules), without and with project-vocabulary learning
Items a system does not auto-accept go to a simulated planner, who resolves them from the answer key.
Run: python bench.py   (first run calls the LLM once per statement, then everything is cached)"""
from collections import Counter, defaultdict
from datetime import date

from core import Project, load_benchmark
from extract import extract_many

SYSTEMS = [("A · exact rules", "A", False), ("A+ · rules + normaliser", "A+", False),
           ("FieldLensAI (no learning)", "FL", False), ("FieldLensAI", "FL", True)]
START = date(2026, 9, 7)


def compatible(ev, aid, gold):
    for g in gold:
        if g["a"] != aid:
            continue
        same_type = ev["event_type"] == g["e"] or (g["e"] in ("START", "PROGRESS") and ev["event_type"] in ("START", "PROGRESS"))
        same_day = ev["date"] == g["d"] or (g["e"] == "PROGRESS" and ev["event_type"] == "START" and ev["date"] <= g["d"])
        if same_type and same_day:
            return True
    return False


def replay(items, extracted, policy, learning):
    p = Project()
    s, weekly, false_updates = Counter(), defaultdict(Counter), []
    for it in sorted(items, key=lambda x: (x["date"], x["id"])):
        p.data_date = date.fromisoformat(it["date"])
        week = f"W{(p.data_date - START).days // 7 + 1}"
        events, rejected = extracted[it["id"]]
        s["rejected_spans"] += len(rejected)
        if not events and it["gold"]:
            s["missed_by_extraction"] += 1
        for ev in events:
            dcs = p.link(ev, policy)
            s["events"] += 1
            weekly[week]["events"] += 1
            if dcs["outcome"] == "AUTO":
                aid = dcs["cands"][0]
                p.accept(ev, aid, by="auto")
                s["auto"] += 1
                if compatible(ev, aid, it["gold"]):
                    s["auto_ok"] += 1
                else:
                    false_updates.append((it["id"], it["case"], ev["span"], aid, ev["event_type"], ev["date"]))
                continue
            s["to_planner"] += 1
            weekly[week]["to_planner"] += 1
            s["unmatched"] += dcs["outcome"] == "UNMATCHED"
            gold = [g for g in it["gold"] if g["a"] != "NEW"]
            if not gold:
                s["planner_rejected_or_new"] += 1
                continue
            g = next((g for g in gold if g["a"] in dcs["cands"]), gold[0])
            s["resolved"] += 1
            s["top3_hit"] += g["a"] in dcs["cands"][:3]
            p.accept(ev, g["a"], by="planner", event_type=g["e"], when=g["d"])
            if learning:
                p.learn(ev, g["a"])
    return s, weekly, false_updates, p


def run(items=None):
    items = items or load_benchmark()
    extracted = extract_many(items)
    results = {}
    for label, policy, learning in SYSTEMS:
        results[label] = replay(items, extracted, policy, learning)
    return results, extracted


def summary_rows(results):
    rows = []
    for label, (s, weekly, fu, _) in results.items():
        rows.append({"System": label, "Events": s["events"], "Auto-accepted": s["auto"],
                     "False updates": len(fu),
                     "Auto precision": f'{100 * s["auto_ok"] / s["auto"]:.0f}%' if s["auto"] else "–",
                     "Sent to planner": s["to_planner"],
                     "Right activity in top 3": f'{100 * s["top3_hit"] / s["resolved"]:.0f}%' if s["resolved"] else "–"})
    return rows


def weekly_rows(results):
    weeks = sorted({w for _, (s, weekly, _, _) in results.items() for w in weekly})
    return {label: {w: round(100 * weekly[w]["to_planner"] / max(weekly[w]["events"], 1)) for w in weeks}
            for label, (s, weekly, _, _) in results.items()}


if __name__ == "__main__":
    results, extracted = run()
    rows = summary_rows(results)
    cols = list(rows[0])
    print(" | ".join(cols))
    for r in rows:
        print(" | ".join(str(r[c]) for c in cols))
    print("\n% of events sent to the planner, by week:")
    for label, w in weekly_rows(results).items():
        print(f"  {label:28s}", "  ".join(f"{k}:{v:>3}%" for k, v in w.items()))
    for label, (s, _, fu, _) in results.items():
        if fu:
            print(f"\nFalse updates - {label}:")
            for f in fu:
                print("  ", f)
    s = results["FieldLensAI"][0]
    print(f"\nExtraction: {s['missed_by_extraction']} statements with no event extracted, "
          f"{s['rejected_spans']} events rejected (quote not found in the text)")
