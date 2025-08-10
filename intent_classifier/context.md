Задача: Модуль IntentClassifier (v3, Stateless-версия)

Этот документ описывает финальную, утвержденную спецификацию для модуля, отвечающего за распознавание намерений пользователя. Версия 3 является ключевым архитектурным обновлением, делающим модуль полностью stateless (не хранящим состояние), что гарантирует его потокобезопасность и предсказуемость в высоконагруженной асинхронной среде.

1. Контекст и цель модуля (CONTEXT)

IntentClassifier является “рефлекторной дугой” системы. Его единственная задача — с максимальной скоростью (< 100мс) и надежностью определить, какому из известных намерений (intent) соответствует речь пользователя. Он инкапсулирует всю сложность работы с эмбеддинг-моделями и алгоритмами семантического поиска.

1.1. Роль в системе:

Модуль работает как высокопроизводительный, чистый (pure) сервис для Orchestrator. Он отвечает на два ключевых вопроса:
	•	“Насколько речь пользователя соответствует одному из ОЖИДАЕМЫХ по сценарию интентов, учитывая предыдущий результат?” (Основной режим работы).
	•	“На что в нашей базе знаний похож этот вопрос?” (Режим обработки вопросов “не по теме”).

1.2. Потребители (Consumers):
	•	Orchestrator: Единственный потребитель.
	•	Оффлайн-скрипты: Скрипт prepare_embeddings.py использует этот модуль для предварительной векторизации всех фраз из dialogue_map.json.

1.3. Жизненный цикл (Lifecycle):

Долгоживущий Singleton. Экземпляр создается один раз при старте приложения. Важно: Несмотря на то, что это Singleton, он является полностью stateless и не хранит никакой информации о конкретных звонках.

1.5. Загрузка контекста и шагов:
Файл будет состоять из двух корневых объектов: `intents` и `dialogue_flow`.
**Пример `intents`:**
```json
{
  "intents": {
    "confirm_yes": {
      "description": "Пользователь выражает согласие",
      "phrases": ["Да", "Верно", "Подтверждаю", "Ага", "Все правильно"]
    },
    "confirm_no": {
      "description": "Пользователь выражает несогласие",
      "phrases": ["Нет", "Неверно", "Отмена", "Неа"]
    },
    "provide_number": {
      "description": "Пользователь называет какое-либо число",
      "phrases": [
        "ответ {number}", "давайте {number}", "{number}", "пусть будет {number}"
      ],
      "entity": {
        "type": "number" 
      }
    }
  }
}
```
Пример dialogue flow:
```json
{
  "dialogue_flow": {
	  "ask_engine_power": {
		  "description": "Система запрашивает мощность двигателя",
		  "system_response": {
			  "playlist": [
				  {
					  "type": "cache",
					  "key": "static:final_price_intro"
				  },
				  {
					  "type": "filler",
					  "key": "filler:hmm"
				  },
				  {
					  "type": "tts",
					  "text_template": "{{ session.variables.final_price }}"
				  },
				  {
					  "type": "cache",
					  "key": "static:currency_rubles"
				  }
			  ]
		  },
		  "transitions": {
			  "provide_number": {
				  "next_state": "ask_about_drivers",
				  "execute_code": "session.variables['engine_power'] = entities['value']\nif entities['value'] > 200:\n    session.variables['base_tariff'] = 15000\nelse:\n    session.variables['base_tariff'] = 12000"
			  }
		  },
		  "long_operation": true
	  },
    "state_goodbye_and_hangup": {
      "description": "Финальное состояние. Проигрываем прощание и завершаем звонок.",
      
      "action": "END_CALL",

      "system_response": {
        "playlist": [
          {
            "type": "cache",
            "key": "static:polite_goodbye" 
          }
        ]
      },
      "transitions": {} 
    }
}
}
```


1.6. models.py

```python
@dataclass(slots=True)
class FaqResult:
    question_id: str
    answer_text: str
    score: float
```

2. Архитектура и компоненты

Модуль будет состоять из нескольких четко разделенных по ответственности классов, находящихся в пакете intent_classifier/.

2.1. intent_classifier/model_wrapper.py -> Класс OnnxModelWrapper

Назначение: Полностью инкапсулирует работу с optimum.onnxruntime. Скрывает от остальной системы детали загрузки модели и токенизации.

Публичные методы:
	•	__init__(self, model_path: str, device: str): Конструктор. Принимает путь к папке с локально сохраненной моделью (например, ./models/MiniLM-L12-v2) и провайдер (CPUExecutionProvider или CUDAExecutionProvider). Загружает модель и токенизатор.
	•	async embed(self, texts: List[str]) -> np.ndarray: Основной метод. Принимает список текстов и асинхронно возвращает NumPy-массив с их эмбеддингами. Внутри использует asyncio.to_thread для вызова блокирующих операций модели.

2.2. intent_classifier/repository.py -> Класс IntentRepository

Назначение: Слой доступа к данным. Хранит все интенты, их фразы и предварительно рассчитанные эмбеддинги. Отвечает за бэкап и восстановление.

Публичные методы:
	•	load_from_backup(self, filepath: str): При старте загружает в память готовый бэкап (например, intents.pkl), содержащий intent_id и их векторы.
	•	prepare_and_save_backup(self, dialogue_map: dict, model_wrapper: OnnxModelWrapper, filepath: str): Метод для оффлайн-скрипта. Проходит по dialogue_map.json, векторизует все фразы через model_wrapper и сохраняет результат в бинарный файл.
	•	get_intent_vectors(self, intent_ids: List[str]) -> Dict[str, np.ndarray]: Возвращает готовые векторы для запрошенного списка интентов.
	•	get_all_faq_vectors(self) -> Dict[str, np.ndarray]: Возвращает векторы для всех вопросов из глобальной базы знаний.
	•	get_intent_metadata(self, intent_id: str) -> Optional[dict]: Возвращает метаданные для интента, включая информацию о том, какую сущность нужно извлекать.

