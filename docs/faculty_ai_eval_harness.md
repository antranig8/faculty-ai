# FacultyAI Eval Harness

## Purpose

Use the eval harness to replay a saved presentation scenario through the backend decision flow without running a live microphone demo.

This is the safest way to tune:

- prepared vs freeform question balance
- timing thresholds
- follow-up behavior
- question-selection quality

## What You Need To Provide

The most useful input on your end is:

1. a `.pptx` deck from the assignment
2. transcript chunks from a rehearsal, in order
3. optionally, the slide number for each chunk if you want manual slide replay

You do **not** need to do a live demo first if you already have:

- a deck
- a rough transcript from practice

Live demos are still useful later, but the eval harness is better for structured tuning.

## Scenario Format

Create a JSON file like this:

```json
{
  "pptxPath": "../path/to/deck.pptx",
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

You can also use `slideOutline` instead of `pptxPath` for quick synthetic tests.

A starter example lives at `backend/eval_scenarios/example_assignment6.json`.

More realistic repo examples:

- `backend/eval_scenarios/faculty_ai_group2_example_scenario.json`
- `backend/eval_scenarios/faculty_ai_group2_profile_scenario.json`

If you want finer timing control, add `chunkDurationsSeconds` with one number per transcript chunk.

## Running It

From the repo root:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.services.eval_runner ..\path\to\scenario.json --out ..\path\to\report.json
```

For the included example:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.services.eval_runner eval_scenarios\example_assignment6.json --out ..\example-report.json
```

## What The Report Contains

For each chunk, the harness records:

- transcript chunk text
- current slide number
- final backend decision
- triggered / queued / resolved feedback
- answer-evaluation result if applicable
- top prepared candidates with scores
- top freeform candidates with scores
- selected candidate according to deterministic hybrid scoring

The harness also simulates slide time during replay. If you do not provide explicit chunk durations, it assumes `4` seconds per chunk.

## Recommended Workflow

1. Start with one real `.pptx`.
2. Add 10-30 transcript chunks from a rehearsal.
3. Use `slideSequence` in manual mode for the clearest replay.
4. Review where the system:
   - asked too early
   - asked the wrong question
   - should have preferred freeform over prepared
   - should have preferred prepared over freeform
5. Tune the runtime only after those patterns repeat across several scenarios.

## Notes

- The harness reuses the real backend decision flow.
- It creates a temporary session and deletes it after replay.
- If Groq is configured, prepared-question generation may still use the LLM during preparation. The live replay itself follows the same runtime rules as the app.
- By default, the replay forces heuristic live runtime selection so results stay stable across runs. Set `"forceHeuristicRuntime": false` in the scenario only when you explicitly want to compare against live LLM arbitration.
