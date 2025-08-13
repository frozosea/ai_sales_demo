import asyncio
import logging
import time
import os
import math
from dotenv import load_dotenv
from livekit import rtc
from livekit.api import LiveKitAPI, AccessToken, VideoGrants

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("simple_echo_server")

load_dotenv()

class SimpleEchoServer:
    def __init__(self):
        self.room = None
        self.participants = {}
        self.audio_tracks = {}
        self.chunk_count = 0
        
        # LiveKit credentials
        self.url = os.getenv('LIVEKIT_URL')
        self.api_key = os.getenv('LIVEKIT_API_KEY')
        self.api_secret = os.getenv('LIVEKIT_API_SECRET')
    
    async def create_token(self, room_name: str, identity: str) -> str:
        """Create access token for the room"""
        token = (
            AccessToken(self.api_key, self.api_secret)
            .with_identity(identity)
            .with_grants(VideoGrants(room_join=True, room=room_name))
        )
        return token.to_jwt()
    
    async def ensure_room_exists(self, room_name: str):
        """Ensure the room exists"""
        api = LiveKitAPI(url=self.url, api_key=self.api_key, api_secret=self.api_secret)
        try:
            from livekit.api.room_service import CreateRoomRequest
            await api.room.create_room(CreateRoomRequest(name=room_name))
            logger.info(f"Room {room_name} created successfully")
        except Exception as e:
            if "already exists" not in str(e):
                logger.error(f"Failed to create room: {e}")
                raise
            logger.info(f"Room {room_name} already exists")
    
    async def handle_participant_connected(self, participant: rtc.Participant):
        """Handle new participant connection"""
        logger.info(f"Participant connected: {participant.identity}")
        self.participants[participant.identity] = participant
    
    async def handle_participant_disconnected(self, participant: rtc.Participant):
        """Handle participant disconnection"""
        logger.info(f"Participant disconnected: {participant.identity}")
        if participant.identity in self.participants:
            del self.participants[participant.identity]
        if participant.identity in self.audio_tracks:
            del self.audio_tracks[participant.identity]
    
    async def handle_track_subscribed(self, track: rtc.Track, publication: rtc.TrackPublication, participant: rtc.Participant):
        """Handle track subscription"""
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info(f"Audio track subscribed from {participant.identity}")
            await self.handle_audio_track(track, participant)
    
    def generate_sine_wave(self, frequency, duration, sample_rate=48000, amplitude=0.3):
        """Generate a sine wave audio frame"""
        import struct
        
        samples = int(sample_rate * duration)
        audio_data = []
        
        for i in range(samples):
            # Generate sine wave
            sample = amplitude * math.sin(2 * math.pi * frequency * i / sample_rate)
            # Convert to 16-bit PCM
            pcm_sample = int(sample * 32767)  # Scale to 16-bit range
            audio_data.extend(struct.pack('<h', pcm_sample))
        
        return bytes(audio_data)
    
    async def handle_audio_track(self, track: rtc.Track, participant: rtc.Participant):
        """Handle incoming audio track with simple echo"""
        logger.info(f"Starting audio echo for {participant.identity}")
        
        # Create a simple audio source for echo
        audio_source = rtc.AudioSource(
            sample_rate=48000,
            num_channels=1
        )
        
        # Create local audio track for echo
        local_track = rtc.LocalAudioTrack.create_audio_track(
            "echo",
            source=audio_source
        )
        self.audio_tracks[participant.identity] = local_track
        
        # Publish the echo track
        await self.room.local_participant.publish_track(local_track)
        logger.info(f"Echo track published for {participant.identity}")
        
        # Start a simple echo loop with audible tones
        asyncio.create_task(self.echo_loop(audio_source, participant.identity))
    
    async def echo_loop(self, audio_source, participant_identity):
        """Simple echo loop that generates audible tones"""
        logger.info(f"Starting echo loop for {participant_identity}")
        
        # Generate some test audio frames for echo
        sample_rate = 48000
        frame_duration = 0.1  # 100ms frames for better audio quality
        samples_per_frame = int(sample_rate * frame_duration)
        
        # Generate a sine wave frame
        sine_wave_data = self.generate_sine_wave(
            frequency=440,  # A4 note
            duration=frame_duration,
            sample_rate=sample_rate,
            amplitude=0.3
        )
        
        while participant_identity in self.participants:
            try:
                # Create audio frame from sine wave
                from livekit.rtc import AudioFrame
                frame = AudioFrame(
                    data=sine_wave_data,
                    sample_rate=sample_rate,
                    num_channels=1,
                    samples_per_channel=samples_per_frame
                )
                
                # Send frame to audio source
                await audio_source.capture_frame(frame)
                
                self.chunk_count += 1
                if self.chunk_count % 10 == 0:  # Log every 10 frames
                    logger.info(f"Echo frame #{self.chunk_count} sent for {participant_identity} (440Hz tone)")
                
                await asyncio.sleep(frame_duration)
                
            except Exception as e:
                logger.error(f"Error in echo loop: {e}")
                break
        
        logger.info(f"Echo loop ended for {participant_identity}")
    
    async def start(self, room_name: str = "echo_test"):
        """Start the echo server"""
        logger.info(f"Starting simple echo server in room: {room_name}")
        
        # Ensure room exists
        await self.ensure_room_exists(room_name)
        
        # Create access token
        token = await self.create_token(room_name, "echo_server")
        
        # Create room
        self.room = rtc.Room()
        
        # Handle participant events with synchronous callbacks
        def on_participant_connected(participant: rtc.Participant):
            asyncio.create_task(self.handle_participant_connected(participant))
        
        def on_participant_disconnected(participant: rtc.Participant):
            asyncio.create_task(self.handle_participant_disconnected(participant))
        
        def on_track_subscribed(track: rtc.Track, publication: rtc.TrackPublication, participant: rtc.Participant):
            asyncio.create_task(self.handle_track_subscribed(track, publication, participant))
        
        self.room.on("participant_connected", on_participant_connected)
        self.room.on("participant_disconnected", on_participant_disconnected)
        self.room.on("track_subscribed", on_track_subscribed)
        
        # Connect to room
        logger.info("Connecting to room...")
        await self.room.connect(self.url, token)
        logger.info("Connected to room!")
        
        # Keep the server running
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Echo server shutting down...")
        finally:
            if self.room:
                await self.room.disconnect()

async def main():
    echo_server = SimpleEchoServer()
    await echo_server.start()

if __name__ == "__main__":
    asyncio.run(main()) 