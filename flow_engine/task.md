
🧩 Задача FE-01 — Контракты и валидация: goals.json + dialogue_map.json + выражения is_required

Цель. Определить схемы конфигов, специальные команды, безопасную оценку условий и подготовить валидацию, чтобы весь движок опирался на JSON-данные, а не на “if-ветки” в коде.

Контекст

FlowEngine — stateless-singleton. Он опирается на 2 файла:
	•	configs/goals.json — цели и требуемые параметры (слоты) с условиями.
	•	configs/dialogue_map.json — хранилище состояний реплик/микросценариев и локальных переходов.

Нужны:
	•	Явные схемы (описание полей/типов).
	•	Поддержка специальных команд в next_state:
	•	RUN_FORCE_CHECK — перейти к следующему обязательному и незаполненному параметру в форс-режиме.
	•	RESUME_PREVIOUS_TASK — вернуться к предыдущей паузнутой задаче (FlowEngine сам вычислит куда).
	•	Безопасная функция для вычисления условий is_required:
	•	Поддержка выражений вида:
session.variables.wants_inner_insurance == true
	•	Учет изменения мнений пользователя (наша функция должна нормализовать булевы/числовые значения в session.variables, например строки "да"/"нет" → True/False, "0"/"1" → int):
	•	Введение абстракции fn boolish(value), fn num(value), fn var("name", default=None) в мини-языке условий.
	•	Все выражения исполняются в песочнице: только разрешённые имена/функции, запрет любых побочных эффектов.

Файлы
	•	flow_engine/schemas.py — формальные описания структур (словами, без кода).
	•	configs/goals.json — минимальный, но реалистичный пример (см. ниже).
	•	configs/dialogue_map.json — минимальный пример (см. ниже).
	•	scripts/validate_dialogue_map.py — (описать, что проверяет).
	•	scripts/validate_goals.py — (описать, что проверяет).

Требования к структурам

goals.json (пример)

{
  "provide_total_price": {
    "is_terminal": false,
    "is_digression": false,
    "is_forcing": false,
    "parameters": [
      {
        "name": "wants_inner_insurance",
        "is_required": true,
        "dialogue_state_to_ask": "ask_if_wants_inner_insurance",
        "force_dialogue_state_to_ask": "force_ask_if_wants_inner_insurance"
      },
      {
        "name": "property_value",
        "is_required": true,
        "dialogue_state_to_ask": "ask_property_value",
        "force_dialogue_state_to_ask": "force_ask_property_value"
      },
      {
        "name": "inner_amount",
        "is_required": "boolish(var('wants_inner_insurance')) == true",
        "dialogue_state_to_ask": "ask_inner_amount",
        "force_dialogue_state_to_ask": "force_ask_inner_amount"
      }
    ],
    "result_state": "summary_total_price"
  },

  "handle_faq_ask_company": {
    "is_terminal": false,
    "is_digression": true,
    "is_forcing": false,
    "result_state": "info_company"
  },

  "handle_rejection": {
    "is_terminal": true,
    "is_digression": false,
    "is_forcing": false,
    "result_state": "refusal_end"
  },

  "demand_final_answer_cost": {
    "is_terminal": false,
    "is_digression": false,
    "is_forcing": true
  }
}

dialogue_map.json (пример)

{
  "ask_property_value": {
    "description": "Запрос стоимости недвижимости",
    "system_response": {
      "playlist": [
        { "type": "tts", "text_template": "Подскажите, на какую сумму оцениваете вашу недвижимость?" }
      ]
    },
    "transitions": {
      "provide_number": {
        "next_state": "RUN_FORCE_CHECK",
        "execute_code": "session.variables['property_value'] = entities['value']"
      },
      "confirm_no": {
        "next_state": "ask_property_value_refine"
      }
    }
  },

  "force_ask_property_value": {
    "system_response": {
      "playlist": [
        { "type": "tts", "text_template": "Чтобы назвать цену, укажите стоимость недвижимости." }
      ]
    },
    "transitions": {
      "provide_number": {
        "next_state": "RUN_FORCE_CHECK",
        "execute_code": "session.variables['property_value'] = entities['value']"
      }
    }
  },

  "info_company": {
    "system_response": {
      "playlist": [ { "type": "cache", "key": "static:about_company" } ]
    },
    "transitions": {
      "return_to_main_goal": { "next_state": "RESUME_PREVIOUS_TASK" }
    }
  },

  "refusal_end": {
    "action": "END_CALL",
    "system_response": {
      "playlist": [ { "type": "cache", "key": "static:polite_goodbye" } ]
    },
    "transitions": {}
  },

  "summary_total_price": {
    "system_response": {
      "playlist": [
        { "type": "tts", "text_template": "Итоговая стоимость: {{ session.variables.total_price }} рублей." }
      ]
    },
    "transitions": { "confirm_yes": { "next_state": "refusal_end" } }
  }
}

