# How Faculty-AI Thinks

Faculty-AI is meant to behave like a thoughtful faculty member in the audience, not a rubric checker reading off preset questions. It listens to the current slide, notices what is still vague or unsupported, and asks one useful question at the right moment.

The rubric matters, but as structure: it tells Faculty-AI which concerns are worth noticing. It is not the whole personality of the system.

## The Pipeline

```text
browser mic ──audio──▶ FastAPI proxy ──▶ Deepgram STT
                                              │ transcript
                                              ▼
 slides + prepared questions + rubric ──▶ decision engine ──▶ faculty question
                                              │                     │
                                     (heuristic or Groq)      Deepgram TTS ──▶ speaker
```

1. **Before the run.** The backend parses the uploaded `.pptx`, classifies each slide, and prepares a small set of slide-specific concerns using the professor's rubric and assignment context. Results are cached by deck content and context.
2. **During the run.** Audio streams through the backend to Deepgram. Final transcript chunks are sent to the decision engine along with the current slide, recent transcript, and conversation history.
3. **Each chunk.** The engine decides on one move: ask, queue for later, evaluate an answer, follow up, or stay quiet.
4. **When it asks.** The question appears in the feedback drawer and is spoken aloud with Deepgram TTS.

## The Core Question

On every transcript chunk, Faculty-AI asks itself:

> What is the most useful professional faculty move right now?

The possible moves are:

| Move | When it fits |
|---|---|
| Prepared question | A concern prepared for this slide is now clearly relevant |
| Freeform question | The presenter said something specific that deserves scrutiny and no prepared concern fits as well |
| Follow-up | The last answer only partly addressed the concern |
| Wait / queue | The question is good but the timing is wrong |
| Skip | The topic is already covered or the moment doesn't warrant it |

## How a Decision Is Made

1. **Which slide are we on?** Inferred from the transcript, with manual override in the UI.
2. **What kind of slide is it?** Each category behaves differently:
   - `team_takeaway`: conservative; waits for real reasoning, not a list of themes
   - `individual_lesson`: more willing to ask one direct question about application or judgment
   - `cip_course_feedback`: pushes vague recommendations toward something concrete
   - `cip_team_feedback`: probes for missing feedback or collaboration detail
3. **Has the presenter said enough yet?** Faculty-AI does not interrupt right as a slide starts or while the speaker is still framing the topic.
4. **What is still missing?** It looks for gaps: unclear justification, unsupported claims, missing examples, missing application, missing tradeoffs.
5. **Prepared or freeform?** It ranks the best prepared concern against the best freeform question for this exact moment and picks the stronger one.
6. **Is now a good time?** Cooldowns and a short answer window keep interruptions spaced out. Each slide can receive one initial question and, after a partial answer, one follow-up once the timing allows it.
7. **Has this been asked already?** Similar questions and covered topics are deduplicated.

## Evaluating Answers

After a question is asked, the presenter's next words are judged as:

- **strong**: the concern is resolved automatically
- **partial**: Faculty-AI may ask one follow-up, never more
- **weak**: the question stays open in the drawer

The presenter can also resolve or reopen any question manually.

## Student Profile Memory

Faculty-AI keeps a deliberately small memory per student. On an individual reflection slide, if a student says something like "I'm a Computer Science major" or mentions an interest (AI, robotics, startups, research), it stores that against the slide's owner.

Later questions on that student's slide can then be tailored slightly:

> *As a Computer Science major,* can you give one example of how "good enough" in industry differs from doing low-quality work?

It only personalizes when it is confident the context belongs to the current speaker, so shared group slides are left generic.

## Deterministic + LLM Hybrid

Most of the control logic is deterministic, which keeps the system stable, cheap, and easy to tune: slide classification, timing gates, deduplication, scoring, and answer evaluation.

When `FACULTY_AI_LLM_PROVIDER=groq` is set, an LLM is added where judgment helps most:

- generating prepared questions from the deck
- arbitrating when several moves are plausible
- writing a better freeform question for the live moment

Without an LLM, each of these uses the heuristic path. The browser also has a basic rephrase fallback when Groq is unavailable.

## Guardrails

Faculty-AI is designed to:

- interrupt only for a specific, academic reason
- ask one strong question rather than several weak ones
- stay grounded in the current slide and transcript
- remain skeptical but fair, not hostile

It does **not** try to grade students live, act as a general chatbot, do speaker diarization, or turn every question into a technical defense.
