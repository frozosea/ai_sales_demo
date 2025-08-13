import asyncio
import yaml
from dotenv import load_dotenv
import os
from livekit.api import LiveKitAPI

load_dotenv()

async def register_agent():
    """Register the echo agent with LiveKit"""
    
    # Initialize LiveKit API
    api = LiveKitAPI(
        url=os.getenv('LIVEKIT_URL'),
        api_key=os.getenv('LIVEKIT_API_KEY'),
        api_secret=os.getenv('LIVEKIT_API_SECRET')
    )
    
    try:
        # List existing dispatches for a specific room
        room_name = "echo-room"
        print(f"Checking existing dispatches for room: {room_name}")
        try:
            dispatches = await api.agent_dispatch.list_dispatch(room_name)
            print(f"Existing dispatches: {[d.metadata.name for d in dispatches.dispatches]}")
        except Exception as e:
            print(f"Error listing dispatches: {e}")
        
        # Create dispatch for the agent
        print("Creating dispatch for echo agent...")
        try:
            from livekit.api import CreateDispatchRequest
            
            dispatch_request = CreateDispatchRequest(
                room_name=room_name,
                agent_name="echo-agent",
                agent_type="echo-agent"
            )
            
            result = await api.agent_dispatch.create_dispatch(dispatch_request)
            print("Dispatch created successfully!")
            print(f"Dispatch ID: {result.metadata.name}")
            
        except Exception as e:
            print(f"Error creating dispatch: {e}")
            print("Trying alternative approach...")
            
            # Try with simple dict
            try:
                result = await api.agent_dispatch.create_dispatch({
                    "room_name": room_name,
                    "agent_name": "echo-agent",
                    "agent_type": "echo-agent"
                })
                print("Dispatch created successfully with dict!")
            except Exception as e2:
                print(f"Alternative approach also failed: {e2}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Close the API client
        await api.aclose()

if __name__ == "__main__":
    asyncio.run(register_agent()) 