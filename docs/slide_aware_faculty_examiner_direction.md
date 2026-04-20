# Slide-Aware Faculty Examiner Direction

## Product Direction

FacultyAI should act like a live stand-in faculty member, not a general presentation helper.

The system listens to a student presenting and selectively raises faculty-style questions, critiques, or remarks when the student reaches a rubric-relevant issue, skips a justification, makes an unsupported claim, or describes a slide in a way that leaves an important gap.

The goal is not constant coaching. The goal is believable academic scrutiny.

## Core Idea

The strongest direction is:

```text
Rubric + slide context + live transcript = decide whether a faculty remark is warranted now
```

Keyword matching alone is not enough. A keyword can help identify relevance, but the system should only trigger if the student has not already answered the underlying faculty concern.

## Inputs

### Professor Configuration

The professor owns the rubric and evaluation expectations. Students should not enter or edit these values during presentation mode.

Professor-owned inputs include:

- rubric criteria
- course expectations
- grading priorities
- preferred faculty question style
- optional assignment description
- optional known constraints

### Student Upload

The student should only upload the presentation file, ideally `.pptx` first.

Student-owned inputs should be limited to:

- presentation upload
- presentation start/pause
- current slide advancement if automatic tracking is not available

The app should extract slide text from the uploaded deck and prepare faculty questions from that extracted content.

### Live Transcript

The transcript provider decides what the student said. OpenAI or another LLM should not be responsible for raw transcription.

The app should compare the current spoken chunk against:

- current slide content
- prepared questions for that slide
- rubric criteria
- recent transcript
- recent feedback history

## Speech Provider Split

Speech and reasoning should be separate.

### Speech-to-Text

Use a dedicated speech provider such as Deepgram or AssemblyAI for live transcription.

Responsibilities:

- microphone stream handling
- live transcript events
- interim and final transcript text
- speaker audio capture
- optional confidence scores

### Text-to-Speech

If voice output is added later, use Deepgram or AssemblyAI voice features, or another dedicated TTS provider.

Voice output is not required for the first presentation-safe version. The first version should keep the visible `!` alert and feedback drawer.

### OpenAI / LLM

OpenAI should be the brains only.

Responsibilities:

- prepare faculty questions from professor rubric and extracted slide text
- judge whether a transcript chunk answers or misses a prepared concern
- generate concise faculty remarks
- avoid generic or repeated questions

OpenAI should not be used for browser microphone capture, speech streaming, or TTS playback.

## Prepared Faculty Questions

Before the presentation starts, the backend should analyze the rubric and slide outline and prepare likely questions per slide.

Each prepared question should include:

```json
{
  "id": "slide-3-q1",
  "slideNumber": 3,
  "rubricCategory": "technical justification",
  "type": "question",
  "priority": "high",
  "question": "Why did you choose FastAPI instead of handling this with Next.js API routes?",
  "listenFor": ["FastAPI", "backend", "API", "architecture"],
  "missingIfAbsent": ["comparison to alternatives", "reason for backend separation"]
}
```

## Runtime Triggering

During presentation mode:

1. The app knows the current slide.
2. The app listens to transcript chunks.
3. The backend checks whether the transcript relates to prepared questions.
4. The backend asks whether the student already answered the concern.
5. If the concern is relevant and unanswered, the app raises a visible `!` alert.

## Trigger Types

### Slide Arrival Trigger

When a slide becomes active, the app has prepared questions ready, but it does not show them immediately.

### Speech Match Trigger

When the student says something related to a prepared question, the app can trigger if the underlying issue is still unanswered.

Example:

```text
Student says: "We use FastAPI for the backend."
Question: "Why did you choose FastAPI instead of Next.js API routes?"
Trigger condition: no reason or tradeoff has been explained.
```

### Rubric Gap Trigger

If the slide is ending and the student still has not addressed a rubric-relevant concern, the app may ask a question before the next slide.

## MVP Implementation Path

### Phase 1: Role-Split Slide-Aware Demo

- Add professor configuration storage.
- Keep rubric setup out of student presentation mode.
- Add student `.pptx` upload.
- Extract slide text from the uploaded presentation.
- Generate deterministic prepared questions from extracted slide text and professor rubric.
- Add current slide tracking in the frontend.
- Send current slide and prepared questions into `/analyze-chunk`.
- Prefer prepared questions over generic live feedback.

### Phase 2: Better Question Generation

- Replace deterministic question preparation with an LLM.
- Keep the same response shape.
- Cache prepared questions so demos are stable.

### Phase 3: Better Presentation Upload

- Improve `.pptx` parsing.
- Add PDF support if needed.
- Display slides inside the app or provide manual slide tracking.

- Add Deepgram or AssemblyAI live transcription.
- Chunk final transcript events every few seconds.
- Trigger slide-aware feedback during live speech.

## Product Rule

FacultyAI should only interrupt when it has a specific academic reason.

Good:

```text
What evidence shows that this is a real problem for your target users?
```

Good:

```text
Why was FastAPI the right backend choice instead of a simpler Next.js API route?
```

Bad:

```text
Can you elaborate?
```

Bad:

```text
This is interesting. Tell me more.
```

## Current Build Target

For now, build a web app where the student:

1. Uploads a `.pptx`.
2. Clicks prepare.
3. Presents through a demo transcript flow.
4. Manually advances slides.
5. Gets faculty-style alerts based on current slide, professor rubric, and spoken transcript.

Professor setup should happen outside the student presentation flow.
