"""Self-check for the deterministic core (no API needed): python test_core.py"""
from core import Project, load_benchmark


def ev(span, event_type, tags=(), step=None, source="DPR", date="2026-09-13", explicit=True, obj=None, qty=(None, None)):
    return {"span": span, "tag_refs": list(tags), "work_phrase": step, "object_phrase": obj, "event_type": event_type,
            "completion_explicit": explicit, "qty_done": qty[0], "qty_total": qty[1], "date": date,
            "report_date": "2026-09-13", "source": source, "ref": "test"}


def project_on_13_sep():
    p = Project()
    p.preload(load_benchmark(), before="2026-09-13")
    return p


def test_baseline_plan_is_consistent():
    p = Project()
    base = p.cpm(actuals=False)
    for aid, a in p.acts.items():
        assert base[aid]["es"] == a["ps"] and base[aid]["ef"] == a["pf"], aid
    assert base["PIP-1842"]["float"] == 0 and base["M-U3-MC"]["ef"].isoformat() == "2026-09-24"


def test_worked_example():
    p = project_on_13_sep()
    # 1. DPR: tag + work step picks PIP-1842 out of the three XX-107 activities
    d1 = p.link(ev("XX-107 spool erection completed at 17:15.", "FINISH", ["XX-107"], "erection"))
    assert d1["outcome"] == "AUTO" and d1["cands"] == ["PIP-1842"], d1
    p.accept(d1["ev"], "PIP-1842", by="auto")
    # 2. Excel: "Line 107" + welding -> progress on PIP-1843
    d2 = p.link(ev("Line 107 | Welding | 6 | 22 | ", "PROGRESS", ["Line 107"], "Welding", "XLS", explicit=False, qty=(6, 22)))
    assert d2["outcome"] == "AUTO" and d2["cands"] == ["PIP-1843"], d2
    p.accept(d2["ev"], "PIP-1843", by="auto")
    # 3. Voice: "one-oh-seven" hydrotest is out of sequence and XX-170 is a near-identical tag -> review
    d3 = p.link(ev("hydro test on one-oh-seven done", "FINISH", ["one-oh-seven"], "hydro test", "VOICE"))
    assert d3["outcome"] == "REVIEW" and {"OUT_OF_SEQUENCE", "SIMILAR_TAG"} <= set(d3["flags"]), d3
    assert d3["cands"][:2] == ["PIP-1844", "PIP-2210"], d3["cands"]
    # 4. No tag, no matching activity -> unmatched (possible new work), never silently dropped
    d4 = p.link(ev("Temporary support fabricated near PR-3 grid 7.", "FINISH", step="fabricated"))
    assert d4["outcome"] == "UNMATCHED", d4
    # impact: +1 day on a zero-float chain moves the milestone
    rows, base, fc = p.impact()
    assert fc["PIP-1842"]["ef"].isoformat() == "2026-09-13"
    # export file carries evidence
    row = next(r for r in p.export_rows() if r["activity_id"] == "PIP-1842")
    assert row["actual_finish"] == "2026-09-13" and "17:15" in row["evidence"]


def test_baselines_behave_like_rules():
    p = project_on_13_sep()
    voice = ev("hydro test on one-oh-seven done", "FINISH", ["one-oh-seven"], "hydro test", "VOICE")
    assert p.link(voice, "A")["outcome"] == "MANUAL"                         # exact strings miss spoken tags
    assert p.link(voice, "A+")["cands"] == ["PIP-1844"] and p.link(voice, "A+")["outcome"] == "AUTO"  # the false update


def test_learning_needs_confirmation():
    p = Project()
    ht = ev("HT of line XX-170 started", "START", ["XX-170"], "HT", date="2026-09-10")
    assert p.link(ht)["flags"] == ["UNKNOWN_STEP"]
    p.learn(ht, "PIP-2210")                                                  # planner resolves once
    assert "PROVISIONAL_RULE" in p.link(ht)["flags"]
    p.learn(ht, "PIP-2210")                                                  # confirmed a second time
    assert "PROVISIONAL_RULE" not in p.link(ht)["flags"] and p.step_of("HT") == ("HYDROTEST", "learned")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
