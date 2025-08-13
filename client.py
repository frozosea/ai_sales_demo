# client.py
import asyncio
import logging
import signal

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.transports.network.websocket_client import (
    WebsocketClientParams,
    WebsocketClientTransport,
)
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.serializers.protobuf import ProtobufFrameSerializer

logging.basicConfig(level=logging.INFO)
logging.getLogger("pipecat").setLevel(logging.WARNING)
logger = logging.getLogger("pipecat-client")
logger.setLevel(logging.INFO)

# Глобальная переменная для контроля работы
running = True

def signal_handler(signum, frame):
    global running
    logger.info("Получен сигнал остановки...")
    running = False

async def main():
    global running
    
    # Устанавливаем обработчик сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    uri = "ws://localhost:8765/ws"

    # Создаем транспорт
    transport = WebsocketClientTransport(
        uri=uri,
        params=WebsocketClientParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            serializer=ProtobufFrameSerializer(),
            add_wav_header=True,  # Optional WAV headers
        ),
    )

    # Пайплайн с правильной структурой input -> output
    pipeline = Pipeline([
        transport.input(),
        transport.output(),
    ])

    @transport.event_handler("on_connected")
    async def on_connected(transport, websocket):
        logger.info(f"✅ Подключено к {uri}")
        logger.info("🎤 Говорите в микрофон для тестирования эхо с перебиванием")

    @transport.event_handler("on_disconnected")
    async def on_disconnected(transport, websocket):
        logger.info(f"❌ Отключено от {uri}")
        if running:
            logger.info("🔄 Попытка переподключения...")


    runner = PipelineRunner()
    task = PipelineTask(pipeline)
    
    try:
        while running:
            try:
                await runner.run(task)
            except Exception as e:
                logger.error(f"Ошибка в пайплайне: {e}")
                if running:
                    logger.info("🔄 Перезапуск через 5 секунд...")
                    await asyncio.sleep(5)
                else:
                    break
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Клиент остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        running = False