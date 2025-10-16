Live Stand: “Dialogue AI Assistant”

1. Vision and Goal

The goal of this project is to demonstrate a prototype of a next-generation voice AI assistant capable of conducting natural, seamless real-time dialogue. We show that the technology makes it possible to move away from robotic responses and annoying pauses, creating an effective tool for business communications.

Key “Wow Effects”:
	•	Instant reaction: The assistant answers standard questions with no delay.
	•	“Real-time thinking”: The response to complex questions begins almost immediately, creating the illusion of a live thought process.
	•	Full dialogue control: The user can interrupt the assistant at any moment, and it will instantly yield, like a polite conversation partner (Barge-in).
	•	Premium voice quality: The assistant’s voice sounds natural and convincing.

⸻

2. System Architecture

The system is built on the principles of speed, intelligence, and quality. Each module contributes to the final result.

 

Component	Technology	Business Justification
Frontend	React / Next.js	Fast start and focus on visualizing the assistant’s “thought process.”
Media Server	LiveKit	Ensures reliable low-latency WebRTC connection for seamless voice transfer.
Orchestrator	Python (Asyncio)	A flexible core managing the best AI services on the market.
In-Memory Cache	Redis	Provides instant access to ready audio responses, creating the “wow effect.”
STT	Yandex SpeechKit	Best-in-class Russian speech recognition with minimal delay.
LLM	OpenAI GPT-4o mini	Allows the assistant to hold meaningful dialogue, not just follow a script.
TTS	ElevenLabs	Delivers premium, natural voice output, increasing trust.


⸻

3. Quick Start for Developers

3.1. Installing dependencies
	1.	Set up environment:

python -m venv venv
source venv/bin/activate


	2.	Install requirements.txt:

pip install -r requirements.txt


	3.	Set up environment variables:
Copy env.example to .env and fill it with your API keys and settings.

cp env.example .env
# nano .env



3.2. Local launch of LiveKit and Redis

For full functionality you need a running LiveKit server and Redis.
Use Docker for quick deployment:

# Run LiveKit
docker run --rm -it -p 7880:7880 -p 7881:7881 livekit/livekit-server --dev

# Run Redis
docker run --rm -d -p 6379:6379 --name redis-cache redis

This will launch LiveKit in development mode. API Key and Secret will be printed to the console — add them to your .env file.

⸻

4. Project Structure and Module Description

Below is the description of the key directories and their contents.

project_root/
├─ README.md              # This file
├─ .env.example           # Sample environment variables
├─ requirements.txt       # Python dependencies
├─ configs/               # All configuration files
├─ scripts/               # Helper scripts for build and tests
├─ infra/                 # Infrastructure configs (logs, metrics, Redis)
├─ domain/                # Common data models and interfaces
├─ cache/                 # Caching module (Redis)
├─ llm/                   # Logic for working with Large Language Models (OpenAI)
├─ flow_engine/           # Dialogue scenario management
├─ intent_classifier/     # User intent recognition
├─ stt_yandex/            # Speech recognition (Speech-to-Text)
├─ tts_manager/           # Speech synthesis (Text-to-Speech)
├─ orchestrator/          # "Conductor" of the whole process
└─ webapi/                # WebSocket API for Frontend interaction

Detailed module description:
	•	configs/: Contains all static configuration:
	•	config.yml: Global settings (keys, timeouts).
	•	prompts.yml: System prompts for LLM.
	•	dialogue_map.json: Map of dialogue states and transitions.
	•	goals.json: Goals and parameters for FlowEngine.
	•	scripts/: Utility set for preparing and maintaining the project:
	•	load_static_audio.py: Loads pre-recorded WAV files into Redis cache. Used for “warming up” the cache with static audio responses for minimal latency.
	•	prepare_embeddings.py: Creates vector embeddings of phrases from dialogue_map.json. Required for IntentClassifier which uses semantic search to detect user intent.
	•	validate_dialogue_map.py: Validates references and fields in dialogue_map.json to prevent runtime errors.
	•	gen_token.py: Generates JWT tokens for connecting to LiveKit.
	•	benchmark_embed.py: Script for measuring embedding model performance.
	•	download_model.py: Script for downloading models from HuggingFace.
	•	domain/: Central place for defining shared data structures (models.py) and abstract interfaces (interfaces/). Helps avoid circular dependencies and ensures loose coupling.
	•	cache/: Redis-based cache implementation. Stores three types of data: static audio fragments, TTS synthesis cache, and LLM dialogue summaries.
	•	intent_classifier/: Determines user intent (intent) from speech. Uses a local ONNX model for fast semantic search over pre-built embeddings.
	•	flow_engine/: The “brain” of the dialogue system. Manages tasks, slots, and scenarios based on goals.json and dialogue_map.json. Stateless singleton: receives current session state and event, outputs a new state.
	•	stt_yandex/: Module for streaming speech recognition via Yandex SpeechKit. Provides both partial and final recognition results.
	•	tts_manager/: Responsible for speech synthesis via ElevenLabs, using a hybrid approach (HTTP for short phrases, WebSocket for LLM streaming responses).
	•	llm/: Manages interaction with OpenAI, including dialogue context management, prompt engineering, and handling streaming responses.
	•	orchestrator/: The “conductor” of the call. Coordinates all modules: receives audio from LiveKit, sends it to STT, passes result to IntentClassifier and FlowEngine/LLM, gets audio from TTS or Cache and sends it back to LiveKit. A new Orchestrator instance is created per call.
	•	webapi/: Application entry point. Implements a FastAPI WebSocket server, accepts client connections, creates an Orchestrator instance per call, and manages its lifecycle.

⸻

5. Visualization API (WebSocket)

The API is designed so that the Frontend can display the assistant’s “thoughts” in real time.
	•	Sending to server: start_demo_call, user_interrupted.
	•	Receiving from server:
	•	demo_call_started: Session started.
	•	bot_mind_state_update: Key message with current state (IDLE, LISTENING, ANALYZING_SPEECH, CHECKING_CACHE, ROUTING_TO_LLM, GENERATING_SPEECH, SPEAKING).
	•	llm_text_chunk: Streaming delivery of generated LLM text.
	•	error_occurred: Error message.
