import asyncio
import ipaddress
import json
import logging
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
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


def _websocket_open(websocket: WebSocket) -> bool:
    return (
        websocket.client_state == WebSocketState.CONNECTED
        and websocket.application_state == WebSocketState.CONNECTED
    )


async def _safe_send_json(websocket: WebSocket, payload: dict) -> bool:
    if not _websocket_open(websocket):
        return False
    try:
        await websocket.send_json(payload)
        return True
    except (RuntimeError, WebSocketDisconnect):
        return False


async def _safe_send_text(websocket: WebSocket, payload: str) -> bool:
    if not _websocket_open(websocket):
        return False
    try:
        await websocket.send_text(payload)
        return True
    except (RuntimeError, WebSocketDisconnect):
        return False


async def _safe_close(websocket: WebSocket, code: int = 1000) -> None:
    if not _websocket_open(websocket):
        return
    try:
        await websocket.close(code=code)
    except RuntimeError:
        return


async def _safe_deepgram_send(deepgram_ws, payload) -> bool:
    try:
        await deepgram_ws.send(payload)
        return True
    except ConnectionClosed:
        return False


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


@router.get("/deepgram/tts/preview")
async def deepgram_tts_preview() -> dict[str, bool | str]:
    settings = get_settings()
    return {
        "provider": "deepgram",
        "enabled": bool(settings.deepgram_api_key),
    }


@router.websocket("/deepgram/proxy")
async def deepgram_proxy(websocket: WebSocket) -> None:
    await websocket.accept()

    if not _websocket_authorized(websocket):
        await _safe_send_json(websocket, {"type": "error", "message": "Missing or invalid API key."})
        await _safe_close(websocket, code=1008)
        return

    settings = get_settings()
    if not settings.deepgram_api_key:
        await _safe_send_json(websocket, {"type": "error", "message": "DEEPGRAM_API_KEY is not configured."})
        await _safe_close(websocket, code=1011)
        return

    deepgram_url = _deepgram_listen_url(settings.deepgram_model, settings.deepgram_language)

    try:
        async with connect(
            deepgram_url,
            additional_headers={"Authorization": f"Token {settings.deepgram_api_key}"},
            max_size=None,
        ) as deepgram_ws:
            await _safe_send_json(websocket, {"type": "proxy_open"})

            async def keep_alive() -> None:
                while True:
                    await asyncio.sleep(4)
                    if not await _safe_deepgram_send(deepgram_ws, json.dumps({"type": "KeepAlive"})):
                        return

            async def browser_to_deepgram() -> None:
                while True:
                    message = await websocket.receive()
                    if message.get("bytes") is not None:
                        data = message["bytes"]
                        if data:
                            if not await _safe_deepgram_send(deepgram_ws, data):
                                return
                    elif message.get("text") is not None:
                        payload = message["text"]
                        if payload == "__close__":
                            await _safe_deepgram_send(deepgram_ws, json.dumps({"type": "CloseStream"}))
                            return
                    elif message.get("type") == "websocket.disconnect":
                        await _safe_deepgram_send(deepgram_ws, json.dumps({"type": "CloseStream"}))
                        return

            async def deepgram_to_browser() -> None:
                async for message in deepgram_ws:
                    if isinstance(message, bytes):
                        continue
                    if not await _safe_send_text(websocket, message):
                        return

            keep_alive_task = asyncio.create_task(keep_alive())
            browser_task = asyncio.create_task(browser_to_deepgram())
            upstream_task = asyncio.create_task(deepgram_to_browser())

            done, pending = await asyncio.wait(
                {keep_alive_task, browser_task, upstream_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

            for task in done:
                if task.cancelled():
                    continue
                exc = task.exception()
                if exc and not isinstance(exc, (WebSocketDisconnect, ConnectionClosed, asyncio.CancelledError)):
                    raise exc

    except ConnectionClosed as exc:
        logger.info("Deepgram upstream closed: code=%s reason=%s", exc.code, exc.reason or "")
        await _safe_send_json(
            websocket,
            {
                "type": "proxy_close",
                "code": exc.code,
                "reason": exc.reason or "",
            },
        )
        await _safe_close(websocket)
    except WebSocketDisconnect:
        return
    except Exception as exc:
        logger.exception("deepgram_proxy failed")
        await _safe_send_json(websocket, {"type": "error", "message": str(exc)})
        await _safe_close(websocket, code=1011)

