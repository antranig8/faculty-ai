# FacultyAI Roadmap

## Goal

Move FacultyAI from a solid slide-aware live feedback demo into a more believable, stateful faculty evaluator for ENES 104 Assignment 6.

The right direction is not "ask more questions." The right direction is:

- ask fewer, stronger questions
- ask them at better times
- remember what already happened
- judge whether the presenter actually answered

## Where The Project Already Stands

FacultyAI already has a meaningful baseline:

- professor-owned rubric and assignment framing
- `.pptx` upload and slide text extraction
- prepared slide-aware faculty question generation
- cached prepared questions
- live transcript ingestion through Deepgram
- current slide tracking with auto inference plus manual override
- slide category and lightweight slide author inference
- selective triggering instead of constant interruption
- queued-question state and delivery
- explicit answer evaluation with one follow-up max
- timing-aware release of queued questions
- stronger deterministic ranking among multiple valid prepared concerns
- dedupe and cooldown logic
- one-question-per-slide enforcement
- feedback resolution and reopen flow
- SQLite persistence for sessions and prepared-question cache

This means the project is no longer a generic live question generator. It already behaves like a constrained rubric-aware questioning system.

## What Is Partially Implemented

These areas exist, but are still shallow or incomplete:

### Slide Awareness

Implemented:

- current slide can be inferred from transcript
- current slide can be manually overridden
- prepared questions are scoped to slide number

Still weak:

- slide category is first-class but still heuristic
- slide ownership is lightweight and should not become the main product axis
- timing is better than before, but still backend-threshold based rather than fully observability-driven

### Presentation Memory

Implemented:

- asked question ids/messages are tracked
- asked slide numbers are tracked
- duplicate questions are suppressed
- recent feedback history affects runtime decisions

Still weak:

- topic coverage is still heuristic rather than explicit rubric memory
- queue state exists, but the UI does not yet expose candidate competition or why one concern lost
- unresolved concerns and follow-ups exist, but post-session summarization is still minimal

### Answer Handling

Implemented:

- unresolved feedback can auto-resolve from transcript evidence
- presenter can manually mark feedback addressed or reopen it

Still weak:

- answer quality is exposed, but still heuristic rather than LLM-graded
- follow-up handling exists, but the post-session reporting of answer quality is still limited
- there is not yet a higher-level view of which concerns remained unresolved across the whole rehearsal

## Immediate Next Priority

The next implementation pass should focus on broader question-quality and observability rather than deeper student-specific behavior.

### 1. Better Selection Observability

The runtime now ranks multiple valid concerns, but the UI still does not explain much about that competition.

Needed next:

- surface why the winning concern beat the alternatives
- show candidate ranking or at least the top losing concern in debug mode
- make trigger reasons easier to audit after the rehearsal

### 2. Better Results / Session Review

The live session is stronger than the after-session experience.

Useful next additions:

- per-session summary of all asked questions
- which answers were weak / partial / strong
- unresolved concerns at the end of the rehearsal
- rough rubric-area coverage across the full presentation

### 3. Better Provider / Model Observability

It should be clearer when the app used:

- deterministic logic
- prepared-question ranking only
- live LLM arbitration
- fallback heuristics after provider issues

## Next After That

These are the next logical improvements after queueing and answer evaluation.

### Better Timing Rules

Current timing is better than before because queueing and slide-time thresholds now exist. The next improvement is not "more timing features" by default, but better introspection and tuning.

Useful next work:

```ts
type TimingState = {
  slideStartTime: number;
  lastQuestionTime?: number;
  lastTranscriptTime?: number;
  silenceDurationMs?: number;
};
```

This should stay pragmatic. The product does not need perfect live interruption. It needs believable restraint.

## Later

These are valid, but should wait until the runtime is more stateful:

- adaptive question difficulty
- executive-style pressure questions beyond the prepared-question framework
- PowerPoint or Google Slides integrations
- OCR or screenshot-based slide detection
- richer multi-session analytics
- deeper student-specific targeting policies

## Product Guardrails

As the system becomes more capable, it should keep these constraints:

- prefer prepared slide-aware concerns over freestyle questioning
- do not ask repeated questions
- do not over-focus on deep technical architecture unless the slide calls for it
- do not interrupt immediately on slide arrival
- ask at most one follow-up unless the user explicitly expands the design later
- optimize for believable academic scrutiny, not maximum aggressiveness

## Recommended Implementation Order

### Phase 1

- expose stronger runtime reasons in the UI
- make question-selection ranking more inspectable
- improve post-session review

### Phase 2

- improve rubric-coverage reporting
- improve provider / model observability
- tune timing thresholds from real session behavior

### Phase 3

- add richer analytics and review tools
- consider adaptive difficulty only if the simpler system is already trustworthy
- consider deeper integrations only if they materially improve rehearsal quality

## Acceptance Criteria For The Next Pass

- the UI explains more clearly why a specific concern won
- a finished session can be reviewed outside the live drawer
- provider/model path selection is easier to inspect during failures or demos
- the runtime remains tied to rubric + slide context + transcript evidence

## Final Direction

Build FacultyAI as a:

**stateful, rubric-aware, timing-controlled faculty evaluator**
