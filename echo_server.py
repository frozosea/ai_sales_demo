import asyncio
import logging
import time
from typing import Dict, Optional
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import cli, JobContext, JobProcess, WorkerOptions

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("echo_server")

load_dotenv()

class EchoServer:
    def __init__(self):
        self.participants: Dict[str, rtc.Participant] = {}
        self.audio_tracks: Dict[str, rtc.LocalAudioTrack] = {}
        self.chunk_count = 0
        self.is_echoing = True  # Control echo on/off
        self.last_activity = time.time()
        self.activity_threshold = 0.5  # Seconds of silence before stopping echo
        
    async def handle_participant_connected(self, participant: rtc.Participant):
        """Handle new participant connection"""
        logger.info(f"Participant connected: {participant.identity}")
        self.participants[participant.identity] = participant
        
        # Subscribe to participant's audio tracks
        @participant.on("track_subscribed")
        async def on_track_subscribed(track: rtc.Track, publication: rtc.TrackPublication, participant: rtc.Participant):
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                logger.info(f"Audio track subscribed from {participant.identity}")
                await self.handle_audio_track(track, participant)
    
    async def handle_participant_disconnected(self, participant: rtc.Participant):
        """Handle participant disconnection"""
        logger.info(f"Participant disconnected: {participant.identity}")
        if participant.identity in self.participants:
            del self.participants[participant.identity]
        if participant.identity in self.audio_tracks:
            del self.audio_tracks[participant.identity]
    
    def detect_activity(self, audio_frame) -> bool:
        """Detect if there's audio activity in the frame"""
        # Simple activity detection based on frame data
        if hasattr(audio_frame, 'data'):
            # Check if frame has non-zero data
            data = audio_frame.data
            if isinstance(data, bytes):
                # Convert bytes to numbers and check for non-zero values
                values = [b for b in data if b != 0]
                return len(values) > len(data) * 0.1  # 10% non-zero values
        return True  # Default to active if we can't determine
    
    async def handle_audio_track(self, track: rtc.Track, participant: rtc.Participant):
        """Handle incoming audio track with echo and interruption logic"""
        logger.info(f"Starting audio echo for {participant.identity}")
        
        # Create local audio track for echo
        local_track = rtc.LocalAudioTrack.create_audio_track("echo")
        self.audio_tracks[participant.identity] = local_track
        
        # Publish the echo track
        await participant.room.local_participant.publish_track(local_track)
        
        # Process audio frames
        async for frame in track:
            self.chunk_count += 1
            
            # Detect activity
            is_active = self.detect_activity(frame)
            if is_active:
                self.last_activity = time.time()
                if not self.is_echoing:
                    logger.info("Audio activity detected - starting echo")
                    self.is_echoing = True
            
            # Log first few chunks and then every 100th
            if self.chunk_count <= 5 or self.chunk_count % 100 == 0:
                logger.info(f"Processing audio frame #{self.chunk_count} from {participant.identity}, active: {is_active}, echoing: {self.is_echoing}")
            
            # Echo the audio frame back if we're in echoing mode
            if self.is_echoing:
                try:
                    await local_track.write_frame(frame)
                except Exception as e:
                    logger.error(f"Error writing echo frame: {e}")
            
            # Check for silence timeout
            if self.is_echoing and (time.time() - self.last_activity) > self.activity_threshold:
                logger.info("Silence detected - stopping echo")
                self.is_echoing = False

def prewarm(proc: JobProcess):
    logger.info("Prewarming echo server")

async def entrypoint(ctx: JobContext):
    logger.info(f"Starting echo server in room: {ctx.room.name}")
    
    # Create echo server instance
    echo_server = EchoServer()
    
    # Connect to room
    await ctx.connect()
    
    # Handle participant events
    @ctx.room.on("participant_connected")
    async def on_participant_connected(participant: rtc.Participant):
        await echo_server.handle_participant_connected(participant)
    
    @ctx.room.on("participant_disconnected")
    async def on_participant_disconnected(participant: rtc.Participant):
        await echo_server.handle_participant_disconnected(participant)
    
    logger.info("Echo server ready!")
    
    # Keep the server running
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("Echo server shutting down...")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        prewarm_fnc=prewarm
    )) 