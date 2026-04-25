# How FacultyAI Thinks

This document explains how the current FacultyAI runtime listens, decides, and responds during a presentation.

## The Big Idea

FacultyAI is not supposed to behave like a rubric checker that blurts out preset questions.

It is supposed to behave more like a thoughtful faculty or executive audience member who:

- listens to the current slide
- pays attention to what the student is actually saying
- notices what still feels vague, unsupported, or underdeveloped
- asks one useful question at the right time

The rubric still matters, but mainly as structure.

It helps FacultyAI know what kinds of concerns are worth paying attention to.
It is not meant to be the entire personality of the system.

## What FacultyAI Pays Attention To

At runtime, the system mainly works from:

- the current slide
- the slide category
- the recent transcript
- previously asked questions
- whether a question is still waiting to be answered
- whether the current moment is too early, too crowded, or too repetitive

It also has a lightweight memory for:

- who has already been asked questions
- which student likely owns an individual reflection slide
- small profile clues such as:
  - major
  - discipline
  - interests

Example:

- if a student says `I am a Computer Science major`
- and that happens on their individual reflection slide
- FacultyAI can remember that and use it later to make a question more specific

## The Main Question FacultyAI Asks Itself

The core runtime question is:

`What is the most useful professional faculty move right now?`

That move could be:

- ask a prepared question
- ask a freeform question
- ask a follow-up
- wait
- skip

## How It Decides What To Ask

### 1. It identifies the kind of slide

FacultyAI does not treat every slide the same.

Different slide categories have different behavior:

- `team_takeaway`
  - more conservative
  - waits for real reasoning, not just a list of themes
- `individual_lesson`
  - more willing to ask one direct question
  - especially if the student has not explained application or judgment
- `cip_course_feedback`
  - looks for vague recommendations
  - tries to force a more concrete improvement
- `cip_team_feedback`
  - looks for missing feedback details, collaboration details, or team-learning details
- closing moments
  - may allow one final synthesis question

### 2. It checks whether the presenter is still setting context

FacultyAI should not interrupt too early.

So it often waits if:

- the slide has just started
- the speaker is still framing the topic
- there is not enough spoken context yet

This is why timing gates exist.

They are there to make the question feel deliberate rather than random.

### 3. It looks for what is still missing

FacultyAI tries to notice gaps such as:

- unclear justification
- vague recommendations
- unsupported claims
- missing application
- missing prioritization
- missing example
- missing tradeoff

It is not just looking for keywords.
It is trying to notice whether the student has actually done enough with the idea they introduced.

### 4. It compares prepared vs freeform questions

Prepared questions are useful because they keep the system grounded.

But freeform questions are useful when the live moment naturally calls for something better.

So the runtime often compares:

- the best prepared question for this slide
- the best freeform question for this exact moment

Then it chooses the stronger one.

## What A Prepared Question Means

A prepared question is a slide-aware concern that was created before the live presentation.

These are useful because they:

- keep the system aligned with the assignment
- reduce generic filler questions
- give the runtime strong anchors

But they are not the only valid response anymore.

## What A Freeform Question Means

A freeform question is generated from the live moment.

This is how FacultyAI can react more naturally when a presenter says something interesting that deserves scrutiny right now.

Examples:

- clarifying a confusing idea
- challenging a vague recommendation
- asking for practical application
- asking for a better distinction between two concepts

## How The Student Profile Memory Works

FacultyAI now has a lightweight speaker-profile memory.

This is not a heavy profile system.

It does not try to build a full student identity model.

It only stores small useful details when confidence is high.

Right now that mainly means:

- if the student is on an individual slide
- and they say something like `I am a Computer Science major`
- or they mention an interest like software, AI, startups, robotics, research, or product
- FacultyAI can store that as part of that student's profile

Then later, when asking a question on that student's individual slide, it can tailor the wording slightly.

Example:

Instead of:

- `Can you give one example of how "good enough" in industry is different from doing low-quality work?`

It can move toward:

- `As a Computer Science major, can you give one example of how "good enough" in industry is different from doing low-quality work?`

This is meant to make the question feel more relevant, not more complicated.

## How It Handles 2 To 4 Students

FacultyAI can handle multiple students because it stores profile context by student name.

That works best when:

- the slide is clearly an individual reflection slide
- the slide author is known
- the student says profile-like information on their own slide

It is less aggressive on shared group slides.

That is intentional.

The system should only personalize when it has a good reason to believe the context belongs to the current speaker.

## Why It Sometimes Waits Or Queues A Question

A good question can still be badly timed.

So FacultyAI may:

- queue a question because the slide just started
- wait because another question was just asked
- hold a question because the speaker is already answering it
- skip a question because the same topic was already covered

This is one of the most important parts of making the system feel smart.

Bad timing makes even a good question feel wrong.

## What Makes It Feel More Human

The system tends to feel better when it:

- lets the presenter finish setting context
- asks only one strong question instead of many small ones
- uses the current slide and current moment, not just the rubric
- avoids repeating the same question shape
- asks for something specific when the student is vague

## What It Does Not Try To Do

FacultyAI is not trying to:

- grade the students live
- act like a generic chatbot
- do perfect speaker diarization
- build a deep psychological model of each presenter
- turn every question into a technical defense question

The goal is simpler:

- listen carefully
- be professionally skeptical
- ask useful questions
- stay grounded in the presentation

## Current Deterministic Thinking In Practice

The main deterministic logic usually goes like this:

1. What slide are we on?
2. What kind of slide is it?
3. Has the presenter said enough yet?
4. What concern is still missing or weak?
5. Is the best move a prepared question or a freeform one?
6. Is now a good time to interrupt?
7. Has this topic already been asked?
8. If yes, ask one question.
9. If not, wait, queue, or skip.

## Why The LLM Is Still There

Most of the cheap control logic is deterministic.

That is good because it keeps the system:

- stable
- cheaper
- easier to tune

The LLM is still useful as an arbitration layer when:

- several questions are plausible
- a freeform question may be better than the prepared option
- the moment requires more human-like judgment

The goal is not to let the LLM run everything.

The goal is to use it where it helps most.
