#!/usr/bin/env python3
"""
Генератор JWT токенов для LiveKit
"""

import argparse
import time
from typing import Optional
import jwt
import os


def generate_token(
    api_key: str,
    api_secret: str,
    room: str,
    identity: str,
    ttl_seconds: int = 3600,
    can_publish: bool = True,
    can_subscribe: bool = True
) -> str:
    """Генерирует JWT токен для LiveKit"""
    
    now = int(time.time())
    payload = {
        "iss": api_key,
        "sub": identity,
        "iat": now,
        "exp": now + ttl_seconds,
        "room": room,
        "permissions": {
            "roomJoin": True,
            "canPublish": can_publish,
            "canSubscribe": can_subscribe,
        }
    }
    
    return jwt.encode(payload, api_secret, algorithm="HS256")


def main():
    parser = argparse.ArgumentParser(description="Generate LiveKit JWT tokens")
    parser.add_argument("--api-key", default=os.getenv("LIVEKIT_API_KEY", "devkey"), 
                       help="LiveKit API key")
    parser.add_argument("--api-secret", default=os.getenv("LIVEKIT_API_SECRET", "secret"), 
                       help="LiveKit API secret")
    parser.add_argument("--room", default=os.getenv("LK_ROOM", "demo"), 
                       help="Room name")
    parser.add_argument("--identity", required=True, help="Participant identity")
    parser.add_argument("--ttl", type=int, default=3600, help="Token TTL in seconds")
    parser.add_argument("--no-publish", action="store_true", help="Disable publish permission")
    parser.add_argument("--no-subscribe", action="store_true", help="Disable subscribe permission")
    
    args = parser.parse_args()
    
    token = generate_token(
        api_key=args.api_key,
        api_secret=args.api_secret,
        room=args.room,
        identity=args.identity,
        ttl_seconds=args.ttl,
        can_publish=not args.no_publish,
        can_subscribe=not args.no_subscribe
    )
    
    print(f"🎟️  Token for {args.identity} in room '{args.room}':")
    print(token)
    print(f"\n📋 Copy this token to your client")
    print(f"🔗 Room URL: {os.getenv('LIVEKIT_URL', 'ws://localhost:7880')}")


if __name__ == "__main__":
    main()
