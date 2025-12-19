"""
WebSocket connection handler for OpenAI Realtime API.

Handles both:
1. Direct WebSocket connection (for simulation mode)
2. Sideband connection (for production with WebRTC frontend)
"""

import asyncio
import json
import logging
import os
from typing import Any, Callable, Optional

import websockets
from websockets.asyncio.client import ClientConnection

from src.backend.state import CallState
from src.backend.tool_handlers import ToolHandlers, parse_tool_arguments
from src.config.system_prompt import get_system_prompt
from src.config.tools import TOOLS

logger = logging.getLogger(__name__)

# Realtime API endpoints
REALTIME_API_URL = "wss://api.openai.com/v1/realtime"
MODEL = "gpt-realtime"


class RealtimeConnection:
    """
    Manages WebSocket connection to OpenAI Realtime API.

    Can operate in two modes:
    - Direct: Creates a new session (for simulation/testing)
    - Sideband: Connects to existing session by call_id (for production)
    """

    def __init__(
        self,
        state: CallState,
        on_transcript: Optional[Callable[[str, str], None]] = None,
    ):
        """
        Initialize the connection handler.

        Args:
            state: CallState instance to update with extracted data
            on_transcript: Optional callback for transcript updates (speaker, text)
        """
        self.state = state
        self.tool_handlers = ToolHandlers(state)
        self.on_transcript = on_transcript
        self.ws: Optional[ClientConnection] = None
        self._running = False

    def _get_api_key(self) -> str:
        """Get OpenAI API key from environment."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        return api_key

    def _build_session_config(self) -> dict[str, Any]:
        """Build the session configuration for session.update."""
        # Generate system prompt with patient name if available
        system_prompt = get_system_prompt(self.state.patient_name)

        return {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "model": MODEL,
                "instructions": system_prompt,
                "tools": TOOLS,
                "audio": {
                    "input": {
                        "transcription": {
                            "model": "whisper-1",
                            "language": "en",
                        },
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

    async def connect_direct(self) -> None:
        """
        Connect directly to Realtime API (creates new session).

        Used for simulation/testing mode.
        """
        api_key = self._get_api_key()
        url = f"{REALTIME_API_URL}?model={MODEL}"

        logger.info(f"Connecting to Realtime API: {url}")

        self.ws = await websockets.connect(
            url,
            additional_headers={
                "Authorization": f"Bearer {api_key}",
            },
        )

        logger.info("Connected to Realtime API")

        # Wait for session.created, then configure
        await self._wait_for_session_created()
        await self._configure_session()

    async def connect_sideband(self, call_id: str, ephemeral_key: str | None = None) -> None:
        """
        Connect to existing session via sideband (for WebRTC frontend).

        Args:
            call_id: The call ID from the WebRTC connection's Location header
            ephemeral_key: The ephemeral key used to create the WebRTC session (may be required)
        """
        # Use ephemeral key if provided, otherwise fall back to main API key
        api_key = ephemeral_key if ephemeral_key else self._get_api_key()
        url = f"{REALTIME_API_URL}?call_id={call_id}"

        logger.info(f"Connecting to Realtime API (sideband): {url}")
        logger.info(f"Using {'ephemeral key' if ephemeral_key else 'main API key'} for auth")

        self.ws = await websockets.connect(
            url,
            additional_headers={
                "Authorization": f"Bearer {api_key}",
            },
        )

        logger.info(f"Connected to Realtime API (sideband) for call {call_id}")

        # Configure the session with our tools and prompt
        await self._configure_session()

        # Trigger the AI to start the conversation with a greeting
        await self.trigger_greeting()

    async def _wait_for_session_created(self) -> None:
        """Wait for session.created event after connecting."""
        if not self.ws:
            raise RuntimeError("WebSocket not connected")

        async for message in self.ws:
            event = json.loads(message)
            event_type = event.get("type")

            if event_type == "session.created":
                logger.info("Session created")
                return
            elif event_type == "error":
                raise RuntimeError(f"Error from API: {event.get('error')}")

    async def _configure_session(self) -> None:
        """Send session configuration with tools and instructions."""
        if not self.ws:
            raise RuntimeError("WebSocket not connected")

        config = self._build_session_config()
        await self.ws.send(json.dumps(config))
        logger.info("Session configured with tools and instructions")

    async def send_user_message(self, text: str) -> None:
        """
        Send a text message as user input (for simulation mode).

        Args:
            text: The user's text message
        """
        if not self.ws:
            raise RuntimeError("WebSocket not connected")

        # Add message to conversation
        await self.ws.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": text
                    }
                ]
            }
        }))

        # Trigger response
        await self.ws.send(json.dumps({
            "type": "response.create"
        }))

        # Record in transcript
        self.state.add_transcript_entry("patient", text)
        if self.on_transcript:
            self.on_transcript("patient", text)

    async def run_event_loop(self) -> None:
        """
        Main event loop - listen for and handle Realtime API events.

        Runs until the session ends or an error occurs.
        """
        if not self.ws:
            raise RuntimeError("WebSocket not connected")

        self._running = True
        current_response_text = ""

        try:
            async for message in self.ws:
                if not self._running:
                    break

                event = json.loads(message)
                event_type = event.get("type", "")

                await self._handle_event(event_type, event)

        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"Connection closed: {e}")
        except Exception as e:
            logger.error(f"Error in event loop: {e}")
            raise

    async def _handle_event(self, event_type: str, event: dict[str, Any]) -> None:
        """Handle a single event from the Realtime API."""

        # Log all events at info level for debugging
        logger.info(f"Event: {event_type}")

        if event_type == "error":
            error = event.get("error", {})
            logger.error(f"API Error: {error}")

        elif event_type == "session.updated":
            # Log the session config to verify transcription was accepted
            session = event.get("session", {})
            audio_input = session.get("audio", {}).get("input", {})
            transcription_config = audio_input.get("transcription")
            logger.info(f"Session configuration updated - transcription config: {transcription_config}")

        elif event_type == "conversation.item.input_audio_transcription.completed":
            # Patient speech transcribed
            transcript = event.get("transcript", "")
            if transcript:
                self.state.add_transcript_entry("patient", transcript)
                if self.on_transcript:
                    self.on_transcript("patient", transcript)
                logger.info(f"Patient: {transcript}")

        elif event_type == "response.output_text.delta":
            # Text response streaming (simulation mode)
            delta = event.get("delta", "")
            # We'll accumulate this in response.output_text.done

        elif event_type == "response.output_text.done":
            # Complete text response
            text = event.get("text", "")
            if text:
                self.state.add_transcript_entry("assistant", text)
                if self.on_transcript:
                    self.on_transcript("assistant", text)
                logger.info(f"Assistant: {text}")

        elif event_type == "response.output_audio_transcript.done":
            # AI audio response transcribed (voice mode)
            transcript = event.get("transcript", "")
            if transcript:
                self.state.add_transcript_entry("assistant", transcript)
                if self.on_transcript:
                    self.on_transcript("assistant", transcript)
                logger.info(f"Assistant: {transcript}")

        elif event_type == "response.function_call_arguments.done":
            # Tool call ready to execute
            await self._handle_tool_call(event)

        elif event_type == "response.done":
            # Response complete
            response = event.get("response", {})
            status = response.get("status")
            if status == "failed":
                logger.error(f"Response failed: {response.get('status_details')}")

        elif event_type == "input_audio_buffer.speech_started":
            logger.debug("Speech detected")

        elif event_type == "input_audio_buffer.speech_stopped":
            logger.debug("Speech ended")

    async def _handle_tool_call(self, event: dict[str, Any]) -> None:
        """Handle a tool call from the model."""
        call_id = event.get("call_id", "")
        name = event.get("name", "")
        arguments_str = event.get("arguments", "{}")

        logger.info(f"Tool call: {name}({arguments_str})")

        # Parse arguments and execute handler
        arguments = parse_tool_arguments(arguments_str)
        result = self.tool_handlers.handle_tool_call(name, arguments)

        # Send result back to API
        await self._send_tool_result(call_id, result)

        # Don't trigger continuation after end_interview - the call is done
        # This prevents a redundant second goodbye message
        if name == "end_interview":
            logger.info("Interview ended, not triggering continuation")
            return

        # Trigger continuation for other tools
        await self.ws.send(json.dumps({"type": "response.create"}))

    async def _send_tool_result(self, call_id: str, result: dict[str, Any]) -> None:
        """Send tool execution result back to the API."""
        if not self.ws:
            raise RuntimeError("WebSocket not connected")

        await self.ws.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": json.dumps(result)
            }
        }))

        logger.debug(f"Sent tool result for {call_id}")

    async def trigger_greeting(self) -> None:
        """
        Trigger the AI to start the conversation with a greeting.

        Called after session is configured to initiate the call.
        """
        if not self.ws:
            raise RuntimeError("WebSocket not connected")

        # Send an empty response.create to trigger the AI to speak first
        await self.ws.send(json.dumps({
            "type": "response.create"
        }))

        logger.info("Triggered greeting")

    async def close(self) -> None:
        """Close the WebSocket connection."""
        self._running = False
        if self.ws:
            await self.ws.close()
            logger.info("Connection closed")
