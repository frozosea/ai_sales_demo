from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import grpc
from yandex.cloud.ai.stt.v3 import stt_pb2, stt_service_pb2_grpc

from domain.stt_models import STTConfig, STTConnectionError

def jlog(level, event, **kwargs):
    logging.log(level, json.dumps({"event": event, **kwargs}))

@dataclass
class WarmConnection:
    channel: grpc.aio.Channel
    stub: stt_service_pb2_grpc.RecognizerStub
    config_sent: bool = False
    last_used: float = 0.0
    in_use: bool = False

class STTConnectionPool:
    def __init__(
        self,
        config: STTConfig,
        iam_token: str,
        folder_id: str,
        max_connections: int = 10,
        max_idle_time: float = 300.0,  # 5 minutes
    ):
        self.config = config
        self._iam_token = iam_token
        self._folder_id = folder_id
        self.max_connections = max_connections
        self.max_idle_time = max_idle_time
        
        self._connections: Dict[str, WarmConnection] = {}
        self._lock = asyncio.Lock()
        
        # Start connection cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_idle_connections())
    
    async def _create_connection(self) -> Tuple[str, WarmConnection]:
        """Creates a new connection with channel and stub."""
        connection_id = uuid.uuid4().hex
        
        t_start = time.monotonic()
        jlog(logging.INFO, "stt_pool_connection_start", connection_id=connection_id)
        
        creds = grpc.ssl_channel_credentials()
        channel_options = [
            ('grpc.keepalive_time_ms', 20000),
            ('grpc.keepalive_timeout_ms', 10000),
            ('grpc.http2.max_pings_without_data', 0),
            ('grpc.max_send_message_length', 10 * 1024 * 1024),
            ('grpc.max_receive_message_length', 10 * 1024 * 1024),
        ]
        
        channel = grpc.aio.secure_channel(
            self.config.endpoint, creds, options=channel_options
        )
        stub = stt_service_pb2_grpc.RecognizerStub(channel)
        
        conn = WarmConnection(
            channel=channel,
            stub=stub,
            config_sent=False,
            last_used=time.monotonic(),
            in_use=False
        )
        
        t_finish = time.monotonic()
        jlog(
            logging.INFO,
            "stt_pool_connection_ready",
            connection_id=connection_id,
            duration_ms=round((t_finish - t_start) * 1000, 2),
        )
        
        return connection_id, conn
    
    async def _warm_up_connection(self, connection_id: str, conn: WarmConnection) -> None:
        """Warms up a connection by sending test audio."""
        if conn.config_sent:
            return
            
        t_start = time.monotonic()
        jlog(logging.INFO, "stt_pool_warmup_start", connection_id=connection_id)
        
        try:
            # Create test audio (200ms of silence)
            sample_rate = self.config.sample_rate_hertz
            duration_ms = 200
            num_samples = int(sample_rate * duration_ms / 1000)
            silence_chunk = b'\x00' * (num_samples * 2)  # 2 bytes per sample for 16-bit PCM
            
            # Create config for warmup
            audio_format = stt_pb2.AudioFormatOptions(
                raw_audio=stt_pb2.RawAudio(
                    audio_encoding=stt_pb2.RawAudio.AudioEncoding.LINEAR16_PCM,
                    sample_rate_hertz=sample_rate,
                    audio_channel_count=1,
                )
            )
            
            recognition_options = stt_pb2.StreamingOptions(
                recognition_model=stt_pb2.RecognitionModelOptions(
                    audio_format=audio_format,
                    text_normalization=stt_pb2.TextNormalizationOptions(
                        text_normalization=stt_pb2.TextNormalizationOptions.TextNormalization.TEXT_NORMALIZATION_ENABLED,
                        profanity_filter=False,
                        literature_text=False,
                    ),
                    language_restriction=stt_pb2.LanguageRestrictionOptions(
                        restriction_type=stt_pb2.LanguageRestrictionOptions.LanguageRestrictionType.WHITELIST,
                        language_code=[self.config.language_code],
                    ),
                    audio_processing_type=stt_pb2.RecognitionModelOptions.AudioProcessingType.REAL_TIME
                )
            )
            
            async def warmup_generator():
                yield stt_pb2.StreamingRequest(session_options=recognition_options)
                yield stt_pb2.StreamingRequest(chunk=stt_pb2.AudioChunk(data=silence_chunk))
            
            metadata = (
                ("authorization", f"Bearer {self._iam_token}"),
                ("x-folder-id", self._folder_id),
                ("x-client-request-id", f"warmup-{connection_id}"),
                ("x-normalize-partials", "true"),
            )
            
            # Send warmup request
            stream = conn.stub.RecognizeStreaming(warmup_generator(), metadata=metadata)
            async for _ in stream:
                pass  # Consume responses but ignore them
            
            conn.config_sent = True
            
            t_finish = time.monotonic()
            jlog(
                logging.INFO,
                "stt_pool_warmup_complete",
                connection_id=connection_id,
                duration_ms=round((t_finish - t_start) * 1000, 2),
            )
            
        except Exception as e:
            jlog(logging.ERROR, "stt_pool_warmup_error", connection_id=connection_id, error=str(e))
            raise
    
    async def acquire(self) -> Tuple[str, WarmConnection]:
        """Acquires a warmed-up connection from the pool."""
        async with self._lock:
            # Try to find an available connection
            for conn_id, conn in self._connections.items():
                if not conn.in_use:
                    conn.in_use = True
                    conn.last_used = time.monotonic()
                    return conn_id, conn
            
            # Create new connection if pool not full
            if len(self._connections) < self.max_connections:
                conn_id, conn = await self._create_connection()
                await self._warm_up_connection(conn_id, conn)
                conn.in_use = True
                conn.last_used = time.monotonic()
                self._connections[conn_id] = conn
                return conn_id, conn
            
            # Wait for a connection to become available
            while True:
                for conn_id, conn in self._connections.items():
                    if not conn.in_use:
                        conn.in_use = True
                        conn.last_used = time.monotonic()
                        return conn_id, conn
                await asyncio.sleep(0.1)
    
    async def release(self, connection_id: str) -> None:
        """Releases a connection back to the pool."""
        async with self._lock:
            if connection_id in self._connections:
                conn = self._connections[connection_id]
                conn.in_use = False
                conn.last_used = time.monotonic()
    
    async def _cleanup_idle_connections(self) -> None:
        """Periodically cleans up idle connections."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                async with self._lock:
                    now = time.monotonic()
                    to_remove = []
                    
                    for conn_id, conn in self._connections.items():
                        if (not conn.in_use and 
                            (now - conn.last_used) > self.max_idle_time):
                            to_remove.append(conn_id)
                    
                    for conn_id in to_remove:
                        conn = self._connections.pop(conn_id)
                        await conn.channel.close()
                        jlog(logging.INFO, "stt_pool_connection_closed", connection_id=conn_id)
                        
            except Exception as e:
                jlog(logging.ERROR, "stt_pool_cleanup_error", error=str(e))
    
    async def close(self) -> None:
        """Closes all connections in the pool."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        async with self._lock:
            for conn_id, conn in self._connections.items():
                try:
                    await conn.channel.close()
                    jlog(logging.INFO, "stt_pool_connection_closed", connection_id=conn_id)
                except Exception as e:
                    jlog(logging.ERROR, "stt_pool_close_error", connection_id=conn_id, error=str(e))
            self._connections.clear() 