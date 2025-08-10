from __future__ import annotations
import os
import sys
import json
import argparse
import logging
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from intent_classifier.fasttext_classifier import FastTextClassifier

logging.basicConfig(level=logging.INFO, format='%(message)s')

def prepare_data(data_path: str, output_path: str):
    """
    Преобразует JSON-данные в формат, понятный FastText.
    Формат: __label__<intent_id> <text>
    """
    logging.info(f"Preparing data from {data_path} for FastText.")
    with open(data_path, 'r', encoding='utf-8') as f_in, \
         open(output_path, 'w', encoding='utf-8') as f_out:
        data = json.load(f_in)
        for intent, phrases in data.items():
            for phrase in phrases:
                # Нормализуем текст: убираем лишние пробелы и переводим в нижний регистр
                normalized_phrase = " ".join(phrase.lower().split())
                if normalized_phrase: # Пропускаем пустые строки
                    f_out.write(f"__label__{intent} {normalized_phrase}\n")
    logging.info(f"FastText training data saved to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Train a FastText model for intent classification.")
    parser.add_argument(
        "--data-path",
        type=str,
        default="intent_classifier/test_data/data.json",
        help="Path to the 'dirty' test data JSON file."
    )
    parser.add_argument(
        "--output-model-path",
        type=str,
        default="configs/fasttext_model.bin",
        help="Path to save the trained FastText model."
    )
    parser.add_argument(
        "--temp-data-file",
        type=str,
        default="fasttext_train_data.txt",
        help="Temporary file for formatted training data."
    )
    # Добавляем параметры обучения FastText
    parser.add_argument("--lr", type=float, default=0.1, help="Learning rate.")
    parser.add_argument("--epoch", type=int, default=25, help="Number of epochs.")
    parser.add_argument("--wordNgrams", type=int, default=1, help="Max length of word n-grams.")
    parser.add_argument("--dim", type=int, default=100, help="Size of word vectors.")

    args = parser.parse_args()

    # Убедимся, что директория для модели существует
    Path(args.output_model_path).parent.mkdir(exist_ok=True)

    # 1. Подготовка данных
    prepare_data(args.data_path, args.temp_data_file)

    # 2. Обучение модели
    classifier = FastTextClassifier()
    train_params = {
        "lr": args.lr,
        "epoch": args.epoch,
        "wordNgrams": args.wordNgrams,
        "dim": args.dim,
    }
    try:
        classifier.train(
            data_path=args.temp_data_file,
            model_save_path=args.output_model_path,
            **train_params
        )
        logging.info("FastText model training completed successfully.")
    except Exception as e:
        logging.error(f"An error occurred during training: {e}")
        # Очищаем временный файл в случае ошибки
        os.remove(args.temp_data_file)
        sys.exit(1)

    # 3. Очистка временного файла
    os.remove(args.temp_data_file)
    logging.info(f"Temporary data file {args.temp_data_file} removed.")

if __name__ == "__main__":
    main() 