2.3. intent_classifier/entity_extractors.py -> Новые классы-парсеры

Назначение: Новый файл, содержащий набор простых классов для извлечения разных типов данных.

Примеры классов:

class SimpleNumericExtractor:
    def extract(self, text: str) -> Optional[int]: ...
    
class BooleanExtractor:
    def extract(self, text: str) -> Optional[bool]: ...

2.4. intent_classifier/classifier.py -> Класс IntentClassifier

Назначение: Основной класс модуля, реализующий всю логику. Является “фасадом” для Orchestrator.

Публичные методы:
	•	__init__(self, model: OnnxModelWrapper, repo: IntentRepository, config: dict, extractors: dict): Конструктор. Принимает все зависимости. Больше не инициализирует внутренние словари для хранения состояния звонков.
	•	async classify_intent(self, text: str, expected_intents: List[str], previous_leader: Optional[str] = None) -> Optional[IntentResult]: (ИЗМЕНЕНА СИГНАТУРА) Основной метод. Теперь принимает previous_leader как аргумент. 
	•	async find_faq_answer(self, text: str) -> Optional[FaqResult]: Реализует режим “Поисковика”.

3. Логика работы classify_intent (Stateless-версия)

Это ключевой метод, который будет вызываться Orchestrator-ом на каждый partial и final результат от STT.

Вход:
	•	text: Распознанная речь.
	•	expected_intents: Список ID интентов, которые мы ждем на этом шаге.
	•	previous_leader: Optional[str]: (НОВЫЙ АРГУМЕНТ) ID интента-лидера с предыдущего partial шага. Orchestrator отвечает за его хранение в SessionState и передачу сюда.

Векторизация:

Вызывает await self.model.embed([text]) для получения вектора пользовательской фразы.

Получение кандидатов:

Вызывает self.repo.get_intent_vectors(expected_intents) для получения векторов-кандидатов.

Расчет сходства:

Быстро вычисляет косинусное сходство между вектором пользователя и всеми векторами-кандидатами.

Применение “Ворот Подтверждения”:
	1.	Находит лидера (интент с максимальным score).
	2.	Проверка 1 (Порог): score > config.thresholds.confidence
	3.	Проверка 2 (Отрыв): score - score_второго_места > config.thresholds.gap
	4.	Проверка 3 (Стабильность): (ИЗМЕНЕНА ЛОГИКА) Сравнивает текущего лидера с переданным аргументом previous_leader. Они должны совпадать.

Извлечение сущностей (Entity Extraction):
	•	Проверка необходимости: Вызывает self.repo.get_intent_metadata(победивший_интент) и проверяет наличие блока entity.
	•	Если entity блок существует:
	•	Извлекает имя парсера (например, parser: "simple_numeric").
	•	Вызывает соответствующий парсер: extractor = self.extractors["simple_numeric"].
	•	Выполняет извлечение: extracted_data = extractor.extract(text).
	•	Если entity блок отсутствует: Шаг пропускается.

Выход:
	•	Если все ворота пройдены И (сущность не требовалась ИЛИ сущность была успешно извлечена):
→ Возвращает объект IntentResult(intent_id, score, entities, current_leader).
Важно: результат теперь содержит current_leader, чтобы Orchestrator мог сохранить его для следующего вызова.
	•	Если интент определен, но извлечь обязательную сущность не удалось:
→ Возвращает None.
	•	В противном случае (не пройдены ворота):
→ Возвращает None.


⸻

### 📦 Быстрый конвейер спринта

#### 0) Укажи путь для .env и подними deps
python -m pip install -U numpy onnxruntime transformers tokenizers optimum huggingface_hub python-dotenv

#### 1) Скачай/подложи модель (ОНNX) и пропиши путь в .env
python scripts/download_model.py --repo-id intfloat/e5-small-v2-onnx --target models/our_model
или локально:
python scripts/download_model.py --from-dir /path/to/my_export --target models/our_model

#### 2) Подготовь бэкап эмбеддингов (intents_backup.pkl)
python scripts/prepare_embeddings.py \
  --intents configs/intents.json \
  --dialogue configs/dialogue_map.json \
  --output configs/intents_backup.pkl \
  --device cpu

#### 3) Мини-бенч (латентности embed/классификации)
python scripts/benchmark_embed.py \
  --backup configs/intents_backup.pkl \
  --text "пусть будет 500000" \
  --expected provide_number,confirm_yes,confirm_no \
  --repeat 20

#### 4) Ручной e2e тест (реальные кейсы)
python intent_classifier/test/manual_test_intents.py \
  --backup configs/intents_backup.pkl \
  --intents configs/intents.json \
  --device cpu \
  --repeat 10
⸻

### 🧩 Замечания по рискам и нюансам
	•	Совместимость модели: нужен ONNX-экспорт фичер-экстрактора (sentence-embeddings). Если скачанная модель не оннх — конвертируй заранее (вне спринта) или скорректируй model_wrapper под PyTorch (хуже по латентности).
	•	Нормализация векторов: обязательно L2-норма → косинус=dot, дешёвый скоринг.
	•	Пороговые значения: начальные confidence=0.4, gap=0.05 — регулируются под данные клиента.
	•	Статичность: никакой per-call статики внутри IntentClassifier; всё состояние — снаружи (например, previous_leader хранит Orchestrator).
	•	Логи: все скрипты и ядро печатают строго JSON-события — удобно стыковать с Kibana/Grafana.