import asyncio
import json
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from app.config import get_settings
from app.models.response_models import SpeechSessionResponse
from app.services.speech_provider import SpeechProviderName, get_speech_provider

router = APIRouter(prefix="/speech", tags=["speech"])


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

    settings = get_settings()
    if not settings.deepgram_api_key:
        await websocket.send_json({"type": "error", "message": "DEEPGRAM_API_KEY is not configured."})
        await websocket.close(code=1011)
        return

    query = urlencode(
        {
            "model": settings.deepgram_model,
            "language": settings.deepgram_language,
            "encoding": "linear16",
            "sample_rate": "16000",
            "channels": "1",
            "smart_format": "true",
            "interim_results": "true",
            "vad_events": "true",
            "endpointing": "300",
        }
    )
    deepgram_url = f"wss://api.deepgram.com/v1/listen?{query}"

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
        await websocket.send_json({"type": "error", "message": str(exc)})
        await websocket.close(code=1011)

