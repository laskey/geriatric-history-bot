"""
HTTP and WebSocket server for the frontend.

Serves:
- Static frontend files
- Ephemeral API key generation for secure WebRTC connections
- HTTP endpoint for initiating sideband connections
- WebSocket endpoint for streaming state updates to browser
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

import aiohttp
from aiohttp import web, WSMsgType

from src.backend.output import generate_output, save_output
from src.backend.realtime_connection import RealtimeConnection
from src.backend.state import CallState, CallStatus
from src.config.system_prompt import get_system_prompt
from src.config.tools import TOOLS

logger = logging.getLogger(__name__)

# Store active calls by call_id
active_calls: dict[str, "CallSession"] = {}


class CallSession:
    """Manages a single call session with its state and connections."""

    def __init__(self, call_id: str, ephemeral_key: str | None = None, patient_name: str | None = None):
        self.call_id = call_id
        self.ephemeral_key = ephemeral_key
        self.state = CallState(call_id=call_id, patient_name=patient_name)
        self.realtime_connection: RealtimeConnection | None = None
        self.browser_websockets: list[web.WebSocketResponse] = []
        self._event_task: asyncio.Task | None = None

    async def start_sideband(self) -> None:
        """Connect to OpenAI Realtime API via sideband."""
        self.realtime_connection = RealtimeConnection(
            self.state,
            on_transcript=self._on_transcript,
        )
        await self.realtime_connection.connect_sideband(self.call_id, self.ephemeral_key)

        # Start event loop in background
        self._event_task = asyncio.create_task(self._run_event_loop())

    async def _run_event_loop(self) -> None:
        """Run the realtime event loop and broadcast updates."""
        try:
            if self.realtime_connection:
                await self.realtime_connection.run_event_loop()
        except Exception as e:
            logger.error(f"Event loop error for call {self.call_id}: {e}")
        finally:
            # Call ended - broadcast final state and save output
            await self._broadcast_state()
            save_output(self.state)
            logger.info(f"Call {self.call_id} ended, output saved")

    def _on_transcript(self, speaker: str, text: str) -> None:
        """Handle transcript updates - broadcast to browser."""
        asyncio.create_task(self._broadcast_transcript(speaker, text))
        asyncio.create_task(self._broadcast_state())

    async def _broadcast_transcript(self, speaker: str, text: str) -> None:
        """Send transcript update to all connected browsers."""
        message = json.dumps({
            "type": "transcript",
            "speaker": speaker,
            "text": text,
        })
        await self._broadcast(message)

    async def _broadcast_state(self) -> None:
        """Send current state to all connected browsers."""
        output = generate_output(self.state)
        message = json.dumps({
            "type": "state",
            "data": output,
        })
        await self._broadcast(message)

    async def _broadcast(self, message: str) -> None:
        """Broadcast message to all connected browser websockets."""
        disconnected = []
        for ws in self.browser_websockets:
            try:
                if not ws.closed:
                    await ws.send_str(message)
            except Exception:
                disconnected.append(ws)

        # Clean up disconnected sockets
        for ws in disconnected:
            self.browser_websockets.remove(ws)

    async def add_browser_websocket(self, ws: web.WebSocketResponse) -> None:
        """Add a browser websocket connection."""
        self.browser_websockets.append(ws)
        # Send current state immediately
        await self._broadcast_state()

    async def close(self) -> None:
        """Close the session."""
        if self._event_task:
            self._event_task.cancel()
            try:
                await self._event_task
            except asyncio.CancelledError:
                pass

        if self.realtime_connection:
            await self.realtime_connection.close()

        # Close browser websockets
        for ws in self.browser_websockets:
            await ws.close()


async def handle_index(request: web.Request) -> web.Response:
    """Serve the main frontend page."""
    frontend_path = Path(__file__).parent.parent / "frontend" / "index.html"
    if frontend_path.exists():
        return web.FileResponse(frontend_path)
    return web.Response(text="Frontend not found", status=404)


async def handle_static(request: web.Request) -> web.Response:
    """Serve static frontend files."""
    filename = request.match_info.get("filename", "")
    frontend_path = Path(__file__).parent.parent / "frontend" / filename

    if frontend_path.exists() and frontend_path.is_file():
        return web.FileResponse(frontend_path)
    return web.Response(text="File not found", status=404)


async def handle_ephemeral_key(request: web.Request) -> web.Response:
    """
    Generate an ephemeral API key for the browser to use.

    This keeps your main API key secure on the server while allowing
    the browser to establish WebRTC connections directly with OpenAI.

    Ephemeral keys are short-lived and scoped to realtime sessions only.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not set")
        return web.json_response(
            {"error": "Server not configured with API key"},
            status=500
        )

    try:
        # Request ephemeral key from OpenAI with full session configuration
        # This ensures the WebRTC session starts with our prompt and tools
        # Note: input_audio_transcription is NOT supported in client_secrets endpoint
        # It must be set via session.update on the sideband WebSocket connection
        # Note: We use a generic prompt here since we don't know patient name yet
        # The sideband connection will send a session.update with the patient-specific prompt
        session_config = {
            "session": {
                "type": "realtime",
                "model": "gpt-realtime",
                "instructions": get_system_prompt(),  # Generic prompt - sideband will update with patient name
                "tools": TOOLS,
                "audio": {
                    "input": {
                        "turn_detection": {
                            "type": "semantic_vad",
                            "eagerness": "high",
                            "create_response": True,
                            "interrupt_response": True,
                        }
                    },
                    "output": {
                        "voice": "coral"
                    }
                }
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/realtime/client_secrets",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=session_config
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to get ephemeral key: {response.status} - {error_text}")
                    return web.json_response(
                        {"error": "Failed to generate ephemeral key"},
                        status=500
                    )

                data = await response.json()
                ephemeral_key = data.get("value")

                if not ephemeral_key:
                    logger.error(f"No ephemeral key in response: {data}")
                    return web.json_response(
                        {"error": "Invalid response from OpenAI"},
                        status=500
                    )

                logger.info("Generated ephemeral key for client")
                return web.json_response({"key": ephemeral_key})

    except Exception as e:
        logger.error(f"Error generating ephemeral key: {e}")
        return web.json_response(
            {"error": "Failed to generate ephemeral key"},
            status=500
        )


async def handle_start_call(request: web.Request) -> web.Response:
    """
    Handle POST /api/start-call

    Browser sends the call_id from WebRTC connection.
    We start a sideband connection to handle tools.
    """
    try:
        data = await request.json()
        call_id = data.get("call_id")
        ephemeral_key = data.get("ephemeral_key")

        logger.info(f"Received start-call request: call_id={call_id}, ephemeral_key={'present' if ephemeral_key else 'missing'}")

        if not call_id:
            return web.json_response(
                {"error": "call_id is required"},
                status=400
            )

        if call_id in active_calls:
            return web.json_response(
                {"error": "Call already active"},
                status=409
            )

        # Create session and start sideband
        # TODO: In production, patient_name would come from a scheduling system
        patient_name = data.get("patient_name", "Mike Laskey")
        session = CallSession(call_id, ephemeral_key, patient_name)
        active_calls[call_id] = session

        try:
            await session.start_sideband()
        except Exception as e:
            del active_calls[call_id]
            logger.error(f"Failed to start sideband for {call_id}: {e}")
            return web.json_response(
                {"error": f"Failed to connect: {str(e)}"},
                status=500
            )

        logger.info(f"Started sideband for call {call_id}")

        return web.json_response({
            "success": True,
            "call_id": call_id,
        })

    except Exception as e:
        logger.error(f"Error in start_call: {e}")
        return web.json_response(
            {"error": str(e)},
            status=500
        )


async def handle_end_call(request: web.Request) -> web.Response:
    """
    Handle POST /api/end-call

    Clean up a call session.
    """
    try:
        data = await request.json()
        call_id = data.get("call_id")

        if not call_id or call_id not in active_calls:
            return web.json_response(
                {"error": "Call not found"},
                status=404
            )

        session = active_calls[call_id]
        await session.close()
        del active_calls[call_id]

        logger.info(f"Ended call {call_id}")

        return web.json_response({"success": True})

    except Exception as e:
        logger.error(f"Error in end_call: {e}")
        return web.json_response(
            {"error": str(e)},
            status=500
        )


async def handle_call_websocket(request: web.Request) -> web.WebSocketResponse:
    """
    Handle WebSocket connection for live state updates.

    Browser connects to /api/ws/{call_id} to receive state updates.
    """
    call_id = request.match_info.get("call_id")

    if not call_id or call_id not in active_calls:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await ws.send_json({"error": "Call not found"})
        await ws.close()
        return ws

    session = active_calls[call_id]

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    await session.add_browser_websocket(ws)
    logger.info(f"Browser connected to call {call_id}")

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                # Handle any messages from browser if needed
                pass
            elif msg.type == WSMsgType.ERROR:
                logger.error(f"WebSocket error: {ws.exception()}")
    finally:
        if ws in session.browser_websockets:
            session.browser_websockets.remove(ws)
        logger.info(f"Browser disconnected from call {call_id}")

    return ws


async def handle_get_output(request: web.Request) -> web.Response:
    """
    Handle GET /api/output/{call_id}

    Return the structured output for a call.
    """
    call_id = request.match_info.get("call_id")

    if not call_id or call_id not in active_calls:
        return web.json_response(
            {"error": "Call not found"},
            status=404
        )

    session = active_calls[call_id]
    output = generate_output(session.state)

    return web.json_response(output)


def create_app() -> web.Application:
    """Create the aiohttp application."""
    app = web.Application()

    # Routes
    app.router.add_get("/", handle_index)
    app.router.add_get("/static/{filename}", handle_static)
    app.router.add_get("/api/ephemeral-key", handle_ephemeral_key)
    app.router.add_post("/api/start-call", handle_start_call)
    app.router.add_post("/api/end-call", handle_end_call)
    app.router.add_get("/api/ws/{call_id}", handle_call_websocket)
    app.router.add_get("/api/output/{call_id}", handle_get_output)

    return app


async def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Run the server."""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, host, port)
    await site.start()

    logger.info(f"Server running at http://{host}:{port}")
    print(f"\n🚀 Server running at http://localhost:{port}")
    print("   Open this URL in your browser to start testing.\n")

    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await runner.cleanup()
