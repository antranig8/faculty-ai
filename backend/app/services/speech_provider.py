from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
from typing import Literal
from urllib import error, request

from app.config import get_settings


SpeechProviderName = Literal["deepgram", "assemblyai"]


@dataclass
class TranscriptEvent:
    text: str
    is_final: bool
    confidence: float | None = None
    started_at_ms: int | None = None
    ended_at_ms: int | None = None


@dataclass
class SpeechSession:
    provider: SpeechProviderName
    access_token: str | None = None
    expires_in: int | None = None
    websocket_url: str | None = None
    model: str | None = None
    language: str | None = None


class SpeechProvider(ABC):
    name: SpeechProviderName

    @abstractmethod
    async def start_transcription_session(self) -> SpeechSession:
        """Create a client-ready live transcription session."""

    @abstractmethod
    async def synthesize_speech(self, text: str) -> bytes:
        """Optional TTS hook for later voice output."""


class DeepgramSpeechProvider(SpeechProvider):
    name: SpeechProviderName = "deepgram"

    async def start_transcription_session(self) -> SpeechSession:
        settings = get_settings()
        if not settings.deepgram_api_key:
            raise RuntimeError("DEEPGRAM_API_KEY is not configured.")

        payload = json.dumps({"ttl_seconds": 60}).encode("utf-8")
        req = request.Request(
            "https://api.deepgram.com/v1/auth/grant",
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Token {settings.deepgram_api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with request.urlopen(req, timeout=10) as response:
                body = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Deepgram token request failed: {details or exc.reason}") from exc
        except error.URLError as exc:
            raise RuntimeError("Unable to reach Deepgram to start a transcription session.") from exc

        is_flux = settings.deepgram_model.startswith("flux-")
        websocket_url = (
            "wss://api.deepgram.com/v2/listen"
            f"?model={settings.deepgram_model}"
            "&encoding=linear16"
            "&sample_rate=16000"
            "&eot_threshold=0.7"
            "&eot_timeout_ms=5000"
        ) if is_flux else (
            "wss://api.deepgram.com/v1/listen"
            f"?model={settings.deepgram_model}"
            f"&language={settings.deepgram_language}"
            "&smart_format=true"
            "&interim_results=true"
            "&vad_events=true"
            "&endpointing=300"
        )

        return SpeechSession(
            provider=self.name,
            access_token=body["access_token"],
            expires_in=body.get("expires_in"),
            websocket_url=websocket_url,
            model=settings.deepgram_model,
            language=settings.deepgram_language,
        )

    async def synthesize_speech(self, text: str) -> bytes:
        raise NotImplementedError("Deepgram TTS is not wired yet.")


class AssemblyAISpeechProvider(SpeechProvider):
    name: SpeechProviderName = "assemblyai"

    async def start_transcription_session(self) -> SpeechSession:
        raise NotImplementedError("AssemblyAI live transcription is not wired yet.")

    async def synthesize_speech(self, text: str) -> bytes:
        raise NotImplementedError("AssemblyAI TTS is not wired yet.")


def get_speech_provider(name: SpeechProviderName) -> SpeechProvider:
    if name == "deepgram":
        return DeepgramSpeechProvider()
    if name == "assemblyai":
        return AssemblyAISpeechProvider()
    raise ValueError(f"Unsupported speech provider: {name}")

