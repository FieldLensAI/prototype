"""FieldLensAI prototype - run with: streamlit run app.py"""
import csv
import io
import os
from datetime import date

import groq
import pandas as pd
import streamlit as st

import bench
from core import DATA, FLAG_TEXT, Project, load_benchmark
from extract import MODEL, ExtractionError, extract_sheet, extract_text, save_cache

DAY = "2026-09-13"
DAY_DIR = DATA / "demo_day"
OUTCOME = {"AUTO": "🟢 Auto-accepted", "REVIEW": "🟠 Planner review", "UNMATCHED": "🟣 Unmatched / possible new work"}

st.set_page_config(page_title="FieldLensAI prototype", layout="wide")
ss = st.session_state


def reset():
    p = Project()
    p.preload(load_benchmark(), before=DAY)      # 7-12 Sep already reconciled
    p.data_date = date.fromisoformat(DAY)
    ss.update(p=p, queue=[], log=[], chat=[], ask=None, day_done=False, bench=None)


if "p" not in ss:
    reset()
p: Project = ss.p
for msg in ss.pop("flash", []):
    st.toast(msg)


def api_errors(fn):
    try:
        return fn()
    except groq.AuthenticationError:
        st.error("Groq rejected the API key. Check GROQ_API_KEY in prototype/.env and restart.")
    except groq.RateLimitError:
        st.error("Groq free-tier rate limit reached. Wait a minute and click again; finished results are cached.")
    except groq.APIConnectionError:
        st.error("Can't reach Groq. Check the connection; cached results still work.")
    except (groq.APIStatusError, ExtractionError) as e:
        st.error(f"Extraction failed: {e}")


def label(aid):
    return f"{aid} · {p.acts[aid]['description']}"


def fmt(x):
    return x.strftime("%d-%b") if x else ""


def handle(dcs, by="auto"):
    """Route one link decision: auto-accept into the ledger, otherwise into the planner queue."""
    ev = dcs["ev"]
    if dcs["outcome"] == "AUTO":
        p.accept(ev, dcs["cands"][0], by=by)
    else:
        ss.queue.append(dcs)
    ss.log.append(dcs)


# ---------------- sidebar ----------------
with st.sidebar:
    st.title("FieldLensAI")
    st.caption("Prototype · SIH26122 · synthetic Unit-3 PR-3 project")
    key_ok = bool(os.environ.get("GROQ_API_KEY"))
    st.write(f"Extraction model: `{MODEL}` on Groq", "✅ key loaded from .env" if key_ok else "⚠️ no GROQ_API_KEY in .env (cached results only)")
    st.write(f"Data date: **{fmt(p.data_date)}** · planner queue: **{len(ss.queue)}**")
    rules = [{"phrase": k, "means": v["step"], "confirmations": v["n"]} for k, v in p.step_alias.items()] + \
            [{"phrase": k, "means": v["tag"], "confirmations": v["n"]} for k, v in p.tag_alias.items()]
    st.subheader("Learned project vocabulary")
    if rules:
        st.dataframe(pd.DataFrame(rules), hide_index=True)
    else:
        st.caption("Nothing learned yet.")
    if st.button("Reset demo"):
        reset()
        st.rerun()

tabs = st.tabs(["1 · Plan", "2 · Reconcile 13-Sep", "3 · Planner review", "4 · Supervisor assistant",
                "5 · Impact & export", "6 · Benchmark"])

# ---------------- 1. plan ----------------
with tabs[0]:
    st.header("Baseline schedule (Primavera export)")
    st.caption("Tags and work steps are derived from activity descriptions at import. 7–12 Sep reports are already reconciled.")
    base = p.cpm(actuals=False)
    rows = []
    for aid, a in p.acts.items():
        stt = p.state(aid)
        rows.append({"Activity": aid, "Description": a["description"], "Work step": a["step"], "Tags": ", ".join(a["tags"]),
                     "Planned": f"{fmt(a['ps'])} → {fmt(a['pf'])}", "Total float (d)": base[aid]["float"],
                     "Actual start": fmt(stt["as"]), "Actual finish": fmt(stt["af"])})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

