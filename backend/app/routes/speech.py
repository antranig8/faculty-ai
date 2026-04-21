import asyncio
import ipaddress
import json
import logging
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from app.config import get_settings
from app.models.response_models import SpeechSessionResponse
from app.services.speech_provider import SpeechProviderName, get_speech_provider

router = APIRouter(prefix="/speech", tags=["speech"])
logger = logging.getLogger("faculty_ai.speech")


def _is_local_host(host: str | None) -> bool:
    if not host:
        return False
    if host in {"127.0.0.1", "::1", "localhost", "testclient"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _websocket_authorized(websocket: WebSocket) -> bool:
    if _is_local_host(websocket.client.host if websocket.client else None):
        return True

    required_key = get_settings().faculty_ai_app_api_key
    if not required_key:
        return False

    provided_key = websocket.query_params.get("key") or websocket.headers.get("x-facultyai-key")
    return provided_key == required_key


def _deepgram_listen_url(model: str, language: str) -> str:
    is_flux = model.startswith("flux-")
    endpoint = "v2/listen" if is_flux else "v1/listen"
    if is_flux:
        params: dict[str, str] = {
            "model": model,
            "encoding": "linear16",
            "sample_rate": "16000",
            "smart_format": "true",
            "eot_timeout_ms": "5000",
        }
    else:
        params = {
            "model": model,
            "language": language,
            "encoding": "linear16",
            "sample_rate": "16000",
            "channels": "1",
            "smart_format": "true",
            "interim_results": "true",
            "vad_events": "true",
            "endpointing": "300",
        }
        params["language"] = language
    return f"wss://api.deepgram.com/{endpoint}?{urlencode(params)}"


@router.post("/{provider_name}/session", response_model=SpeechSessionResponse)
async def create_speech_session(provider_name: SpeechProviderName) -> SpeechSessionResponse:
    provider = get_speech_provider(provider_name)
    try:
        session = await provider.start_transcription_session()
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return SpeechSessionResponse(
        provider=session.provider,
        accessToken=session.access_token,
        expiresIn=session.expires_in,
        websocketUrl=session.websocket_url,
        model=session.model,
        language=session.language,
    )


@router.websocket("/deepgram/proxy")
async def deepgram_proxy(websocket: WebSocket) -> None:
    await websocket.accept()

    if not _websocket_authorized(websocket):
        await websocket.send_json({"type": "error", "message": "Missing or invalid API key."})
        await websocket.close(code=1008)
        return

    settings = get_settings()
    if not settings.deepgram_api_key:
        await websocket.send_json({"type": "error", "message": "DEEPGRAM_API_KEY is not configured."})
        await websocket.close(code=1011)
        return

    deepgram_url = _deepgram_listen_url(settings.deepgram_model, settings.deepgram_language)

    try:
        async with connect(
            deepgram_url,
            additional_headers={"Authorization": f"Token {settings.deepgram_api_key}"},
            max_size=None,
        ) as deepgram_ws:
            await websocket.send_json({"type": "proxy_open"})

            async def keep_alive() -> None:
                while True:
                    await asyncio.sleep(4)
                    await deepgram_ws.send(json.dumps({"type": "KeepAlive"}))

            async def browser_to_deepgram() -> None:
                while True:
                    message = await websocket.receive()
                    if message.get("bytes") is not None:
                        data = message["bytes"]
                        if data:
                            await deepgram_ws.send(data)
                    elif message.get("text") is not None:
                        payload = message["text"]
                        if payload == "__close__":
                            await deepgram_ws.send(json.dumps({"type": "CloseStream"}))
                            return
                    elif message.get("type") == "websocket.disconnect":
                        await deepgram_ws.send(json.dumps({"type": "CloseStream"}))
                        return

            async def deepgram_to_browser() -> None:
                async for message in deepgram_ws:
                    if isinstance(message, bytes):
                        continue
                    await websocket.send_text(message)

            keep_alive_task = asyncio.create_task(keep_alive())
            browser_task = asyncio.create_task(browser_to_deepgram())
            upstream_task = asyncio.create_task(deepgram_to_browser())

            done, pending = await asyncio.wait(
                {keep_alive_task, browser_task, upstream_task},
                return_when=asyncio.FIRST_EXCEPTION,
            )

            for task in pending:
                task.cancel()

            for task in done:
                exc = task.exception()
                if exc and not isinstance(exc, (WebSocketDisconnect, ConnectionClosed, asyncio.CancelledError)):
                    raise exc

    except ConnectionClosed as exc:
        logger.info("Deepgram upstream closed: code=%s reason=%s", exc.code, exc.reason or "")
        await websocket.send_json(
            {
                "type": "proxy_close",
                "code": exc.code,
                "reason": exc.reason or "",
            }
        )
        await websocket.close()
    except WebSocketDisconnect:
        return
    except Exception as exc:
        logger.exception("deepgram_proxy failed")
        await websocket.send_json({"type": "error", "message": str(exc)})
        await websocket.close(code=1011)

