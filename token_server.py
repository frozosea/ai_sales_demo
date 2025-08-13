from quart import Quart, jsonify, send_from_directory
from dotenv import load_dotenv
import os
from livekit.api import LiveKitAPI, AccessToken, VideoGrants, CreateRoomRequest
import logging
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('token_server')

app = Quart(__name__)
load_dotenv()

# Load LiveKit credentials from environment variables
api_key = os.getenv('LIVEKIT_API_KEY')
api_secret = os.getenv('LIVEKIT_API_SECRET')
livekit_url = os.getenv('LIVEKIT_URL')

logger.info(f"LiveKit URL: {livekit_url}")
logger.info(f"API Key present: {'Yes' if api_key else 'No'}")
logger.info(f"API Secret present: {'Yes' if api_secret else 'No'}")

# Initialize LiveKit API client lazily
api_client = None

def get_api_client():
    global api_client
    if api_client is None:
        logger.info("Creating new LiveKit API client")
        api_client = LiveKitAPI(url=livekit_url, api_key=api_key, api_secret=api_secret)
    return api_client

@app.route('/')
async def serve_client():
    return await send_from_directory('.', 'echo_client.html')

@app.route('/token')
async def get_token():
    try:
        if not all([api_key, api_secret, livekit_url]):
            missing = [
                k for k, v in {
                    'LIVEKIT_API_KEY': api_key,
                    'LIVEKIT_API_SECRET': api_secret,
                    'LIVEKIT_URL': livekit_url
                }.items() if not v
            ]
            logger.error(f"Missing credentials: {missing}")
            return jsonify({
                'error': 'LiveKit credentials not configured',
                'missing': missing
            }), 500
        
        # Ensure room exists
        room_name = "echo_test"
        client = get_api_client()
        logger.info(f"Creating/ensuring room: {room_name}")
        
        try:
            # Try to create room using the room service
            await client.room.create_room(CreateRoomRequest(name=room_name))
            logger.info("Room created successfully")
        except Exception as e:
            if "already exists" not in str(e):
                logger.error(f"Failed to create room: {str(e)}")
                raise
            logger.info("Room already exists")
        
        # Create access token
        logger.info("Generating access token")
        token = (
            AccessToken(api_key, api_secret)
            .with_identity("echo_test_user")
            .with_grants(VideoGrants(room_join=True, room=room_name))
        )
        
        token_jwt = token.to_jwt()
        logger.info("Token generated successfully")
        
        # Return token and URL
        return jsonify({
            'token': token_jwt,
            'url': livekit_url,
            'room': room_name
        })
    
    except Exception as e:
        logger.error(f"Error in get_token: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'error': 'Failed to create token',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True) 