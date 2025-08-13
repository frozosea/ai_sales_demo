import asyncio
from typing import List, Optional, Dict, Any

from domain.models import SessionState
from domain.interfaces.cache import AbstractCache
from domain.interfaces.llm import AbstractConversationManager
from flow_engine.engine import FlowEngine
from intent_classifier.classifier import IntentClassifier
from stt_yandex.stt_yandex import YandexSTTStreamer
from tts_manager.manager import TTSManager


class Orchestrator:
    def __init__(
        self,
        call_id: str,
        flow_engine: FlowEngine,
        intent_classifier: IntentClassifier,
        llm_manager: AbstractConversationManager,
        tts_manager: TTSManager,
        stt_streamer: YandexSTTStreamer,
        cache: AbstractCache,
        neutral_fillers_keys: List[str],
        non_secure_response: str,
        dialogue_map: Dict[str, Any],
    ):
        self.call_id = call_id
        self.flow_engine = flow_engine
        self.intent_classifier = intent_classifier
        self.llm_manager = llm_manager
        self.tts_manager = tts_manager
        self.stt_streamer = stt_streamer
        self.cache = cache
        self.neutral_fillers_keys = neutral_fillers_keys
        self.non_secure_response = non_secure_response
        self.dialogue_map = dialogue_map

        self.session_state = SessionState(call_id=call_id)
        # self.metrics_logger = MetricsLogger(trace_id=call_id) # TODO: Implement MetricsLogger
        self.current_playback_task: Optional[asyncio.Task] = None
        self.call_ended = False

    async def run(self, inbound_stream, outbound_stream):
        """Главный метод, запускающий основной цикл диалога."""
        audio_chunk_queue = asyncio.Queue(maxsize=100)
        stt_response_queue = await self.stt_streamer.start_recognition(audio_chunk_queue)

        # Фонувую задачу, которая будет читать байты из inbound_stream и класть их в audio_chunk_queue
        inbound_stream_reader_task = asyncio.create_task(
            self._pipe_inbound_stream_to_stt(inbound_stream, audio_chunk_queue)
        )

        try:
            # 2. Запускает приветствие бота (первый ход).
            self.session_state.turn_state = 'BOT_TURN'
            initial_state_config = self.dialogue_map[self.session_state.current_state_id]
            print(f"Initial state config: {initial_state_config}")
            playlist_config = initial_state_config['system_response']['playlist']
            await self._play_audio_playlist(playlist_config, outbound_stream)

            # 4. Внутри цикла вызывает `await self._dialogue_loop(stt_response_queue, outbound_stream)`.
            await self._dialogue_loop(stt_response_queue, outbound_stream)
        finally:
            # 5. Использует `try…finally` для гарантированного вызова `self.shutdown()` в конце.
            await self.shutdown()
            inbound_stream_reader_task.cancel()
            await asyncio.gather(inbound_stream_reader_task, return_exceptions=True)


    async def _pipe_inbound_stream_to_stt(self, inbound_stream, audio_chunk_queue: asyncio.Queue):
        # This is a placeholder for how the inbound stream would be handled.
        # In a real scenario, this would read chunks from the telephony provider.
        async for chunk in inbound_stream:
            await audio_chunk_queue.put(chunk)
        await audio_chunk_queue.put(None)  # Signal end of stream


    async def _dialogue_loop(self, stt_response_queue, outbound_stream):
        """Приватный метод для одного полного цикла «вопрос‑ответ»."""
        while not self.call_ended:
            self.session_state.turn_state = 'USER_TURN'
            
            stt_result, error = await stt_response_queue.get()
            if error:
                # Handle STT error, maybe log and continue or hang up
                print(f"STT Error: {error}")
                continue

            if not stt_result:
                # End of STT stream
                break

            # TODO: Add metrics logging t1, t2

            expected_intents = list(self.dialogue_map.get(self.session_state.current_state_id, {}).get("transitions", {}).keys())

            if not stt_result.is_final:
                # 5. Обработка `partial` результатов
                intent_result = await self.intent_classifier.classify_intent(
                    text=stt_result.text,
                    expected_intents=expected_intents,
                    previous_leader=self.session_state.previous_intent_leader
                )
                if intent_result:
                    self.session_state.previous_intent_leader = intent_result.current_leader
                continue

            # 6. Обработка `final` результатов
            final_text = stt_result.text
            intent_result = await self.intent_classifier.classify_intent(
                text=final_text,
                expected_intents=expected_intents,
                previous_leader=self.session_state.previous_intent_leader
            )

            playlist_to_play = None

            if intent_result:
                # Сценарий
                # TODO: Check for entities
                flow_result = self.flow_engine.process_event(
                    session_state=self.session_state, # Pass the object directly
                    intent_id=intent_result.intent_id
                )
                # Update session state from flow engine result
                self.session_state.current_state_id = flow_result.next_state
                self.session_state.task_stack = flow_result.task_stack
                # ... any other variables ...

                new_state_config = self.dialogue_map.get(self.session_state.current_state_id, {})
                playlist_to_play = new_state_config.get("system_response", {}).get("playlist")

            else:
                # Не по сценарию -> LLM
                faq_answer = await self.intent_classifier.find_faq_answer(text=final_text)
                if faq_answer:
                    # Found in FAQ, construct a simple playlist
                    playlist_to_play = [{"type": "tts", "text_template": faq_answer.answer_text}]
                else:
                    await self._handle_unscripted_flow(final_text, outbound_stream)
                    # _handle_unscripted_flow manages its own playback, so we can continue the loop
                    continue

            if playlist_to_play:
                self.session_state.turn_state = 'BOT_TURN'
                await self._play_audio_playlist(playlist_to_play, outbound_stream)

            # Check if we need to end the call
            current_state_config = self.dialogue_map.get(self.session_state.current_state_id, {})
            if current_state_config.get("action") == "END_CALL":
                self.call_ended = True

            if intent_result:
                self.session_state.previous_intent_leader = intent_result.current_leader
            else:
                self.session_state.previous_intent_leader = None
    
    async def _play_audio_playlist(self, playlist_config: List[Dict[str, Any]], outbound_stream):
        """Умный проигрыватель аудио‑ответов."""
        
        async def play_item(item: Dict[str, Any]):
            item_type = item.get("type")
            if item_type == "cache" or item_type == "filler":
                key = item.get("key")
                audio_chunks = await self.cache.get(key)
                if audio_chunks:
                    for chunk in audio_chunks:
                        await outbound_stream.write(chunk)
            elif item_type == "tts":
                text_template = item.get("text_template", "")
                # Simple templating for now
                text_to_speak = text_template.format(session=self.session_state)
                async for chunk in self.tts_manager.stream_static_text(text_to_speak):
                    await outbound_stream.write(chunk)

        playback_tasks = [play_item(item) for item in playlist_config]
        self.current_playback_task = asyncio.gather(*playback_tasks)
        
        try:
            await self.current_playback_task
        except asyncio.CancelledError:
            # This is expected if a barge-in happens
            pass
        finally:
            self.current_playback_task = None


    async def _handle_unscripted_flow(self, text: str, outbound_stream):
        """Handles the flow when the user input is not part of the script."""
        try:
            text_input_queue, audio_output_queue = await self.tts_manager.start_llm_stream()
        except Exception as e: # Assuming a generic TTSConnectionError
            # TODO: log the error
            await self._play_audio_playlist([{"type": "cache", "key": self.non_secure_response}], outbound_stream)
            return

        llm_text_stream = self.llm_manager.process_user_turn(text)

        async def _pipe_llm_to_tts(llm_stream, tts_queue):
            first_chunk = True
            async for chunk in llm_stream:
                if first_chunk:
                    first_chunk = False
                    if not chunk.is_safe:
                        # Abort LLM generation and play safe response
                        # TODO: Implement abort_generation in LLMManager
                        # await self.llm_manager.abort_generation()
                        await self._play_audio_playlist([{"type": "cache", "key": self.non_secure_response}], outbound_stream)
                        return 
                
                await tts_queue.put(chunk.text_chunk)
            await tts_queue.put(None) # Signal end of text

        async def _stream_audio_from_queue(audio_queue, stream):
            while True:
                chunk = await audio_queue.get()
                if chunk is None:
                    break
                await stream.write(chunk)
        
        pipe_task = asyncio.create_task(
            _pipe_llm_to_tts(llm_text_stream, text_input_queue)
        )
        playback_task = asyncio.create_task(
            _stream_audio_from_queue(audio_output_queue, outbound_stream)
        )
        
        self.current_playback_task = playback_task
        
        await asyncio.gather(pipe_task, playback_task)


    async def shutdown(self):
        """Корректное завершение работы."""
        # TODO: Add final metrics logging
        if self.llm_manager:
            await self.llm_manager.shutdown()
        if self.stt_streamer:
            await self.stt_streamer.stop_recognition()


# "Фабрика" для создания и настройки экземпляра
async def create_orchestrator_instance(
    call_id: str,
    flow_engine: FlowEngine,
    intent_classifier: IntentClassifier,
    llm_manager: AbstractConversationManager,
    tts_manager: TTSManager,
    stt_streamer: YandexSTTStreamer,
    cache: AbstractCache,
    neutral_fillers_keys: List[str],
    non_secure_response: str,
    dialogue_map: Dict[str, Any],
) -> Orchestrator:
    """
    Creates and initializes an instance of the Orchestrator.
    In a real application, this would also handle asynchronous setup of connections.
    """
    orchestrator = Orchestrator(
        call_id=call_id,
        flow_engine=flow_engine,
        intent_classifier=intent_classifier,
        llm_manager=llm_manager,
        tts_manager=tts_manager,
        stt_streamer=stt_streamer,
        cache=cache,
        neutral_fillers_keys=neutral_fillers_keys,
        non_secure_response=non_secure_response,
        dialogue_map=dialogue_map,
    )
    # According to context, here we would call something like:
    # await orchestrator._setup_connections()
    # This is where connections for TTS, etc., would be established.
    return orchestrator
