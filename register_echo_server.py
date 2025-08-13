import os
import asyncio
from dotenv import load_dotenv
from livekit.api import LiveKitAPI
from livekit.api.agent_dispatch_service import CreateAgentDispatchRequest

load_dotenv()

async def register_echo_server():
    """Register the echo server with LiveKit for the echo_test room"""
    
    # Initialize LiveKit API
    api = LiveKitAPI(
        url=os.getenv('LIVEKIT_URL'),
        api_key=os.getenv('LIVEKIT_API_KEY'),
        api_secret=os.getenv('LIVEKIT_API_SECRET')
    )
    
    # Create dispatch request for echo server
    dispatch_request = CreateAgentDispatchRequest(
        room_name="echo_test",  # Same room as token server
        agent_id="echo_server",
        agent_name="Echo Server",
        agent_metadata={
            "description": "Simple echo server with interruption logic"
        }
    )
    
    try:
        # Register the agent
        response = await api.agent_dispatch.create_agent_dispatch(dispatch_request)
        print(f"Echo server registered successfully!")
        print(f"Dispatch ID: {response.dispatch_id}")
        print(f"Room: {response.room_name}")
        print(f"Agent ID: {response.agent_id}")
        
    except Exception as e:
        print(f"Failed to register echo server: {e}")
        if "already exists" in str(e):
            print("Echo server already registered for this room")
        else:
            raise

if __name__ == "__main__":
    asyncio.run(register_echo_server()) 