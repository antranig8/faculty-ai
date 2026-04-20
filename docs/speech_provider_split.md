# Speech Provider Split

## Decision

Use a dedicated speech provider for transcription and optional voice output. Keep OpenAI focused on faculty reasoning.

Preferred candidates:

- Deepgram
- AssemblyAI

## Responsibilities

### Speech Provider

- live microphone transcription
- interim transcript events
- final transcript chunks
- optional text-to-speech later
- confidence and timing metadata if available

### OpenAI / LLM

- rubric-aware question preparation
- slide-aware reasoning
- deciding whether a concern is answered or unanswered
- generating concise faculty remarks
- duplicate and generic-question avoidance

## Backend Boundary

Create a provider interface so the app can switch between Deepgram and AssemblyAI without changing the faculty reasoning pipeline.

```text
Live audio -> Speech provider -> transcript chunks -> FacultyAI backend -> OpenAI reasoning -> alert
```

## MVP Rule

Do not block the current demo on live speech. Keep fake transcript mode while adding provider boundaries.

That gives the class demo a stable fallback if live transcription fails.
