import json
from pathlib import Path
from typing import Dict, Any

def load_json_config(file_path: str) -> Dict[str, Any]:
    """Загружает JSON-конфиг."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {file_path}")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)
