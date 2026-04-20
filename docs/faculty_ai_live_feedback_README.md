# Faculty AI Live Feedback — Build README

## Project Summary

Build a presentation assistant that listens to a student presenting live, analyzes what they are saying in near real time, and surfaces faculty-style feedback as on-screen alerts.

The first version should **not** interrupt with voice.  
It should:

- listen to the presenter through the microphone
- transcribe speech live
- analyze transcript chunks with AI
- decide whether feedback is worth surfacing
- show a visible **"!"** on screen when feedback is triggered
- let the user open the feedback card to see:
  - a question
  - a critique
  - a suggestion
  - a clarification request

This is the safest and strongest MVP.

---

## Goal

Create a demo where a student can present a project and an on-screen **Faculty AI** reacts with relevant questions or critiques based on what the student has actually said.

The output should feel like:

- “How are you measuring that outcome?”
- “You mentioned personalization. What exactly is being personalized?”
- “Why did you choose this architecture over an alternative?”
- “That claim sounds important, but it needs evidence.”

The system should **not** spam, repeat itself, or ask generic filler questions.

---

## MVP Definition

### Required
- live microphone input
- live transcript
- transcript chunking every few seconds
- project context loaded beforehand
- AI analysis of transcript chunks
- structured feedback generation
- on-screen alert system with feedback history
- cooldown logic to avoid too many alerts

### Not required for v1
- voice output
- avatar
- realistic interruption timing
- slide parsing automation
- full grading system
- multi-user support
- polished auth

---

## Core User Flow

1. User uploads or pastes project context
   - project title
   - summary
   - stack
   - goals
   - optional rubric
   - optional slide notes

2. User enters presentation mode

3. App starts listening and transcribing

4. Every 5–10 seconds:
   - collect a transcript chunk
   - send recent transcript + project context + recent feedback history to backend

5. Backend decides:
   - no feedback
   - or generate one useful feedback item

6. Frontend shows:
   - a floating **"!"**
   - feedback panel or drawer
   - feedback type and message

7. Presenter can respond or keep going

---

## Recommended Stack

### Frontend
- Next.js
- React
- TypeScript
- Tailwind CSS

### Backend
Choose one:

#### Option A
- FastAPI (Python)

#### Option B
- Node.js + Express or Next API routes

For this project, **FastAPI** is a strong choice if you want fast prototyping and clean AI orchestration.

### AI / LLM
- OpenAI API or equivalent LLM provider

### Speech-to-Text
Two approaches:

#### Easier MVP
- browser speech recognition if supported

#### Better / more controllable
- streaming speech-to-text provider
- or backend transcription pipeline

For the first demo, browser-based speech recognition can be enough if reliability is acceptable.

### Storage
- local JSON or lightweight DB for MVP
- optional: Supabase later

---

## Best Architecture for V1

## High-Level Architecture

### Frontend
Responsible for:
- microphone capture
- live transcript display
- session controls
- faculty alert UI
- feedback history

### Backend
Responsible for:
- receiving transcript chunks
- combining chunks with project context
- deciding if feedback should trigger
- generating structured faculty-style feedback
- preventing duplicate / low-quality alerts

### AI Layer
Responsible for:
- section awareness
- identifying vague claims
- spotting missing justification
- asking project-aware questions
- producing short, specific outputs

---

## Suggested File Structure

```text
faculty-ai-live-feedback/
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx
│   │   ├── present/
│   │   │   └── page.tsx
│   │   └── api/
│   ├── components/
│   │   ├── TranscriptPanel.tsx
│   │   ├── FacultyAlert.tsx
│   │   ├── FeedbackDrawer.tsx
│   │   ├── SessionControls.tsx
│   │   └── ProjectContextForm.tsx
│   ├── lib/
│   │   ├── speech.ts
│   │   ├── api.ts
│   │   └── types.ts
│   └── styles/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── routes/
│   │   │   ├── analyze.py
│   │   │   └── session.py
│   │   ├── services/
│   │   │   ├── llm_service.py
│   │   │   ├── feedback_engine.py
│   │   │   ├── cooldown.py
│   │   │   └── section_tracker.py
│   │   ├── models/
│   │   │   ├── request_models.py
│   │   │   └── response_models.py
│   │   └── utils/
│   │       └── prompt_templates.py
│   └── requirements.txt
│
├── docs/
│   ├── prompts.md
│   ├── demo-script.md
│   └── rubric-ideas.md
│
├── .env.example
├── README.md
└── package.json
```

