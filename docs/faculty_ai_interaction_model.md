# FacultyAI Interaction Model

## Direction

FacultyAI should not behave like a rubric-triggered checker that occasionally asks questions.

It should behave like a believable faculty or executive audience member that:

- listens to the presentation in context
- stays professional and productive
- uses assignment framing and rubric as structure
- chooses the most useful interaction at the current moment

The rubric is scaffolding, not the whole brain.

## Core Shift

The old shape of the runtime was closer to:

```text
prepared concern -> transcript match -> ask that concern
```

The target shape is:

```text
presentation context + slide + transcript + assignment framing + conversation history
-> choose the best faculty move
```

## Interaction Types

The runtime should think in terms of interaction types rather than only question ids.

Current target interaction set:

- `prepared_question`
- `freeform_question`
- `follow_up`
- `wait`
- `skip`

Prepared questions are still important. They are strong anchors because they keep the system grounded in the assignment and slide context. But they should not be the only legal move.

## What "Free Mind" Means Here

The goal is not unrestricted improvisation.

The goal is a system that can ask a better natural question when the live moment makes that question more useful than the prepared list.

That means FacultyAI should be able to:

- use a prepared concern when it fits well
- ask a concise freeform clarification when the presenter makes an unclear claim
- ask a challenge question when a tradeoff or judgment deserves scrutiny
- ask a follow-up when an answer is partial
- wait when the presenter is still setting context

## Guardrails

Freedom should come from professional interaction policy, not from loss of discipline.

The system should still:

- stay relevant to the current slide and recent transcript
- avoid filler and repeated questions
- avoid thesis-defense behavior unless the presentation itself warrants it
- avoid over-focusing on technical architecture unless the slide makes it central
- remain academically serious but not hostile

## Architectural Layers

### 1. Context Layer

Inputs:

- current slide
- slide category and optional author
- recent transcript
- transcript evidence
- recent feedback history
- assignment framing
- rubric background

### 2. Interaction Policy Layer

Responsibility:

- decide whether the best move is a prepared question, freeform question, follow-up, wait, or skip

This layer should answer:

```text
What is the most useful professional faculty move right now?
```

### 3. Wording Layer

Responsibility:

- produce the actual faculty wording once the interaction type is chosen

Prepared questions may be lightly tightened.
Freeform questions should stay concise and professional.

## Deterministic + LLM Hybrid

The intended runtime is hybrid, not purely heuristic and not purely LLM-driven.

### Deterministic Layer

Use deterministic scoring for:

- prepared concerns that are clearly timely
- obvious unsupported claims
- obvious missing evidence
- obvious missing tradeoff justification

### LLM Layer

Use the LLM for arbitration when:

- several plausible interactions exist
- a better freeform question may be more natural than the prepared list
- timing and context require a more human professional judgment

## What This Means For Prepared Questions

Prepared questions should remain in the system because they:

- preserve assignment grounding
- make the runtime stable
- reduce generic questioning
- keep costs and drift under control

But prepared questions should become:

- anchors
- evidence of likely concerns
- one source of candidate interactions

They should not remain:

- the only meaningful question source

## Immediate Implementation Goal

The immediate runtime goal is:

```text
best faculty move
= best prepared question OR best freeform question OR follow-up OR wait/skip
```

This should apply both:

- in the LLM arbitration path
- in the deterministic path

## Non-Goals

This direction does not mean:

- turning FacultyAI into a generic chatbot
- removing assignment structure
- replacing all prepared questions with freeform generation
- making student-specific targeting the main product axis

## Product Test

If the system is working correctly, it should feel less like:

- a scripted rubric checker

and more like:

- a thoughtful, disciplined faculty audience member
