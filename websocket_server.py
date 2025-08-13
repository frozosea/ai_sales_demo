import asyncio
import logging
from dotenv import load_dotenv
import os
from livekit import rtc
from livekit.rtc import Room, LocalAudioTrack, AudioSource
import websockets

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("websocket_server")

# Load environment variables
load_dotenv()
LIVEKIT_URL = os.getenv('LIVEKIT_URL')
LIVEKIT_API_KEY = os.getenv('LIVEKIT_API_KEY')
LIVEKIT_API_SECRET = os.getenv('LIVEKIT_API_SECRET')

# Audio settings
SAMPLE_RATE = 48000
NUM_CHANNELS = 1

class AudioStreamer:
    def __init__(self, room_name: str):
        self.room_name = room_name
        self.room = None
        self.audio_source = None
        self.audio_track = None
        self.running = True
        
    async def setup_room(self):
        """Initialize LiveKit room and audio components"""
        logger.info("Setting up LiveKit room...")
        
        # Create room
        self.room = Room()
        
        # Create audio source
        self.audio_source = AudioSource(
            sample_rate=SAMPLE_RATE,
            num_channels=NUM_CHANNELS
        )
        
        # Handle room events
        @self.room.on("track_subscribed")
        async def on_track_subscribed(track, publication, participant):
            logger.info(f"Track subscribed: {track.kind} from {participant.identity}")
            
        @self.room.on("track_unsubscribed")
        async def on_track_unsubscribed(track, publication, participant):
            logger.info(f"Track unsubscribed: {track.kind} from {participant.identity}")
            
        @self.room.on("participant_connected")
        async def on_participant_connected(participant):
            logger.info(f"Participant connected: {participant.identity}")
            
        @self.room.on("participant_disconnected")
        async def on_participant_disconnected(participant):
            logger.info(f"Participant disconnected: {participant.identity}")

    async def connect_room(self, token: str):
        """Connect to LiveKit room"""
        logger.info(f"Connecting to room: {self.room_name}")
        await self.room.connect(LIVEKIT_URL, token)
        
        # Create and publish audio track
        self.audio_track = LocalAudioTrack.create_audio_track(
            "microphone",
            self.audio_source
        )
        await self.room.local_participant.publish_track(self.audio_track)
        logger.info("Audio track published")

    async def process_audio(self, websocket):
        """Process audio data from WebSocket"""
        logger.info("Starting audio processing...")
        try:
            while self.running:
                # Receive audio data from WebSocket
                data = await websocket.recv()
                logger.debug(f"Received audio chunk: {len(data)} bytes")
                
                # Create audio frame and send to LiveKit
                frame = rtc.AudioFrame(
                    data=data,
                    sample_rate=SAMPLE_RATE,
                    num_channels=NUM_CHANNELS,
                    samples_per_channel=len(data) // (2 * NUM_CHANNELS)  # 16-bit audio
                )
                await self.audio_source.capture_frame(frame)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
        finally:
            self.running = False

async def handle_connection(websocket):
    """Handle WebSocket connection"""
    try:
        # Get room name and token from client
        message = await websocket.recv()
        data = eval(message)  # Simple eval for demo, use json in production
        room_name = data['room']
        token = data['token']
        
        logger.info(f"Client connecting to room: {room_name}")
        
        # Create audio streamer
        streamer = AudioStreamer(room_name)
        await streamer.setup_room()
        await streamer.connect_room(token)
        
        # Start audio processing
        await streamer.process_audio(websocket)
        
    except Exception as e:
        logger.error(f"Connection error: {e}")
    finally:
        if hasattr(streamer, 'room') and streamer.room:
            await streamer.room.disconnect()

async def main():
    """Start WebSocket server"""
    logger.info("Starting WebSocket server...")
    async with websockets.serve(handle_connection, "localhost", 8765):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main()) 