# ---------------- 2. reconcile ----------------
with tabs[1]:
    st.header("Reconcile one day of field evidence")
    files = {"Contractor DPR": DAY_DIR / f"dpr_{DAY}.txt", "Piping spreadsheet": DAY_DIR / f"piping_{DAY}.csv",
             "Supervisor voice note (transcript)": DAY_DIR / f"voice_{DAY}.txt"}
    cols = st.columns(3)
    for col, (name, path) in zip(cols, files.items()):
        col.markdown(f"**{name}**")
        col.code(path.read_text(), language=None)
    if st.button("Extract and link", type="primary", disabled=ss.day_done):
        def run_day():
            dpr, rej1 = extract_text(files["Contractor DPR"].read_text(), "DPR", DAY, files["Contractor DPR"].name)
            voice, rej2 = extract_text(files["Supervisor voice note (transcript)"].read_text(), "VOICE", DAY, "voice_0913.m4a")
            evs = dpr + extract_sheet(files["Piping spreadsheet"].read_text(), DAY, files["Piping spreadsheet"].name) + voice
            for ev in evs:
                handle(p.link(ev))
            ss.day_done = True
            ss.rejected = rej1 + rej2
        with st.spinner("The LLM is extracting events; core rules are linking them…"):
            api_errors(run_day)
        save_cache()
    if ss.log:
        st.dataframe(pd.DataFrame([{
            "Source": dcs["ev"]["source"], "Evidence (verbatim)": dcs["ev"]["span"],
            "Event": f'{dcs["ev"]["event_type"]} · {dcs["ev"]["date"]}', "Link path": dcs["path"],
            "Activity / candidates": ", ".join(dcs["cands"]) or "–", "Outcome": OUTCOME[dcs["outcome"]],
            "Why held back": "; ".join(FLAG_TEXT[f] for f in dcs["flags"])} for dcs in ss.log]),
            hide_index=True, width="stretch")
        st.caption("Planned work (\"scheduled for Monday\"), manpower and weather lines produce no events: "
                   "unknown stays unknown. Every event keeps the exact words it came from.")
        if ss.get("rejected"):
            st.warning(f"Rejected {len(ss.rejected)} extracted event(s) whose quote was not found in the source: {ss.rejected}")

# ---------------- 3. review ----------------
with tabs[2]:
    st.header("Planner review queue")
    if not ss.queue:
        st.info("Nothing waiting. Items appear here when a hold-back rule fires.")
    for i, dcs in enumerate(list(ss.queue)):
        ev = dcs["ev"]
        with st.container(border=True):
            st.markdown(f'**{OUTCOME[dcs["outcome"]]}** · {ev["source"]} · `{ev.get("ref", "")}`')
            st.markdown(f'> {ev["span"]}')
            for f in dcs["flags"]:
                st.markdown(f"- ⚠️ {FLAG_TEXT[f]}")
            options = dcs["cands"] + [x for x in p.acts if x not in dcs["cands"]]
            pick = st.selectbox("Activity", options, key=f"pick{i}", format_func=lambda x: (
                f"{label(x)}  —  {dcs['why'][x]}" if x in dcs["why"] else label(x)))
            kind = st.selectbox("Event", ["START", "PROGRESS", "FINISH"], key=f"kind{i}",
                                index=["START", "PROGRESS", "FINISH", "HOLD"].index(ev["event_type"]) % 3)
            c1, c2, c3 = st.columns(3)
            if c1.button("Accept", key=f"acc{i}", type="primary"):
                p.accept(ev, pick, by="planner", event_type=kind)
                ss.flash = [f"Learned {note}" for note in p.learn(ev, pick)]
                ss.queue.remove(dcs)
                st.rerun()
            if c2.button("New work (raise in P6)", key=f"new{i}"):
                ss.queue.remove(dcs)
                st.rerun()
            if c3.button("Reject", key=f"rej{i}"):
                ss.queue.remove(dcs)
                st.rerun()

