# Eval Harness

The eval harness replays a saved presentation through the real backend decision flow, with no microphone or live demo needed. Use it to tune timing thresholds, follow-up behavior, and how prepared and freeform questions are balanced.

## Scenario Format

A scenario is a JSON file with a deck and the transcript chunks to replay, in order:

```json
{
  "pptxPath": "deck.pptx",
  "slideMode": "manual",
  "slideSequence": [2, 2, 2, 3, 3],
  "defaultChunkDurationSeconds": 4,
  "transcriptChunks": [
    "Our team takeaway from ENES 104 was that professionalism mattered a lot.",
    "We learned that communication was important.",
    "That changed how we approached this presentation.",
    "On my slide I talk about the speaker series.",
    "It changed how I think about engineering practice."
  ]
}
```

| Field | Purpose |
|---|---|
| `pptxPath` | Deck to parse, relative to the scenario file |
| `slideOutline` | Plain-text alternative to `pptxPath` for quick synthetic tests |
| `slideMode` | `manual` uses `slideSequence`; `auto` infers slides from the transcript |
| `slideSequence` | Slide number for each transcript chunk |
| `defaultChunkDurationSeconds` | Simulated seconds per chunk (default `4`) |
| `chunkDurationsSeconds` | Optional per-chunk durations for finer timing control |
| `forceHeuristicRuntime` | Keep live selection deterministic so runs are reproducible (default `true`) |

## Running It

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.services.eval_runner eval_scenarios\sample-rehearsal.json --out ..\example-report.json
```

The report is printed to stdout and, with `--out`, written to a file. Set `FACULTY_AI_LLM_PROVIDER=heuristic` in the replay terminal to keep both preparation and decision-making offline.

## Included Examples

Both sample rehearsal scenarios use the same anonymized PowerPoint as the main README. [Sample rehearsal deck](sample-rehearsal.pptx)

- Replay the engineering course reflection. [Standard scenario](../backend/eval_scenarios/sample-rehearsal.json)
- Replay a variation that includes a student's major and interests. [Profile scenario](../backend/eval_scenarios/sample-rehearsal-profile.json)
- Inspect the saved output from the standard scenario. [Sample report](../backend/eval_scenarios/sample-rehearsal-report.json)
- Run a short rehearsal from an inline slide outline. [Six-chunk example](../backend/eval_scenarios/example_assignment6.json)

## What the Report Contains

For each transcript chunk:

- the chunk text and current slide
- the final decision: triggered, queued, resolved, or quiet
- the answer evaluation, if the chunk answered a question
- the top prepared and freeform candidates with their scores
- the candidate the hybrid scorer selected

The `facultyAINotes` field records the expected behavior from the scenario. The report rows show what happened during the replay.

## Tuning Workflow

1. Start with one real deck and 10–30 transcript chunks from a rehearsal.
2. Use `manual` slide mode for the clearest replay.
3. Look for places where Faculty-AI asked too early, asked the wrong question, or picked a prepared question when a freeform one would have been better (or the reverse).
4. Change the runtime only once a pattern repeats across several scenarios.

## Notes

- Each replay creates a temporary session and deletes it afterwards.
- If Groq is configured, question *preparation* may still use the LLM. Set `"forceHeuristicRuntime": false` only when you want to compare against live LLM arbitration.
