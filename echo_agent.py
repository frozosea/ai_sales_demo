import logging
import asyncio
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    RoomInputOptions,
    WorkerOptions,
    cli,
    AutoSubscribe,
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("echo_agent")

load_dotenv()

class EchoAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="Simple echo agent that returns audio back to the user"
        )
        self.chunk_count = 0
        logger.info("EchoAgent initialized")

    async def process_audio_chunk(self, context: RunContext, audio_chunk: bytes) -> bytes:
        """Simply returns the audio chunk back to the user"""
        self.chunk_count += 1
        logger.info(f"Processing audio chunk #{self.chunk_count}, size: {len(audio_chunk)} bytes")

        # Log first few chunks and then every 100th
        if self.chunk_count <= 5 or self.chunk_count % 100 == 0:
            logger.info(f"Processing audio chunk #{self.chunk_count}, size: {len(audio_chunk)} bytes")
        
        # Return the audio chunk as-is for echo
        return audio_chunk

def prewarm(proc: JobProcess):
    logger.info("Prewarming echo agent")

async def entrypoint(ctx: JobContext):
    # Log context
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    logger.info(f"Starting echo agent in room: {ctx.room.name}")

    # Connect to room first with audio-only subscription
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    
    # Wait for participant
    participant = await ctx.wait_for_participant()
    logger.info(f"Participant joined: {participant.identity}")

    # Create basic session without STT/TTS/LLM
    session = AgentSession()

    # Handle room events
    @ctx.room.on("participant_connected")
    def on_participant_connected(participant):
        logger.info(f"Participant connected: {participant.identity}")
        
    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        logger.info(f"Participant disconnected: {participant.identity}")

    # Start session
    logger.info("Starting echo agent session...")
    await session.start(
        agent=EchoAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            close_on_disconnect=False,  # Keep session alive when participant disconnects
        )
    )

    logger.info("Echo agent ready!")
    
    # Keep the agent running
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("Echo agent shutting down...")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        prewarm_fnc=prewarm
    )) 