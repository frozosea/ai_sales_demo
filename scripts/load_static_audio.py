
import asyncio
import argparse
import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path to allow imports from other modules
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from cache.cache import RedisCacheManager
from infra.redis_config import RedisConfig

# Setup basic logging
# from infra.logging import setup_logging
# setup_logging()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def main(key: str, wav_filepath: str):
    """
    Connects to Redis, loads a WAV file, chunks it, and stores it in the cache.
    """
    if not os.path.exists(wav_filepath):
        logger.error(f"Audio file not found at: {wav_filepath}")
        return

    # Assuming RedisConfig can be instantiated from environment variables or a config file
    redis_config = RedisConfig()
    cache_manager = RedisCacheManager(config=redis_config)

    try:
        await cache_manager.connect()
        success = await cache_manager.load_and_set_audio(key, wav_filepath)
        if success:
            logger.info(f"Successfully loaded and cached audio for key '{key}'.")
        else:
            logger.error(f"Failed to load or cache audio for key '{key}'.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        if cache_manager.redis_client:
            await cache_manager.close()
        logger.info("Script finished.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load a static WAV audio file into the Redis cache."
    )
    parser.add_argument(
        "--key",
        type=str,
        required=True,
        help="The key to store the audio under in Redis (e.g., 'audio_start_greeting')."
    )
    parser.add_argument(
        "--filepath",
        type=str,
        required=True,
        help="The full path to the .wav file to load."
    )
    args = parser.parse_args()

    # In the test, the key is 'audio_start_greeting'
    # and the file is 'stt_yandex/test/test_data/example_8k.wav'
    # Example usage:
    # python scripts/load_static_audio.py --key audio_start_greeting --filepath stt_yandex/test/test_data/example_8k.wav

    asyncio.run(main(args.key, args.filepath))