Критерии готовности
	•	Схемы/описания покрывают все используемые поля и специальные next_state.
	•	Валидаторы сценариев: проверяют существование ссылок состояний, корректность текстовых шаблонов, известных интентов в transitions, синтаксис мини-языка is_required.
	•	Документированы ограничения мини-языка и разрешённые функции: boolish, num, var.

⸻

🧩 Задача FE-02 — Ядро FlowEngine: приоритеты, стек задач, статeless-работа

Цель. Формализовать и реализовать поведение process_event(session_state, intent_id, entities?) → FlowResult по приоритетной лестнице и управлению стеком задач.

Контекст

Порядок приоритетов:
	0.	Терминал (goal.is_terminal): очистка task_stack, пуш финальной задачи, next_state = goal.result_state.
	1.	Форс-интент (goal.is_forcing): перейти в быстрый сбор обязательных слотов основной цели, mode='FORCED', next_state = *force_ask_*.
	2.	Возврат к основному сценарию (intent_id == return_to_main_goal): pop() сверху до следующей не-PAUSED основной задачи, восстановление.
	3.	Дигрессия/FAQ (goal.is_digression): текущую задачу PAUSED, пуш новой FAQ-задачи, next_state = goal.result_state. Флаг should_guide_back при глубине > N.
	4.	Happy-path текущей задачи: применить transitions по dialogue_map для активного состояния (или шага), опционально выполнить execute_code, вернуть next_state.

Файлы
	•	flow_engine/engine.md — контракт process_event, структура FlowResult (поля), таблица приоритетов.
	•	flow_engine/models.md — модель Task/SessionState.task_stack (словами).
	•	flow_engine/test/test_priorities.md — сценарные тесты без кода.

FlowResult (контракт)
	•	status: SUCCESS | MISSING_ENTITY | EXECUTION_ERROR
	•	next_state: str | null
	•	updated_session: сериализуемый срез session_state (минимум: variables, task_stack в плоском виде)
	•	flags: { "should_guide_back": bool, "ended": bool } (опционально)

Поведение по сценариям (проверяем)
	1.	Нетерпеливый пользователь → форс-режим (см. ниже в FE-03).
	2.	Две вложенные FAQ → стек PAUSED/IN_PROGRESS, возврат.
	3.	Отказ → терминал: очистка стека, переход на refusal_end.

Критерии готовности
	•	Описана и согласована схема возврата FlowResult.
	•	Описан протокол модификации стека при каждом приоритете.
	•	Подготовлены сценарные тест-кейсы (словами, с входами/выходами) и фикстуры данных.

⸻

🧩 Задача FE-03 — Форс-режим и RUN_FORCE_CHECK: быстрый сбор обязательных слотов

Цель. Реализовать алгоритм быстрого сбора параметров цели при давлении пользователя (например, “Скажите цену сейчас”). FlowEngine должен выбрать следующий обязательный и незаполненный слот, учитывая условия is_required.

Контекст
	•	В goals.json у параметров есть:
	•	is_required: true | <expr>
	•	dialogue_state_to_ask / force_dialogue_state_to_ask
	•	Когда в диалоге срабатывает is_forcing: true или dialogue_map вернул next_state: "RUN_FORCE_CHECK", FlowEngine должен:
	1.	Пересчитать список требуемых слотов с учётом is_required (используя мини-язык из FE-01).
	2.	Отфильтровать те, что уже заполнены в session.variables.
	3.	Если есть незаполнённые — вернуть их форс-состояние (force_dialogue_state_to_ask).
	4.	Если все заполнены — вернуть result_state цели (например, summary_total_price) и поставить задачу в состояние завершения (в рамках Orchestrator это триггерит озвучивание итогов).

