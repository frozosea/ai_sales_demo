from __future__ import annotations
import logging
import json
import tiktoken
import yaml
from typing import List

from domain.interfaces.llm import AbstractLLMContext
from domain.models import ConversationMessage, ConversationHistory

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("llm.context")

def jlog(data: dict):
    logger.info(json.dumps(data))

class LLMContext(AbstractLLMContext):
    def __init__(self, prompt_config: dict, max_tokens: int, model_name: str):
        self._prompt_config = prompt_config
        self._max_tokens = max_tokens
        self._history: ConversationHistory = []
        self._current_tokens = 0
        try:
            self._encoder = tiktoken.encoding_for_model(model_name)
        except KeyError:
            logger.warning(f"Warning: model {model_name} not found. Using cl100k_base encoding.")
            self._encoder = tiktoken.get_encoding("cl100k_base")

        # Pre-calculate tokens for system prompts
        self._system_prompt_tokens = len(self._encoder.encode(self._prompt_config.get('system_prompt', '')))
        self._format_instruction_tokens = len(self._encoder.encode(self._prompt_config.get('response_format_instruction', '')))
        self._current_tokens += self._system_prompt_tokens + self._format_instruction_tokens

    def add_message(self, message: ConversationMessage) -> None:
        self._history.append(message)
        # Incrementally update token count
        self._current_tokens += len(self._encoder.encode(message['content']))
        ratio = self.estimate_usage_ratio()
        jlog({"event": "add_message", "role": message['role'], "usage_ratio": ratio, "current_tokens": self._current_tokens})

    def build_prompt(self) -> str:
        # A more sophisticated implementation might prune the history
        # to fit within the token limit.
        system_prompt = self._prompt_config.get('system_prompt', '')
        format_instruction = self._prompt_config.get('response_format_instruction', '')
        
        full_prompt_messages = (
            [{"role": "system", "content": system_prompt}] +
            self._history +
            [{"role": "system", "content": format_instruction}]
        )
        
        # For simplicity, we'll just join the content.
        # A real implementation would use a templating engine or format
        # the messages according to the specific model's requirements.
        return "\n".join(msg['content'] for msg in full_prompt_messages)


    def build_summary_prompt(self, history: ConversationHistory) -> str:
        summary_instruction = self._prompt_config.get('summarization_prompt', '')
        dialogue = "\n".join(f"{msg['role']}: {msg['content']}" for msg in history)
        return f"{summary_instruction}\n\n{dialogue}"

    def get_history_for_summary(self) -> ConversationHistory:
        # Return all but the last exchange, for example
        if len(self._history) > 2:
            return self._history[:-2]
        return []

    def estimate_usage_ratio(self) -> float:
        return min(self._current_tokens / self._max_tokens, 1.0)

if __name__ == "__main__":
    # Load configs
    with open("configs/prompts.yml", 'r') as f:
        prompts = yaml.safe_load(f)
    
    with open("configs/config.yml", 'r') as f:
        config = yaml.safe_load(f)

    max_tokens = config['llm']['context_window_size']
    model_name = config['llm']['models']['main']

    context = LLMContext(prompts, max_tokens, model_name)
    
    context.add_message({"role": "user", "content": "Hello, I need help with my account."})
    context.add_message({"role": "assistant", "content": "Certainly, how can I assist you today?"})
    
    full_prompt = context.build_prompt()
    ratio = context.estimate_usage_ratio()
    
    print("--- Generated Prompt ---")
    print(full_prompt)
    print("------------------------")
    jlog({"event": "final_context_state", "usage_ratio": ratio, "prompt_length": len(full_prompt)})
