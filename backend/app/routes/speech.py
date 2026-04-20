from fastapi import APIRouter, HTTPException

from app.services.speech_provider import SpeechProviderName, get_speech_provider

router = APIRouter(prefix="/speech", tags=["speech"])


@router.post("/{provider_name}/session")
async def create_speech_session(provider_name: SpeechProviderName) -> dict[str, str]:
    provider = get_speech_provider(provider_name)
    try:
        provider_session_id = await provider.start_transcription_session()
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return {"provider": provider.name, "providerSessionId": provider_session_id}