Файлы
	•	flow_engine/force_mode.md — описание алгоритма, псевдопоток.
	•	Дополнения к configs/goals.json — наличие force_dialogue_state_to_ask у каждого параметра.
	•	flow_engine/test/test_force_mode.md — тест-кейсы.

Примеры тестовых входных/выходных событий
	•	Вход: intent_id="demand_final_answer_cost", session.variables={}, стек уже содержит Task(goal_id='provide_total_price', status='IN_PROGRESS').
→ Выход: next_state="force_ask_property_value".
	•	Вход: dialogue_map переход provide_number → RUN_FORCE_CHECK, session.variables.property_value=5000000, wants_inner_insurance=true, inner_amount пуст.
→ Выход: next_state="force_ask_inner_amount".

Критерии готовности
	•	Описан детерминированный выбор одного следующего слота.
	•	Поведение при конфликте значений (переопределение предыдущего ответа) — зафиксировано: новая реплика пользователя заменяет значение в session.variables.

⸻

🧩 Задача FE-04 — Исполнение dialogue_map и генерация ответа: плейлисты, execute_code, метаданные

Цель. Превратить состояние/переход dialogue_map в структуру для Orchestrator: что проигрывать (playlist), какой next_state, нужно ли длинное ожидание и т. п.

Контекст
	•	dialogue_map[state_id] содержит:
	•	system_response.playlist — список шагов cache / filler / tts с шаблонизацией ({{ session.variables.* }}).
	•	transitions[intent_id] — next_state и опционально execute_code.
	•	long_operation: bool (опция; если true — Оркестратор включает стратегию с филлерами).
	•	action: "END_CALL" (для финала).
	•	FlowEngine должен вернуть:
	•	next_state (куда перейти),
	•	response (пакет, который Orchestrator отдаст проигрывателю плейлистов),
	•	флаги (ended), если задан action.

Файлы
	•	flow_engine/response_contract.md — формат ответа от FlowEngine к Orchestrator (словами).
	•	Примеры состояний в configs/dialogue_map.json с long_operation.
	•	flow_engine/test/test_dialogue_response.md — тест-кейсы.

Требования
	•	Шаблонизация текста — не в движке: FlowEngine возвращает структуру плейлиста и placeholders; Orchestrator подставит значения (у нас уже есть общий механизм).
	•	execute_code — в песочнице (FE-06), side-effects только в session.variables.
	•	Если переход ведёт к RUN_FORCE_CHECK / RESUME_PREVIOUS_TASK — FlowEngine не возвращает плейлист этого метасостояния; он вычисляет фактическое следующее состояние и возвращает его плейлист.

Критерии готовности
	•	Для заданного state_id и intent_id формируется валидный response с плейлистом.
	•	Для action: END_CALL возвращается flags.ended = true.

⸻

🧩 Задача FE-05 — Дигрессии (FAQ) и связка с IntentClassifier: глубина, should_guide_back

Цель. Обработать отвлечения (FAQ) как полноценные задачи в стеке: пауза основной цели, ответ, возврат.

Контекст
	•	Любой интент, который мапится на goal с is_digression: true, должен:
	•	Поставить текущую активную задачу в PAUSED (с return_state_id).
	•	Положить новую FAQ-задачу на вершину стека.
	•	Вернуть next_state = goal.result_state (например, info_company).
	•	Если глубина стека ≥ 3 — вернуть флаг should_guide_back: true. Orchestrator может произнести мягкую подсказку “вернёмся к расчёту…”.
	•	Если FAQ требует ответа из базы знаний:
	•	FlowEngine не ищет по базе — он только планирует. По согласованному контракту Orchestrator уже получил от IntentClassifier.find_faq_answer(text) ответ (или None).
	•	Если FaqResult есть — FlowEngine вернёт state для проигрыша ответа (из dialogue_map) и пометит response.faq_text для TTS (по контракту).

Файлы
	•	flow_engine/digressions.md — правила и ограничения.
	•	configs/goals.json — примеры is_digression целей (несколько).
	•	flow_engine/test/test_digressions.md — сценарии из реальных диалогов (2–3 вложения, затем возврат).

Критерии готовности
	•	Чёткая логика паузы/возврата.
	•	Поддержан флаг should_guide_back и корректно считается глубина.
	•	Документирован контракт, как FlowEngine использует результат find_faq_answer (если он приходит от Orchestrator).

⸻

🧩 Задача FE-06 — Песочница execute_code, безопасность и трассировка

