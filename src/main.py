"""
Main entry point for the geriatric intake voice AI.

Usage:
    python -m src.main --simulate     # Text-based simulation (no audio)
    python -m src.main --server       # Run web server for browser-based testing
    python -m src.main --sideband <call_id>  # Connect to existing WebRTC session
"""

import argparse
import asyncio
import logging
import sys
import uuid
from typing import Optional

from dotenv import load_dotenv

from src.backend.output import print_summary, save_output
from src.backend.realtime_connection import RealtimeConnection
from src.backend.state import CallState, CallStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def on_transcript(speaker: str, text: str) -> None:
    """Callback for transcript updates - print to console."""
    prefix = "👤 Patient" if speaker == "patient" else "🤖 Assistant"
    print(f"\n{prefix}: {text}")


async def run_simulation() -> None:
    """
    Run in simulation mode with text input instead of audio.

    This allows rapid iteration on the prompt and tools without
    dealing with audio capture.
    """
    print("\n" + "=" * 60)
    print("GERIATRIC INTAKE SIMULATION MODE")
    print("=" * 60)
    print("\nThis simulates a patient intake call using text input.")
    print("Type your responses as the patient would speak them.")
    print("Type 'quit' or 'exit' to end the simulation.")
    print("Type 'status' to see current call state.")
    print("=" * 60 + "\n")

    # Create call state
    call_id = str(uuid.uuid4())[:8]
    state = CallState(call_id=call_id)

    # Create connection
    connection = RealtimeConnection(state, on_transcript=on_transcript)

    try:
        # Connect to Realtime API
        print("Connecting to OpenAI Realtime API...")
        await connection.connect_direct()
        print("Connected!\n")

        # Start the event loop in background
        event_task = asyncio.create_task(connection.run_event_loop())

        # Trigger the AI to start the conversation
        await connection.trigger_greeting()

        # Give the AI time to respond
        await asyncio.sleep(2)

        # Input loop
        while state.status == CallStatus.IN_PROGRESS:
            try:
                # Get user input
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("\n> ").strip()
                )

                if not user_input:
                    continue

                if user_input.lower() in ("quit", "exit"):
                    print("\nEnding simulation...")
                    break

                if user_input.lower() == "status":
                    print_summary(state)
                    continue

                # Send as user message
                await connection.send_user_message(user_input)

                # Give time for response
                await asyncio.sleep(2)

            except EOFError:
                break

        # Clean up
        event_task.cancel()
        try:
            await event_task
        except asyncio.CancelledError:
            pass

    except Exception as e:
        logger.error(f"Error in simulation: {e}")
        raise

    finally:
        await connection.close()

        # Generate output
        print("\n\nGenerating output...")
        output_path = save_output(state)
        print(f"Output saved to: {output_path}")

        print_summary(state)


async def run_sideband(call_id: str) -> None:
    """
    Run in sideband mode, connecting to an existing WebRTC session.

    Args:
        call_id: The call ID from the WebRTC connection
    """
    logger.info(f"Starting sideband connection for call: {call_id}")

    # Create call state
    state = CallState(call_id=call_id)

    # Create connection
    connection = RealtimeConnection(state, on_transcript=on_transcript)

    try:
        # Connect to existing session
        await connection.connect_sideband(call_id)

        # Configure with our tools and prompt
        # (The frontend handles audio, we just handle tools)

        # Run event loop until session ends
        await connection.run_event_loop()

    except Exception as e:
        logger.error(f"Error in sideband mode: {e}")
        raise

    finally:
        await connection.close()

        # Generate output
        output_path = save_output(state)
        logger.info(f"Output saved to: {output_path}")

        print_summary(state)


def main() -> None:
    """Main entry point."""
    # Load environment variables from .env file
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Geriatric intake voice AI system"
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--simulate",
        action="store_true",
        help="Run in simulation mode with text input (no audio)"
    )
    mode_group.add_argument(
        "--server",
        action="store_true",
        help="Run web server for browser-based voice testing"
    )
    mode_group.add_argument(
        "--sideband",
        metavar="CALL_ID",
        help="Connect to existing WebRTC session by call ID"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for web server (default: 8080)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host for web server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        if args.simulate:
            asyncio.run(run_simulation())
        elif args.server:
            from src.backend.server import run_server
            asyncio.run(run_server(host=args.host, port=args.port))
        elif args.sideband:
            asyncio.run(run_sideband(args.sideband))

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
