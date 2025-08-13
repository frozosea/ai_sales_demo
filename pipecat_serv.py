# server.py
import asyncio
import logging
import time

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.transports.network.websocket_server import (
    WebsocketServerParams,
    WebsocketServerTransport,
)
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.audio.vad.vad_analyzer import VADState
from pipecat.frames.frames import Frame, AudioRawFrame
from pipecat.processors.frame_processor import FrameProcessor

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
logging.getLogger("pipecat").setLevel(logging.WARNING)
logger = logging.getLogger("pipecat-app")
logger.setLevel(logging.INFO)

class EchoProcessor(FrameProcessor):
    def __init__(self):
        super().__init__()
        self.is_echoing = True
        self.last_activity = time.time()
        self.activity_threshold = 0.5
        self.vad_state = VADState.QUIET
        
    async def process_frame(self, frame: Frame, direction):
        # Все служебные фреймы и фреймы, идущие к пользователю, просто пропускаем

        # Ловим VAD-фреймы, чтобы изменить наше состояние
        if hasattr(frame, 'vad_state'):
            if frame.state == VADState.SPEAKING:
                if not self.is_echoing:
                    logger.info("🎤 Пользователь говорит, ВКЛЮЧАЮ эхо.")
                    self.is_echoing = True
            elif frame.state == VADState.QUIET:
                if self.is_echoing:
                    logger.info("🤫 Пользователь замолчал, ВЫКЛЮЧАЮ эхо.")
                    self.is_echoing = False
            # VAD-фреймы не нужно отправлять обратно, они служебные
            return

        if self.is_echoing:
                # Если эхо включено, отправляем аудио обратно пользователю
                await self.push_frame(frame, direction)
        #

async def main():
    # Создаем VAD анализатор
    vad_analyzer = SileroVADAnalyzer()
    
    # Создаем эхо процессор
    echo_processor = EchoProcessor()
    
    transport = WebsocketServerTransport(
        host="localhost",
        port=8765,
        params=WebsocketServerParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=vad_analyzer,
        ),
    )

    # Обработчики подключения
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client_id):
        logger.info(f"✅ Клиент подключился: {client_id}")
        logger.info("🎤 Эхо сервер с перебиванием готов!")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client_id):
        logger.info(f"❌ Клиент отключился: {client_id}")

    # Пайплайн с эхо процессором
    pipeline = Pipeline([
        transport.input(),
        echo_processor,
        transport.output(),
    ])

    runner = PipelineRunner()
    task = PipelineTask(pipeline)
    await runner.run(task)

if __name__ == "__main__":
    logger.info("Сервер запущен на ws://localhost:8765/ws")
    logger.info("🔊 Эхо сервер с логикой перебивания")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Сервер остановлен")