---

## Core Data Models

### Project Context
```json
{
  "title": "CodeMaxx",
  "summary": "AI-powered platform for structured programming learning",
  "stack": ["React", "FastAPI", "Supabase"],
  "goals": [
    "generate personalized learning paths",
    "create quizzes and lessons",
    "track progression"
  ],
  "rubric": [
    "clarity",
    "technical justification",
    "impact",
    "evaluation"
  ]
}
```

### Transcript Chunk
```json
{
  "sessionId": "abc123",
  "timestampStart": 120,
  "timestampEnd": 130,
  "text": "Our platform improves learning efficiency by giving users structured guidance and adaptive content."
}
```

### Feedback Response
```json
{
  "trigger": true,
  "type": "question",
  "priority": "medium",
  "section": "solution",
  "message": "How are you defining or measuring learning efficiency here?",
  "reason": "A strong claim was made without a metric or evaluation detail."
}
```

---

## Faculty Feedback Categories

Use only a few feedback types for clarity.

### Recommended types
- `question`
- `critique`
- `suggestion`
- `clarification`
- `praise` (use rarely)

### Examples

#### Question
- “How does your system handle edge cases?”
- “What evidence supports that claim?”

#### Critique
- “This explanation is clear conceptually, but the technical tradeoff is missing.”

#### Suggestion
- “Consider naming one alternative you rejected and why.”

#### Clarification
- “You mentioned personalization. What exactly changes per user?”

#### Praise
- “Strong problem framing. The motivation is clear.”
Do not overuse praise or it will stop feeling like faculty feedback.

---

## Feedback Trigger Logic

This matters a lot.

The app should **not** generate feedback for every chunk.

### Trigger only if:
- a strong claim is made without evidence
- a design choice is mentioned without justification
- a vague phrase appears
- a metric is implied but not explained
- a new important section starts
- a missing tradeoff is obvious
- a very strong explanation deserves positive reinforcement

### Do not trigger if:
- the transcript is too short
- the content is repetitive
- a similar question was already asked recently
- the speaker is clearly mid-sentence
- the generated feedback is generic

---

## Cooldown Rules

These rules are required.

### Suggested defaults
- minimum 15–20 seconds between alerts
- maximum 1 active alert at a time
- maximum 5–7 alerts per presentation
- block near-duplicate questions
- avoid same feedback type 3 times in a row

Without this, the product will feel broken.

---

## Section Tracking

The app should try to infer what part of the presentation the student is in.

### Useful sections
- introduction
- problem
- solution
- architecture
- demo
- evaluation
- future work
- conclusion

This can be inferred from transcript content.

Examples:
- “The problem we noticed...” → `problem`
- “Our architecture uses...” → `architecture`
- “To evaluate this...” → `evaluation`

This helps the feedback be much smarter.

---

## Backend API Design

### POST `/session/start`
Starts a new presentation session.

#### Request
```json
{
  "projectContext": {
    "title": "CodeMaxx",
    "summary": "AI-powered platform for structured programming learning"
  }
}
```

#### Response
```json
{
  "sessionId": "abc123"
}
```

---

### POST `/analyze-chunk`
Send transcript chunk for AI analysis.

#### Request
```json
{
  "sessionId": "abc123",
  "transcriptChunk": "Our system improves learning efficiency by adapting the content path to the user.",
  "recentTranscript": [
    "We built an AI-powered learning platform.",
    "Users enter a topic and goal."
  ],
  "recentFeedback": [
    "What metric defines user improvement here?"
  ],
  "projectContext": {
    "title": "CodeMaxx",
    "summary": "AI-powered platform for structured programming learning"
  }
}
```

#### Response
```json
{
  "trigger": true,
  "feedback": {
    "type": "clarification",
    "priority": "medium",
    "section": "solution",
    "message": "What specific parts of the path are adapted per user?",
    "reason": "The concept of adaptation was mentioned but not explained."
  }
}
```

