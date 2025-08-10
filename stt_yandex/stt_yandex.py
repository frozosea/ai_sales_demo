import asyncio
import json
import logging
import time
import uuid
from typing import AsyncGenerator, Optional, Tuple

import grpc

from domain.stt_models import STTConfig, STTConnectionError, STTResponse
from yandex.cloud.ai.stt.v3 import stt_pb2
from yandex.cloud.ai.stt.v3 import stt_service_pb2_grpc
from .connection_manager import ConnectionManager, ConnectionManagerConfig


def jlog(level, event, **kwargs):
    logging.log(level, json.dumps({"event": event, **kwargs}))


class YandexSTTStreamer:
    @classmethod
    def initialize_pool(
        cls,
        config: STTConfig,
        iam_token: str,
        folder_id: str,
        warmup_interval_sec: float = 5.0,
        max_connections: int = 10
    ):
        """Initializes the connection manager. Call this once at startup."""
        manager_config = ConnectionManagerConfig(
            warmup_interval_sec=warmup_interval_sec,
            max_connections=max_connections
        )
        ConnectionManager.initialize(config, iam_token, folder_id, manager_config)
    
    @classmethod
    async def close_pool(cls):
        """Closes the connection manager. Call this at shutdown."""
        await ConnectionManager.get_instance().close()

    def __init__(self, config: STTConfig, iam_token: str, folder_id: str):
        self.config = config
        self._iam_token = iam_token
        self._folder_id = folder_id
        self._connection_id: Optional[str] = None
        self._connection = None
        self._send_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._trace_id = uuid.uuid4().hex
        
        jlog(logging.INFO, "stt_conn_init", trace_id=self._trace_id)

    async def start_recognition(
        self, audio_chunk_queue: asyncio.Queue[bytes | None]
    ) -> asyncio.Queue[Tuple[STTResponse | None, STTConnectionError | None]]:
        t_start = time.monotonic()
        jlog(logging.DEBUG, "stt_handshake_start")
        
        # Get a warmed-up connection from the manager
        manager = ConnectionManager.get_instance()
        self._connection_id, self._connection = await manager.acquire_connection()
        
        response_queue = asyncio.Queue()

        async def request_generator() -> AsyncGenerator[stt_pb2.StreamingRequest, None]:
            # Always send config first for each new stream
            audio_format = (
                stt_pb2.AudioFormatOptions(
                    container_audio=stt_pb2.ContainerAudio(
                        container_audio_type=stt_pb2.ContainerAudio.ContainerAudioType.OGG_OPUS
                    )
                ) if self.config.container_audio
                else stt_pb2.AudioFormatOptions(
                    raw_audio=stt_pb2.RawAudio(
                        audio_encoding=stt_pb2.RawAudio.AudioEncoding.Value(self.config.audio_encoding),
                        sample_rate_hertz=self.config.sample_rate_hertz,
                        audio_channel_count=1,
                    )
                )
            )
            
            recognition_options = stt_pb2.StreamingOptions(
                recognition_model=stt_pb2.RecognitionModelOptions(
                    audio_format=audio_format,
                    text_normalization=stt_pb2.TextNormalizationOptions(
                        text_normalization=stt_pb2.TextNormalizationOptions.TextNormalization.TEXT_NORMALIZATION_ENABLED,
                        profanity_filter=self.config.profanity_filter,
                        literature_text=False,
                    ),
                    language_restriction=stt_pb2.LanguageRestrictionOptions(
                        restriction_type=stt_pb2.LanguageRestrictionOptions.LanguageRestrictionType.WHITELIST,
                        language_code=[self.config.language_code],
                    ),
                    audio_processing_type=stt_pb2.RecognitionModelOptions.AudioProcessingType.REAL_TIME
                )
            )
            
            t_config_send = time.monotonic()
            yield stt_pb2.StreamingRequest(session_options=recognition_options)
            t_config_sent = time.monotonic()
            jlog(logging.DEBUG, "stt_config_sent", trace_id=self._trace_id, duration_ms=round((t_config_sent - t_config_send) * 1000, 2))
            
            # Then stream audio
            chunk_counter = 0
            while True:
                t_queue_get = time.monotonic()
                chunk = await audio_chunk_queue.get()
                t_queue_got = time.monotonic()
                
                if chunk is None:
                    break
                    
                t_chunk_send = time.monotonic()
                yield stt_pb2.StreamingRequest(chunk=stt_pb2.AudioChunk(data=chunk))
                t_chunk_sent = time.monotonic()
                
                chunk_counter += 1
                jlog(logging.DEBUG, "stt_chunk_sent", 
                     trace_id=self._trace_id,
                     chunk_idx=chunk_counter,
                     queue_wait_ms=round((t_queue_got - t_queue_get) * 1000, 2),
                     send_duration_ms=round((t_chunk_sent - t_chunk_send) * 1000, 2),
                     chunk_size=len(chunk))

        metadata = (
            ("authorization", f"Bearer {self._iam_token}"),
            ("x-folder-id", self._folder_id),
            ("x-client-request-id", self._trace_id),
            ("x-normalize-partials", "true" if self.config.normalize_partials else "false"),
        )
        
        grpc_stream = self._connection.stub.RecognizeStreaming(request_generator(), metadata=metadata)

        self._receive_task = asyncio.create_task(
            self._receive_responses(grpc_stream, response_queue)
        )
        
        t_finish = time.monotonic()
        jlog(logging.INFO, "stt_handshake_finish", ms=round((t_finish - t_start) * 1000, 2))

        return response_queue

    async def stop_recognition(self):
        jlog(logging.INFO, "stt_stop_requested", trace_id=self._trace_id)
        
        tasks_to_cancel = []
        if self._send_task and not self._send_task.done():
            self._send_task.cancel()
            tasks_to_cancel.append(self._send_task)
            
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            tasks_to_cancel.append(self._receive_task)

        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

        # Release connection back to manager
        if self._connection_id:
            await ConnectionManager.get_instance().release_connection(self._connection_id)
            self._connection_id = None
            self._connection = None
            
        jlog(logging.INFO, "stt_stopped", trace_id=self._trace_id)

    async def _receive_responses(
        self,
        stream: grpc.aio.StreamStreamCall,
        response_queue: asyncio.Queue,
    ):
        utter_idx = 0
        try:
            async for response in stream:
                t_parse_start = time.monotonic()
                event_type = response.WhichOneof("Event")
                
                if event_type == "partial":
                    text = response.partial.alternatives[0].text if response.partial.alternatives else ""
                    resp = STTResponse(text, False, 0.5, utter_idx)
                    t_parse_end = time.monotonic()
                    jlog(logging.DEBUG, "stt_partial_parsed", 
                         trace_id=self._trace_id,
                         parse_duration_ms=round((t_parse_end - t_parse_start) * 1000, 2),
                         text_len=len(text))
                    await response_queue.put((resp, None))
                    
                elif event_type == "final":
                    text = response.final.alternatives[0].text if response.final.alternatives else ""
                    resp = STTResponse(text, True, 1.0, utter_idx)
                    t_parse_end = time.monotonic()
                    jlog(logging.DEBUG, "stt_final_parsed",
                         trace_id=self._trace_id,
                         parse_duration_ms=round((t_parse_end - t_parse_start) * 1000, 2),
                         text_len=len(text))
                    await response_queue.put((resp, None))
                    utter_idx += 1
                    
                elif event_type == "final_refinement":
                    text = response.final_refinement.normalized_text.alternatives[0].text if response.final_refinement.normalized_text.alternatives else ""
                    resp = STTResponse(text, True, 1.0, utter_idx - 1)
                    t_parse_end = time.monotonic()
                    jlog(logging.DEBUG, "stt_refinement_parsed",
                         trace_id=self._trace_id,
                         parse_duration_ms=round((t_parse_end - t_parse_start) * 1000, 2),
                         text_len=len(text))
                    await response_queue.put((resp, None))

        except grpc.aio.AioRpcError as e:
            jlog(logging.ERROR, "stt_recv_error", trace_id=self._trace_id, error=str(e))
            await response_queue.put((None, STTConnectionError(f"gRPC receive error: {e}")))
        finally:
            jlog(logging.INFO, "stt_stream_closed", trace_id=self._trace_id)
            await response_queue.put((None, None))

