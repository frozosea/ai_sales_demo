import asyncio
import logging
from dotenv import load_dotenv
import os
from livekit import rtc, api

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("echo")

load_dotenv()

LIVEKIT_URL = os.getenv('LIVEKIT_URL')
LIVEKIT_API_KEY = os.getenv('LIVEKIT_API_KEY')
LIVEKIT_API_SECRET = os.getenv('LIVEKIT_API_SECRET')

class EchoBot:
    def __init__(self, room_name: str):
        self.room_name = room_name
        self.room = None
        self.audio_source = None
        self.audio_track = None
        self.chunk_count = 0
        self._audio_tasks = set()
        
    async def setup(self):
        """Initialize room and audio components"""
        logger.info("Setting up echo bot...")
        
        # Create room
        self.room = rtc.Room()
        
        # Create audio source
        self.audio_source = rtc.AudioSource(
            sample_rate=48000,
            num_channels=1
        )
        
        # Handle room events
        @self.room.on("connected")
        def on_connected():
            logger.info("Connected to room")
            
        @self.room.on("disconnected")
        def on_disconnected():
            logger.info("Disconnected from room")
            
        @self.room.on("participant_connected")
        def on_participant_connected(participant):
            logger.info(f"Participant connected: {participant.identity}")
            
        @self.room.on("participant_disconnected")
        def on_participant_disconnected(participant):
            logger.info(f"Participant disconnected: {participant.identity}")
            
        @self.room.on("track_subscribed")
        def on_track_subscribed(track, publication, participant):
            logger.info(f"Track subscribed: {track.kind} from {participant.identity}")
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                # Create audio stream
                audio_stream = rtc.AudioStream(track)
                # Start audio handling in a new task
                task = asyncio.create_task(self.handle_audio_stream(audio_stream))
                self._audio_tasks.add(task)
                task.add_done_callback(self._audio_tasks.discard)
                
        @self.room.on("track_unsubscribed")
        def on_track_unsubscribed(track, publication, participant):
            logger.info(f"Track unsubscribed: {track.kind} from {participant.identity}")
            
    async def connect(self):
        """Connect to room and publish audio track"""
        logger.info(f"Connecting to room: {self.room_name}")
        
        # Connect to room

        token = (
        api.AccessToken()
        .with_identity("echo-bot")
        .with_grants(api.VideoGrants(room_join=True, room=self.room_name))
    )
        
        await self.room.connect(LIVEKIT_URL, token.to_jwt())
        logger.info("Connected to room")
        
        # Create and publish audio track
        self.audio_track = rtc.LocalAudioTrack.create_audio_track(
            "echo",
            self.audio_source
        )
        await self.room.local_participant.publish_track(self.audio_track)
        logger.info("Published audio track")
        
    async def handle_audio_stream(self, stream: rtc.AudioStream):
        """Handle incoming audio stream"""
        logger.info("Starting to handle audio stream")
        try:
            async for frame_event in stream:
                self.chunk_count += 1
                if self.chunk_count <= 5 or self.chunk_count % 100 == 0:
                    logger.info(f"Processing audio chunk #{self.chunk_count}, size: {len(frame_event.frame.data)} bytes")
                
                # Echo the audio back
                await self.audio_source.capture_frame(frame_event.frame)
                if self.chunk_count <= 5:
                    logger.info(f"Sent chunk #{self.chunk_count} back through audio source")
        except Exception as e:
            logger.error(f"Error in audio stream handler: {e}")
        finally:
            logger.info("Audio stream handler finished")
            
    async def run(self):
        """Run the echo bot"""
        await self.setup()
        await self.connect()
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Shutting down...")
            # Cancel all audio tasks
            for task in self._audio_tasks:
                task.cancel()
            await asyncio.gather(*self._audio_tasks, return_exceptions=True)
            await self.room.disconnect()

async def main():
    # Create and run echo bot
    bot = EchoBot("echo-room")
    await bot.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user") 