---

### GET `/session/{id}/feedback`
Returns feedback history.

---

## Frontend Components

### 1. ProjectContextForm
Collect:
- title
- summary
- stack
- goals
- rubric
- optional notes

### 2. TranscriptPanel
Show:
- live transcript
- maybe highlight recent chunk

### 3. FacultyAlert
A floating UI with:
- exclamation mark
- subtle animation
- badge count if multiple items are queued

### 4. FeedbackDrawer
Shows:
- latest feedback
- type
- time
- history

### 5. SessionControls
Buttons:
- start
- pause
- stop
- clear transcript
- manual test alert

---

## UI Notes

Keep the UI clean.

### Layout idea
- left: live transcript
- right: faculty feedback panel
- top: session state
- floating: “!” alert

### Colors
Keep them simple:
- question = blue-ish
- critique = orange / red-ish
- suggestion = yellow-ish
- praise = green-ish

No need for a complex dashboard in v1.

---

## Prompt Design

This is one of the most important parts.

Your prompt should force the model to behave like a faculty member who is:
- brief
- specific
- grounded in the project
- slightly critical
- not overly friendly
- not generic

### System Prompt Draft

```text
You are simulating a faculty reviewer listening to a student present a technical project.

Your job is to decide whether the student's latest spoken content deserves feedback.

Only trigger feedback if there is a meaningful reason:
- vague claim
- missing evidence
- unexplained metric
- unexamined tradeoff
- unsupported technical decision
- need for clarification
- especially strong explanation worth brief praise

Avoid generic questions.
Avoid repeating earlier feedback.
Avoid interrupting too often.
Keep feedback short and specific.

Return strict JSON with:
- trigger: boolean
- type: question | critique | suggestion | clarification | praise
- priority: low | medium | high
- section: introduction | problem | solution | architecture | demo | evaluation | future_work | conclusion | unknown
- message: short faculty-style feedback
- reason: short explanation for why this feedback was triggered
```

### User Prompt Template

```text
Project context:
{project_context}

Recent transcript:
{recent_transcript}

Latest transcript chunk:
{latest_chunk}

Recent feedback history:
{recent_feedback}

Decide whether feedback should be triggered now.
If not, return trigger=false.
If yes, produce one strong feedback item only.
```

---

## Example Feedback Outputs

### Good
```json
{
  "trigger": true,
  "type": "question",
  "priority": "medium",
  "section": "evaluation",
  "message": "What metric are you using to support the claim that users improve faster?",
  "reason": "A performance claim was made without evaluation details."
}
```

### Good
```json
{
  "trigger": true,
  "type": "critique",
  "priority": "medium",
  "section": "architecture",
  "message": "The stack is named clearly, but the reason for choosing it over alternatives is still missing.",
  "reason": "A technical choice was described without justification."
}
```

### Bad
```json
{
  "trigger": true,
  "type": "question",
  "priority": "low",
  "section": "unknown",
  "message": "Can you elaborate?",
  "reason": "More detail may help."
}
```

That last one is too generic and should be filtered out.

---

## Quality Filters

Before sending feedback to frontend, run filters:

### Reject if:
- message length is too short and generic
- message is nearly identical to recent feedback
- reason is weak
- chunk does not contain enough signal
- cooldown is active

### Optional score-based filtering
You can score:
- specificity
- novelty
- usefulness

Only show feedback above a threshold.

---

## Suggested Build Order

## Phase 1 — Static Demo
Build a fake demo first.

### Goal
Prove the concept without live audio.

### Steps
1. Create UI
2. Add hardcoded transcript chunks
3. Send chunks to backend manually
4. Show generated faculty feedback
5. Add alert icon and feedback drawer

If this feels good, move on.

---

## Phase 2 — Live Transcript MVP
### Goal
Make it work with real speaking.

### Steps
1. Add microphone input
2. Add live transcription
3. Chunk transcript every 5–10 seconds
4. Send chunks to backend
5. Show alerts
6. Add cooldown logic

---

## Phase 3 — Better Context and Smarter Feedback
### Goal
Improve relevance.

