import asyncio
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from groq import APITimeoutError
import httpx

from app.models.request_models import AnalyzeChunkRequest, PresentationPrepareRequest, ProjectContext, QuestionRephraseRequest
from app.models.response_models import FeedbackItem, Slide


class RehearsalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = TemporaryDirectory()
        cls.addClassCleanup(directory.cleanup)
        cls.db_path = Path(directory.name) / "test.db"
        with patch.dict("os.environ", {"FACULTY_AI_DB_PATH": str(cls.db_path)}):
            from app import state

        cls.state = state
        path_patch = patch.object(state, "_DB_PATH", cls.db_path)
        path_patch.start()
        cls.addClassCleanup(path_patch.stop)
        state._init_db()

    def setUp(self):
        self.context = ProjectContext(title="Audit rehearsal")
        self.slide = Slide(slideNumber=3, title="Results", content="Participant reports and evaluation")

    def _analyze(self, session_id: str, text: str, recent: list[str] | None = None):
        from app.routes.analyze import analyze_chunk

        return analyze_chunk(AnalyzeChunkRequest(
            sessionId=session_id,
            projectContext=self.context,
            transcriptChunk=text,
            recentTranscript=recent or [],
            currentSlide=self.slide,
            slideMode="manual",
            simulatedSecondsOnSlide=45,
        ))

    def _start_with_question(self):
        from app.models.request_models import SessionStartRequest
        from app.routes.analyze import _record_feedback
        from app.routes.session import start_session

        session_id = start_session(SessionStartRequest(projectContext=self.context)).sessionId
        session = self.state.get_session(session_id)
        session["transcript"].append("We measured feedback and collected reports in a survey before the question.")
        _record_feedback(session, FeedbackItem(
            type="clarification",
            priority="medium",
            section="evaluation",
            message="Which evidence supports this finding?",
            reason="Test question",
            createdAt=self.state.utc_now_iso(),
            slideNumber=3,
            sourceQuestionId="reports",
            autoResolutionTerms=["reports", "measured feedback"],
        ), 3)
        self.state.save_session(session_id, session)
        return session_id, session

    def test_partial_answer_delivers_one_follow_up_after_answer_window(self):
        from app.services.cooldown import utc_now

        session_id, session = self._start_with_question()
        partial = self._analyze(session_id, "We saw reports from a few people nearby.")
        self.assertEqual(partial.answerEvaluation.answerQuality, "partial")
        self.assertIsNotNone(partial.queuedFeedback)
        waiting = self._analyze(session_id, "We are still thinking about this point.")
        self.assertFalse(waiting.trigger)
        self.assertIsNotNone(waiting.queuedFeedback)
        session["awaiting_answer_until"] = utc_now() - timedelta(seconds=1)
        session["last_feedback_at"] = utc_now() - timedelta(seconds=30)

        follow_up = self._analyze(session_id, "We can explain more about what we did.")
        self.assertTrue(follow_up.trigger, follow_up.reason)
        self.assertEqual(follow_up.feedback.followUpToQuestionId, "reports")
        self.assertIsNone(follow_up.queuedFeedback)
        self.assertEqual(len(session["feedback"]), 2)
        self.assertIsNone(self._analyze(session_id, "Our team is still working through the details.").queuedFeedback)

    def test_confirmation_does_not_use_speech_from_before_the_question(self):
        session_id, session = self._start_with_question()
        self.state.sessions.pop(session_id)
        result = self._analyze(session_id, "Does that answer your question?", recent=session["transcript"])
        self.assertFalse(result.trigger)
        self.assertIsNone(result.resolvedFeedback)
        self.assertEqual(result.answerEvaluation.answerQuality, "weak")

    def test_answer_quality_is_saved_when_a_duplicate_question_is_suppressed(self):
        session_id, session = self._start_with_question()
        candidate = session["feedback"][-1]
        with patch("app.routes.analyze.generate_slide_handoff_feedback", return_value=(candidate, "Test duplicate")):
            result = self._analyze(session_id, "We are still thinking about this point.")

        self.assertFalse(result.trigger)
        self.assertEqual(result.answerEvaluation.answerQuality, "weak")
        self.state.sessions.pop(session_id)
        saved_feedback = self.state.get_session(session_id)["feedback"][-1]
        self.assertEqual(saved_feedback.answerQuality, "weak")
        self.assertFalse(saved_feedback.resolved)

    def test_strong_answer_cancels_its_queued_follow_up(self):
        session_id, _ = self._start_with_question()
        partial = self._analyze(session_id, "We saw reports from a few people nearby.")
        self.assertIsNotNone(partial.queuedFeedback)
        strong = self._analyze(session_id, "We measured feedback in a survey and documented all reports.")
        self.assertEqual(strong.answerEvaluation.answerQuality, "strong")
        self.assertTrue(strong.resolvedFeedback.resolved)
        self.assertIsNone(strong.queuedFeedback)

    def test_provider_failure_does_not_cache_heuristic_fallback(self):
        from app.routes.presentation import prepare_presentation
        from app.services.presentation_preparer import parse_slide_outline, prepare_questions

        outline = "Slide 1: Pilot\nWe chose a small test group before expanding the program."
        request = PresentationPrepareRequest(projectContext=self.context, slideOutline=outline)
        questions = prepare_questions(self.context, parse_slide_outline(outline))
        with patch.dict("os.environ", {"FACULTY_AI_LLM_PROVIDER": "groq", "GROQ_API_KEY": "test"}):
            with patch("app.routes.presentation.prepare_questions_with_llm", side_effect=[None, questions]) as llm:
                self.assertEqual(prepare_presentation(request).questionSource, "heuristic")
                self.assertEqual(prepare_presentation(request).questionSource, "llm")
                self.assertTrue(prepare_presentation(request).cacheHit)
                self.assertEqual(llm.call_count, 2)
            with patch.dict("os.environ", {"FACULTY_AI_LLM_PROVIDER": "heuristic"}):
                self.assertEqual(prepare_presentation(request).questionSource, "heuristic")

    def test_invalid_deck_returns_bad_request(self):
        from app.routes.presentation import upload_presentation

        with self.assertRaises(HTTPException) as error:
            upload_presentation(UploadFile(filename="invalid.pptx", file=BytesIO(b"Invalid document")))
        self.assertEqual(error.exception.status_code, 400)

    def test_rephrase_provider_timeout_returns_unavailable(self):
        from app.routes.speech import rephrase_faculty_question

        timeout = APITimeoutError(request=httpx.Request("POST", "https://api.groq.com"))
        with patch("app.routes.speech.rephrase_question", side_effect=timeout), self.assertRaises(HTTPException) as error:
            asyncio.run(rephrase_faculty_question(QuestionRephraseRequest(question="What evidence supports this finding?")))
        self.assertEqual(error.exception.status_code, 503)
