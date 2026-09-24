# 4 · Supervisor assistant: asking back at the moment of reporting

## What you see

A chat. The supervisor speaks an update (in the prototype you type the transcript). The assistant
either records it, asks **one** tap-to-answer question, or passes it to the planner.

## Try it

Type: `HT on line one-oh-one started`

1. The assistant replies: *"One detail: work step not recognised. Which one was it?"*
   with buttons for the three XX-101 activities: Erect, Weld, Hydrotest.
2. Tap **PIP-1832 · Hydrotest Line 6"-XX-101**.
3. It replies *"Recorded: PIP-1832 … START on 2026-09-13. (Learned "ht" → work step HYDROTEST (1/2 confirmations))"*.
   The sidebar now shows the learned rule.

Other things to try:
- `hydro test on one-oh-seven done` → asks which line, because welding on XX-107 isn't finished.
  Tapping XX-170 records it; tapping XX-107 sends it to the planner (out of sequence).
- `manpower 42, weather clear` → "I didn't hear a start, progress or finish in that. Nothing recorded."
- `scaffolding put up near grid 4` → sent to the planner (no tag, and nothing in the schedule matches well).

## What happens in the code (`app.py`, tab 4)

1. The message goes through the same `extract_text()` as a DPR, with source `VOICE`.
2. Each event is linked with `Project.link()`, exactly as in screen 2.
3. Routing:
   - **AUTO** → recorded, read back to the supervisor.
   - **Several candidates** → the assistant asks, using the reason text of the first hold-back rule
     and a button per candidate. **The question and the choices come from the rules and the schedule,
     not from free LLM text.**
   - **Unmatched** → planner queue, labelled as possible new work.
   - **Single candidate but held back** (e.g. gated QA acceptance) → planner queue with the reason.
4. When the supervisor taps a candidate, `Project.checks()` is run again for that activity, with the
   source treated as a confirmed supervisor answer (so the "misheard tag" rule no longer applies).
   - No remaining reasons → recorded as decided by the supervisor, and `learn()` runs.
   - Remaining reasons (out of sequence, gated, conflicting finish) → planner queue.
     **An answer can resolve ambiguity; it can't override a safety check.**
5. **Other / not sure** → planner queue with the original note.

## Why it matters

- The person who knows the answer is asked **while they're still at the work front**, instead of a planner
  phoning them later.
- It meets the problem statement's "low-friction conversational/voice interface" without adding a
  reporting step: the supervisor speaks once, answers at most one tap.
- Every question and answer is evidence in the ledger.

## Limits

- Voice is a typed transcript here. Groq also offers `whisper-large-v3` for speech-to-text, so real audio is
  the next small step.
- English only in the prototype; the proposal names English/Hindi code-mixed speech as a pilot item.

## Point out to the judges

"Two taps, and the planner never sees it. But if the supervisor picks something that breaks the sequence,
it still goes to the planner: the conversation can clear up ambiguity, not bypass the rules."