Цель. Обеспечить безопасное выполнение мини-скриптов из dialogue_map.transitions[*].execute_code без возможности “сломать” процесс.

Контекст
	•	Допускаем только:
	•	Доступ к session.variables и локальным entities.
	•	Операции присваивания простых типов (str/float/int/bool).
	•	Вычисления без побочных эффектов (никаких импортов, IO, сети).
	•	Нужны:
	•	Чёрный список Python-объектов.
	•	Белый список функций (например, min/max/round по согласованию).
	•	Ограничение по времени (таймаут).
	•	Протокол ошибок: при исключении → FlowResult.status = EXECUTION_ERROR, читабельная причина.

Файлы
	•	flow_engine/utils.md — спецификация песочницы и список разрешённых операций.
	•	flow_engine/test/test_execute_code.md — позитив/негатив (безопасность, таймаут, ошибка синтаксиса).
	•	Логирование: каждая попытка исполнения записывается в структурный лог (JSONL) с trace_id, goal_id, state_id, intent_id, ok/error, elapsed_ms.

Критерии готовности
	•	Чётко описанный API песочницы и формат ошибок.
	•	Полезные логи для отладки реальных сценариев.

⸻

🧩 Задача FE-07 — E2E-набор сценарных тестов FlowEngine (без внешних сервисов)

Цель. Зафиксировать поведение на реальных паттернах диалога: прыжки, FAQ-вставки, форс-режим, отказ.

Контекст

Нам нужен тестовый раннер, который “кормит” FlowEngine последовательностью (intent_id, entities?, meta?) и сверяет FlowResult и эволюцию session_state.task_stack.

Файлы
	•	flow_engine/test/e2e_scenarios.md — описания сценариев и ожидаемых шагов.
	•	flow_engine/test_data/:
	•	goals_e2e.json
	•	dialogue_map_e2e.json
	•	sessions/*.json — исходные срезы session_state.variables для разных стартовых условий.

Обязательные сценарии
	1.	Нетерпеливый прыжок: приветствие прервано, ask_cost → план provide_total_price → форс-вопросы → сводка.
	2.	Две FAQ подряд: ask_company → ask_robot → возврат → ввод значения → RUN_FORCE_CHECK → сводка.
	3.	Передумал: после сбора части данных → терминальный интент → refusal_end.
	4.	Изменение мнения: сначала wants_inner_insurance=true, затем пользователь говорит “передумал” → условные слоты пересчитались, inner_amount становится не нужен.
	5.	Нерелевантный интент на вершине FAQ: при вводе числа в FAQ-задаче — игнор/руление возвратом (описать два варианта: мягкий pop при явном provide_number или ожидание return_to_main_goal).

Критерии готовности
	•	Для каждого сценария — таблица: вход → ожидаемый next_state/flags/stack.
	•	Отчётность: формируем JSONL с шагами сценария (трассировка), пригодную для Kibana/Grafana.

⸻

Общие заметки по качеству и метрикам
	•	Строго JSON-driven: никаких хардкодов по интентам/состояниям. Всё — через goals.json/dialogue_map.json.
	•	Трассировка: каждый вызов process_event логируется: trace_id, intent_id, goal_id(если есть), state_id(если есть), приоритет, next_state, флаги, стек (краткий вид), elapsed_ms.
	•	Отказоустойчивость: если JSON испорчен (нет result_state у терминала и т. п.), возвращаем EXECUTION_ERROR и “аварийное” состояние для Orchestrator (пусть он сыграет тех-филлер и завершит звонок).
	•	Расширяемость: новые цели/FAQ/форс-интенты добавляются только через JSON; движок не меняем.

⸻

Как прогонять тесты (инструкции для разработчика)
	1.	Подготовить/обновить configs/goals.json и configs/dialogue_map.json по примерам из задач.
	2.	Запустить валидаторы (описаны в FE-01).
	3.	Прогнать unit-набор: сценарии приоритетов (FE-02), форс-режим (FE-03), диалоговые ответы (FE-04), дигрессии (FE-05), песочницу (FE-06).
	4.	Прогнать E2E сценарии (FE-07) — сверить ожидаемые next_state, flags, краткие срезы стека.
	5.	Проверить логи JSONL: есть trace, шаги, ошибки помечены, время выполнения < заданных бюджетов (например, < 3–5 мс на вызов FE при mock-условиях).

⸻