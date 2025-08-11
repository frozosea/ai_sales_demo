from __future__ import annotations
import asyncio
import json
import time
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any
from dotenv import dotenv_values
import sys
import os
import statistics
import numpy as np
from datetime import datetime

# Add project root to path for absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from intent_classifier.model_manager import ModelManager
from intent_classifier.repository import IntentRepository
from intent_classifier.classifier import IntentClassifier
from intent_classifier.entity_extractors import SimpleNumericExtractor, BooleanExtractor

# --- 1. Настройка логирования ---
logging.basicConfig(level=logging.INFO, format='%(message)s')

def jlog(event: str, **fields):
    """Кастомный JSON-логгер."""
    logging.info(json.dumps({"event": event, "ts": datetime.utcnow().isoformat(), **fields}, ensure_ascii=False))

# --- 2. Генерация отчета ---
def generate_report(results: Dict[str, Any], output_dir: Path):
    """Генерирует детальный Markdown отчет по результатам теста."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = output_dir / f"intent_test_report_{timestamp}.md"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Отчет о тестировании IntentClassifier\n")
        f.write(f"**Время генерации:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## 1. Сводная статистика\n\n")
        f.write("| Метрика | Значение |\n")
        f.write("|:---|:---|\n")
        f.write(f"| Общая точность (Accuracy) | {results['summary']['accuracy']:.2%} |\n")
        f.write(f"| Средняя уверенность (Score) | {results['summary']['avg_score']:.4f} |\n")
        f.write(f"| P50 Latency (ms) | {results['summary']['p50_ms']:.2f} |\n")
        f.write(f"| P95 Latency (ms) | {results['summary']['p95_ms']:.2f} |\n\n")

        f.write("## 2. Результаты по интентам\n\n")
        f.write("| Интент | Точность | Ср. Score | Кол-во ошибок |\n")
        f.write("|:---|:---|:---|:---|\n")
        for intent, data in results['by_intent'].items():
            f.write(f"| `{intent}` | {data['accuracy']:.2%} | {data['avg_score']:.4f} | {data['errors']} |\n")
        
        f.write("\n## 3. Список ошибок\n\n")
        if not results['errors']:
            f.write("Ошибок не найдено. Отличная работа!\n")
        else:
            f.write("| Исходный интент | Фраза | Распознано как | Score |\n")
            f.write("|:---|:---|:---|:---|\n")
            for error in results['errors']:
                f.write(f"| `{error['expected_intent']}` | `{error['text']}` | `{error['actual_intent']}` | {error['score']:.4f} |\n")
    
    jlog("report_generated", path=str(report_path))

# --- 3. Основная функция ---
async def main():
    parser = argparse.ArgumentParser(description="Data-driven test for IntentClassifier.")
    parser.add_argument("--backup", type=str, required=True, help="Path to intents_backup.pkl")
    parser.add_argument("--data", type=str, default="intent_classifier/test_data/data.json", help="Path to test data JSON file.")
    # Добавляем аргумент для модели FastText
    parser.add_argument(
        "--fasttext-model",
        type=str,
        default="configs/fasttext_model.bin",
        help="Path to the trained FastText model."
    )
    parser.add_argument("--device", type=str, default="cpu", help="Device to use (cpu or cuda)")
    parser.add_argument("--output-dir", type=str, default="reports", help="Directory to save reports.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # --- Загрузка модели и зависимостей ---
    env = dotenv_values()
    model_path = env.get("EMB_MODEL_PATH")
    if not model_path:
        jlog("error", msg="EMB_MODEL_PATH missing in .env")
        return

    ModelManager.initialize(model_path, device=args.device)
    
    repo = IntentRepository()
    repo.load_from_backup(args.backup)

    # Загрузка тестовых данных
    with open(args.data, "r", encoding="utf-8") as f:
        test_data = json.load(f)

    all_intents = list(test_data.keys())

    extractors = {
        "simple_numeric": SimpleNumericExtractor(),
        "boolean": BooleanExtractor()
    }
    
    config = {
        "thresholds": {"confidence": 0.75, "gap": 0.01},
        "faq": {"confidence": 0.55},
    }
    
    # Инициализируем гибридный классификатор
    classifier = IntentClassifier(
        model_path=model_path,
        repo=repo,
        config=config,
        extractors=extractors,
        device=args.device,
    )
    
    # --- Запуск тестов ---
    jlog("test_start", total_intents=len(test_data), total_phrases=sum(len(v) for v in test_data.values()))
    
    all_results = {
        'summary': {'correct': 0, 'total': 0, 'latencies': [], 'scores': []},
        'by_intent': {intent: {'correct': 0, 'total': 0, 'scores': []} for intent in all_intents},
        'errors': []
    }
    
    for expected_intent, phrases in test_data.items():
        for text in phrases:
            t_start = time.monotonic()
            result = await classifier.classify_intent(text, all_intents)
            t_end = time.monotonic()
            
            latency = (t_end - t_start) * 1000
            all_results['summary']['latencies'].append(latency)
            all_results['summary']['total'] += 1
            all_results['by_intent'][expected_intent]['total'] += 1

            actual_intent = result.intent_id if result else "None"
            score = result.score if result else 0.0

            if actual_intent == expected_intent:
                all_results['summary']['correct'] += 1
                all_results['by_intent'][expected_intent]['correct'] += 1
                all_results['summary']['scores'].append(score)
                all_results['by_intent'][expected_intent]['scores'].append(score)
                jlog("test_case", text=text, expected=expected_intent, actual=actual_intent, status="ok", score=score, ms=latency)
            else:
                error_details = {
                    'text': text,
                    'expected_intent': expected_intent,
                    'actual_intent': actual_intent,
                    'score': score
                }
                all_results['errors'].append(error_details)
                jlog("test_case", text=text, expected=expected_intent, actual=actual_intent, status="fail", score=score, ms=latency)
    
    # --- Агрегация результатов ---
    summary = all_results['summary']
    summary['accuracy'] = (summary['correct'] / summary['total']) if summary['total'] > 0 else 0
    summary['avg_score'] = np.mean(summary['scores']) if summary['scores'] else 0
    summary['p50_ms'] = statistics.median(summary['latencies']) if summary['latencies'] else 0
    summary['p95_ms'] = np.percentile(summary['latencies'], 95) if summary['latencies'] else 0
    
    for intent, data in all_results['by_intent'].items():
        data['accuracy'] = (data['correct'] / data['total']) if data['total'] > 0 else 0
        data['avg_score'] = np.mean(data['scores']) if data['scores'] else 0
        data['errors'] = data['total'] - data['correct']

    # --- Генерация отчета ---
    generate_report(all_results, output_dir)
    
    await ModelManager.close()

if __name__ == "__main__":
    asyncio.run(main())