### Steps
1. Add project context form
2. Add rubric-aware prompts
3. Add section tracking
4. Add duplicate detection
5. Improve UI clarity

---

## Phase 4 — Demo Polish
### Goal
Make it presentation-ready.

### Steps
1. Add session history
2. Add manual alert test button
3. Add fallback canned outputs
4. Improve styling
5. Create demo script

---

## Suggested First Sprint

If starting from zero, do this first:

### Day 1
- set up frontend
- set up backend
- define request/response schema
- create project context form
- build feedback drawer
- build fake “!” alert

### Day 2
- connect backend to LLM
- send manual transcript chunks
- render real AI feedback

### Day 3
- add speech transcription
- chunk transcript automatically
- add cooldown and feedback history

### Day 4
- test with your actual project presentation
- improve prompt
- reduce bad feedback
- add fallback demo mode

---

## Demo Mode Fallback

This is extremely important for class.

Build a **demo mode** where:
- transcript chunks are preloaded
- faculty feedback is pre-generated or cached
- alerts trigger on button press or timeline

That way, if live audio fails, the demo still works.

Do not rely 100% on live APIs during a class presentation.

---

## Common Failure Points

### 1. Too much feedback
Fix with cooldown, max alerts, and stronger trigger threshold.

### 2. Generic questions
Fix with better prompting and stricter output filtering.

### 3. Slow response time
Fix by:
- smaller transcript chunks
- lighter prompts
- less context
- cached project summary

### 4. Repetitive questions
Fix with recent feedback history and duplicate checks.

### 5. Wrong section detection
Fix by allowing `unknown` section and using rules before AI.

---

## Nice Add-Ons Later

After MVP works, you can add:

- voice output
- faculty persona selection
  - skeptical professor
  - technical reviewer
  - supportive mentor
- rubric scoring
- end-of-presentation summary
- slide-aware feedback
- session replay with transcript timeline
- export feedback report

Do not build these first.

---

## Example Demo Script

### Intro
“I built a prototype that simulates live faculty feedback during a student presentation.”

### While presenting
Speak normally about the project.

### When alert appears
Click the **“!”** and say:
“This is the type of question a faculty member might ask in response to what I just said.”

### Then answer it live
That interaction is the most impressive part.

---

## Success Criteria

The MVP is successful if it can:
- listen live or semi-live
- generate relevant feedback at least a few times
- avoid spamming
- feel grounded in the project
- make the audience immediately understand the concept

It does **not** need to be perfect.

---

## Recommended Initial Prompt Rules

Use these rules inside your logic:

- minimum transcript chunk length: 20–30 words
- minimum cooldown: 15 seconds
- no duplicate message within last 5 feedback items
- one feedback item max per analysis cycle
- no praise unless truly earned
- prioritize question or clarification over praise

---

## Possible Tech Decisions

### Easiest end-to-end stack
- Next.js frontend
- FastAPI backend
- OpenAI API
- browser speech recognition
- local in-memory session state

### Better but more work
- Next.js frontend
- FastAPI backend
- streaming STT provider
- Supabase for session persistence
- websocket updates

Start with the easiest end-to-end version.

---

## Immediate Next Steps

1. Create repo
2. Build frontend shell
3. Create backend `/analyze-chunk`
4. Hardcode project context
5. Send sample transcript chunk
6. Render first faculty feedback card
7. Add floating “!”
8. Only then add live microphone transcription

---

## Notes for Another Chat

If continuing this project in another chat, say:

> I am building a presentation tool called Faculty AI Live Feedback.  
> It listens to a student presenting, transcribes speech in real time, analyzes transcript chunks, and surfaces faculty-style questions or critiques as on-screen “!” alerts.  
> I want to start with a Next.js frontend and FastAPI backend.  
> Please help me implement the MVP in this order:
> 1. UI shell
> 2. backend analysis endpoint
> 3. fake transcript demo
> 4. live transcription
> 5. cooldown logic
> 6. prompt improvement

---

## Final Build Principle

Do not try to make it impressive by making it complicated.

Make it impressive by making it:
- clear
- controlled
- relevant
- demo-safe
- believable