if __name__ == "__main__":
    import os
    import yaml
    from dotenv import load_dotenv

    load_dotenv()

    async def sandbox_main():
        logging.basicConfig(level=logging.INFO, format='%(message)s')
        
        iam_token = os.getenv("YC_IAM_TOKEN")
        folder_id = os.getenv("YC_FOLDER_ID")

        if not iam_token or not folder_id:
            jlog(logging.CRITICAL, "auth_creds_missing", details="YC_IAM_TOKEN or YC_FOLDER_ID is not set.")
            return

        with open("configs/stt_config.yml", "r") as f:
            config_data = yaml.safe_load(f)

        stt_config = STTConfig(**config_data)
        
        # Initialize pool with custom warmup interval
        YandexSTTStreamer.initialize_pool(
            stt_config,
            iam_token,
            folder_id,
            warmup_interval_sec=5.0,
            max_connections=2
        )

        streamer = YandexSTTStreamer(stt_config, iam_token, folder_id)

        audio_queue = asyncio.Queue(maxsize=50)
        response_queue = await streamer.start_recognition(audio_queue)

        async def response_handler():
            while True:
                resp, err = await response_queue.get()
                if err:
                    jlog(logging.ERROR, "sandbox_response_error", error=str(err))
                    break
                if resp:
                    jlog(logging.INFO, "sandbox_response", **resp.__dict__)
                if resp and resp.is_final and resp.text == "": # Heuristic for end
                    break

        handler_task = asyncio.create_task(response_handler())

        # Simulate no audio being sent, just connection setup and teardown
        await audio_queue.put(None) 
        
        await handler_task
        await streamer.stop_recognition()
        
        # Close pool
        await YandexSTTStreamer.close_pool()
        
        jlog(logging.INFO, "sandbox_finished")

    asyncio.run(sandbox_main())
