from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal


SpeechProviderName = Literal["deepgram", "assemblyai"]


@dataclass
class TranscriptEvent:
    text: str
    is_final: bool
    confidence: float | None = None
    started_at_ms: int | None = None
    ended_at_ms: int | None = None


class SpeechProvider(ABC):
    name: SpeechProviderName

    @abstractmethod
    async def start_transcription_session(self) -> str:
        """Create a provider-side live transcription session."""

    @abstractmethod
    async def synthesize_speech(self, text: str) -> bytes:
        """Optional TTS hook for later voice output."""


class DeepgramSpeechProvider(SpeechProvider):
    name: SpeechProviderName = "deepgram"

    async def start_transcription_session(self) -> str:
        raise NotImplementedError("Deepgram live transcription is not wired yet.")

    async def synthesize_speech(self, text: str) -> bytes:
        raise NotImplementedError("Deepgram TTS is not wired yet.")


class AssemblyAISpeechProvider(SpeechProvider):
    name: SpeechProviderName = "assemblyai"

    async def start_transcription_session(self) -> str:
        raise NotImplementedError("AssemblyAI live transcription is not wired yet.")

    async def synthesize_speech(self, text: str) -> bytes:
        raise NotImplementedError("AssemblyAI TTS is not wired yet.")


def get_speech_provider(name: SpeechProviderName) -> SpeechProvider:
    if name == "deepgram":
        return DeepgramSpeechProvider()
    if name == "assemblyai":
        return AssemblyAISpeechProvider()
    raise ValueError(f"Unsupported speech provider: {name}")