# ---------------- 4. supervisor assistant ----------------
with tabs[3]:
    st.header("Supervisor voice assistant")
    st.caption("Speak (here: type the transcript) an update. The assistant asks back only when a hold-back rule "
               "fires, with choices from the schedule. Answers are evidence; gated checks still go to the planner.")
    for role, text in ss.chat:
        st.chat_message(role).write(text)
    if ss.ask:
        dcs = ss.ask
        cols = st.columns(len(dcs["cands"]) + 1)
        for col, aid in zip(cols, dcs["cands"]):
            if col.button(label(aid), key=f"ask{aid}"):
                ev = dcs["ev"]
                ss.chat.append(("user", f"Taps: {aid}"))
                flags, _ = p.checks(dict(ev, source="SUPERVISOR"), aid)
                if flags:
                    ss.queue.append(dict(dcs, cands=[aid], flags=flags, why={aid: p.explain(ev, aid)}))
                    ss.chat.append(("assistant", f"Noted {aid}. Sent to the planner because: {FLAG_TEXT[flags[0]]}."))
                else:
                    p.accept(ev, aid, by="supervisor")
                    notes = p.learn(ev, aid)
                    ss.chat.append(("assistant", f"Recorded: {label(aid)} — {ev['event_type']} on {ev['date']}."
                                    + (f" (Learned {'; '.join(notes)})" if notes else "")))
                ss.ask = None
                st.rerun()
        if cols[-1].button("Other / not sure"):
            ss.queue.append(dcs)
            ss.chat.append(("assistant", "Sent to the planner with your voice note."))
            ss.ask = None
            st.rerun()
    said = st.chat_input("e.g. hydro test on one-oh-seven done", disabled=bool(ss.ask))
    if said:
        ss.chat.append(("user", said))
        out = api_errors(lambda: extract_text(said, "VOICE", p.data_date.isoformat(), "assistant"))
        if out:
            events, _ = out
            if not events:
                ss.chat.append(("assistant", "I didn't hear a start, progress or finish in that. Nothing recorded."))
            for ev in events:
                dcs = p.link(ev)
                if dcs["outcome"] == "AUTO":
                    p.accept(ev, dcs["cands"][0], by="supervisor")
                    ss.chat.append(("assistant", f"Recorded: {label(dcs['cands'][0])} — {ev['event_type']} on {ev['date']}."))
                elif len(dcs["cands"]) > 1:
                    ss.ask = dcs
                    ss.chat.append(("assistant", f"One detail: {FLAG_TEXT[dcs['flags'][0]].lower()}. Which one was it?"))
                    break
                elif dcs["outcome"] == "UNMATCHED":
                    ss.queue.append(dcs)
                    ss.chat.append(("assistant", "I can't match that to a planned activity, so it's flagged to the planner as possible new work."))
                else:
                    ss.queue.append(dcs)
                    ss.chat.append(("assistant", f"Noted. Sent to the planner because: {FLAG_TEXT[dcs['flags'][0]]}."))
        st.rerun()

# ---------------- 5. impact & export ----------------
with tabs[4]:
    st.header("Verified actuals → schedule impact")
    rows, base, fc = p.impact()
    mc_b, mc_f = base["M-U3-MC"]["ef"], fc["M-U3-MC"]["ef"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Mechanical completion (baseline)", fmt(mc_b))
    c2.metric("Forecast from accepted actuals", fmt(mc_f), f"{(mc_f - mc_b).days:+d} days", delta_color="inverse")
    c3.metric("Accepted actuals this session", sum(e["by"] in ("auto", "planner", "supervisor") for e in p.ledger))
    st.caption("Calendar-day CPM on the imported logic, for illustration. Primavera recalculates with real calendars on import.")
    slipped = [r for r in rows if r["slip_days"] > 0]
    st.subheader("Activities forecast to finish late")
    st.dataframe(pd.DataFrame([{**r, "baseline_finish": fmt(r["baseline_finish"]), "forecast_finish": fmt(r["forecast_finish"])}
                               for r in slipped]), hide_index=True, width="stretch")
    st.subheader("P6 update file (planner signs off, then imports)")
    exp = p.export_rows()
    st.dataframe(pd.DataFrame(exp), hide_index=True, width="stretch")
    if exp:
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(exp[0]))
        w.writeheader()
        w.writerows(exp)
        st.download_button("Download P6 update CSV", buf.getvalue(), file_name=f"fieldlens_p6_update_{DAY}.csv")
    st.subheader("Audit trail")
    st.dataframe(pd.DataFrame([{"Activity": e["activity"], "Event": e["type"], "Date": e["date"], "Decided by": e["by"],
                                "Evidence": " | ".join(e["evidence"])} for e in p.ledger if e["by"] not in ("P6", "history")]),
                 hide_index=True, width="stretch")

# ---------------- 6. benchmark ----------------
with tabs[5]:
    st.header("Benchmark: does FieldLensAI beat plain rules?")
    st.caption("61 synthetic field statements over four weeks (DPR, spreadsheet, voice), each with an answer key. "
               "Items a system does not auto-accept go to a simulated planner who answers from the key. "
               "Caveat: the same team wrote the schedule, the statements and the system, so these numbers show the "
               "mechanism working; they are not a performance claim for OIL data.")
    if st.button("Run benchmark", type="primary"):
        with st.spinner("Extracting (cached after the first run) and replaying four weeks…"):
            out = api_errors(bench.run)
        if out:
            ss.bench = out[0]
    if ss.bench:
        st.dataframe(pd.DataFrame(bench.summary_rows(ss.bench)), hide_index=True, width="stretch")
        st.subheader("% of events sent to the planner, by week")
        st.line_chart(pd.DataFrame(bench.weekly_rows(ss.bench)))
        for name, (s, _, fu, _) in ss.bench.items():
            if fu:
                with st.expander(f"False updates · {name} ({len(fu)})"):
                    st.dataframe(pd.DataFrame(fu, columns=["item", "case", "evidence", "linked to", "event", "date"]),
                                 hide_index=True, width="stretch")
