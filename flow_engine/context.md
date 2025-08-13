### **Спецификация: FlowEngine v4 (Адаптивный Менеджер Задач)**

#### **1. Концепция и Роль**

`FlowEngine` — это **умный, целе-ориентированный мозг** диалоговой системы. Он является stateless-синглтоном. Его задача — не просто переключать состояния, а **динамически планировать, приостанавливать, возобновлять и отменять задачи** на основе целей диалога, зависимостей между данными и поведения пользователя в реальном времени.

-----

#### **2. Ключевые Сущности и Файлы Конфигурации**

##### **2.1. `goals.json` (Карта Целей и Зависимостей)**

Это декларативное описание **ЧТО** система может делать и **ЧТО** ей для этого нужно.

  * **Структура:**
      * `goal_id`: Уникальное имя цели (например, `provide_total_price`).
      * `parameters`: Список "слотов" (данных), которые необходимо собрать для достижения цели.
          * `name`: Имя переменной (e.g., `inner_amount`).
          * `is_required`: Условие необходимости. Может быть `true` или **строкой-условием** (e.g., `"session.variables.wants_inner_insurance == true"`).
          * `dialogue_state_to_ask`: ID состояния из `dialogue_map` для запроса этой переменной в обычном режиме.
          * `force_dialogue_state_to_ask`: ID состояния для запроса в **форсированном режиме**.
      * `is_digression`: Флаг `true` для целей, являющихся отвлечениями (FAQ).
      * `is_terminal`: Флаг `true` для целей, которые необратимо завершают основной сценарий.
      * `is_forcing`: Флаг `true` для интентов-требований.

##### **2.2. `dialogue_map.json` (Библиотека Реплик и Микро-сценариев)**

Роль `dialogue_map` **упрощается**. Он больше не является жестким графом. Теперь это хранилище:

  * **Состояний-вопросов:** (`ask_property_value`, `force_ask_property_value`).
  * **Состояний-ответов:** (`info_company`).
  * **Локальных переходов:** Например, подтверждение только что названной суммы (`confirm_property_value`).
  * **Специальных команд:** Переход с `next_state: "RESUME_PREVIOUS_TASK"` или `next_state: "RUN_FORCE_CHECK"`.


#### **2.3. Пример файлов **
dialogue_map.json:
```json
{

  "ask_property_value": {

    "system_response": { "template": "Подскажите, на какую сумму оцениваете стоимость вашей недвижимости?" },

    "transitions": { ... }

  },

  "force_ask_property_value": {

    "system_response": { "template": "Чтобы я мог назвать точную цену, мне осталось узнать только стоимость недвижимости. Какая она?" },

    "transitions": {

        "provide_number": {

            "next_state": "RUN_FORCE_CHECK", // Специальная команда для FlowEngine

            "execute_code": "..." 

        }

    }

  }

}
```
RUN_FORCE_CHECK — это специальный next_state, который говорит FlowEngine: "Переменную я получил, проверь, нужно ли что-то еще из форсированного списка, и перейди к следующему прямому вопросу".


goals.json:
```json
{

  "provide_total_price": {

    "parameters": [

      {

        "name": "wants_inner_insurance",

        "is_required": true,

        "dialogue_state_to_ask": "ask_if_wants_inner_insurance" 

      },

      {

        "name": "property_value",

        "is_required": true,

        "dialogue_state_to_ask": "ask_property_value"

      },

      {

        "name": "inner_amount",

        "is_required": "session.variables.wants_inner_insurance == true", // УСЛОВИЕ!

        "dialogue_state_to_ask": "ask_inner_amount"

      }

    ]

  },

  "handle_faq_ask_product": {

     // ...

  }
```

-----

#### **3. Модели Данных в `SessionState`**

```python
# domain/models.py
from dataclasses import dataclass, field
from typing import Optional, List, Literal

@dataclass
class Task:
    """Описывает одну активную задачу (основную цель или отвлечение)."""
    goal_id: str
    status: Literal['IN_PROGRESS', 'PAUSED']
    mode: Literal['NORMAL', 'FORCED'] = 'NORMAL'  # Режим выполнения
    return_state_id: Optional[str] = None # Куда вернуться после прерывания

@dataclass
class SessionState:
    # ... call_id, trace_id, variables, etc.
    
    # Стек задач. Вершина стека (последний элемент) - текущая активная задача.
    task_stack: List[Task] = field(default_factory=list)
```

-----

#### **4. Основной Алгоритм: `process_event`**

Это сердце движка. Логика выполняется в строгом порядке приоритетов.

**`process_event(session_state, intent_id)` -\> `FlowResult`**

1.  **ПРИОРИТЕТ 0: ТЕРМИНАЛЬНЫЙ ИНТЕНТ**

      * Найти цель, соответствующую `intent_id`. Если у нее `is_terminal: true`:
          * **Очистить `session_state.task_stack`**.
          * Поместить в стек новую, финальную задачу (e.g., `Task(goal_id='handle_rejection')`).
          * Вернуть `next_state` для этой задачи (e.g., `refusal_end`). **ВЫХОД**.

2.  **ПРИОРИТЕТ 1: ФОРСИРОВАННЫЙ ИНТЕНТ (`demand_final_answer_...`)**

      * Найти цель для `intent_id`. Если у нее `is_forcing: true`:
          * Найти в стеке основную "паузнутую" бизнес-цель (например, `provide_total_price`).
          * **Очистить стек от всех прерываний**, которые лежат выше основной цели.
          * Установить у основной цели `mode = 'FORCED'`.
          * Запустить "Режим быстрого сбора" (см. ниже). **ВЫХОД**.

3.  **ПРИОРИТЕТ 2: ВОЗВРАТ ПО ИНИЦИАТИВЕ ПОЛЬЗОВАТЕЛЯ (`return_to_main_goal`)**

      * Если `intent_id == 'return_to_main_goal'`:
          * Снять (`pop`) со стека текущую задачу (которая является прерыванием).
          * Взять новую вершину стека (паузнутую задачу), установить `status = 'IN_PROGRESS'`.
          * Вернуть `next_state = task.return_state_id`. **ВЫХОД**.

4.  **ПРИОРИТЕТ 3: ГЛОБАЛЬНОЕ ПРЕРЫВАНИЕ (FAQ)**

      * Найти цель для `intent_id`. Если у нее `is_digression: true`:
          * **Проверить "правило здравого смысла"**: Если `len(task_stack) >= 3`, вернуть флаг `should_guide_back: true` для `Orchestrator`.
          * Поставить текущую задачу на `PAUSED`, сохранив `return_state_id`.
          * Поместить на стек новую задачу для обработки FAQ.
          * Вернуть `next_state` для ответа на FAQ. **ВЫХОД**.

5.  **ПРИОРИТЕТ 4: ОБРАБОТКА ТЕКУЩЕЙ ЗАДАЧИ (Happy Path)**

      * Взять текущую задачу с вершины стека.
      * Выполнить `execute_code` для текущего перехода.
      * **"Режим быстрого сбора" (если `task.mode == 'FORCED'`)**:
          * Определить следующий **обязательный** и **незаполненный** параметр цели.
          * Если такой параметр есть, вернуть `next_state` из его `force_dialogue_state_to_ask`.
          * Если все параметры собраны, выполнить финальный расчет, завершить задачу и вернуть `next_state` для показа результата (e.g. `summary_single`).
      * **"Нормальный режим" (если `task.mode == 'NORMAL'`)**:
          * Вернуть `next_state` из `dialogue_map` для текущего "счастливого" пути.

-----

#### **5. Разбор Реальных Сценариев**

##### **Сценарий №1: "Нетерпеливый пользователь"**

  * **Стек:** `[Task(provide_total_price, PAUSED)]`
  * **Пользователь:** "Хватит вопросов, какая цена?\!" (`intent: 'demand_final_answer_cost'`)
  * **`FlowEngine`:** Срабатывает **Приоритет 1**. Находит задачу, ставит `mode='FORCED'`. Определяет, что не хватает `property_value`. Возвращает `next_state: 'force_ask_property_value'`.
  * **Робот:** "Чтобы я мог назвать точную цену, мне осталось узнать только стоимость недвижимости. Какая она?"

##### **Сценарий №2: "Любопытный, но сговорчивый"**

  * **Стек:** `[Task(provide_total_price, IN_PROGRESS)]`. Робот спрашивает про недвижимость.
  * **Пользователь:** "А вы робот?" (`intent: 'ask_robot'`)
  * **`FlowEngine`:** Срабатывает **Приоритет 3**. Ставит `provide_total_price` на `PAUSED`. Наверх стека кладется `Task(handle_faq_ask_robot)`. Возвращает `next_state: 'info_robot'`.
  * **Робот:** "Нет, я не робот..."
  * **Пользователь:** "А, понятно, давайте вернемся к делу" (`intent: 'return_to_main_goal'`)
  * **`FlowEngine`:** Срабатывает **Приоритет 2**. Снимает со стека `handle_faq_ask_robot`. Возобновляет `provide_total_price` и возвращает `next_state` оттуда.
  * **Робот:** "Так на какую сумму оцениваете стоимость вашей недвижимости?"

##### **Сценарий №3: "Решительный отказ"**

  * **Стек:** `[Task(provide_total_price, PAUSED), Task(handle_faq_ask_company, IN_PROGRESS)]`
  * **Пользователь:** "Мне это не интересно" (`intent: 'provide_reject_reason'`)
  * **`FlowEngine`:** Срабатывает **Приоритет 0**. Интент — терминальный.
      * **`task_stack` очищается: `[]`**.
      * В стек кладется `[Task(handle_rejection)]`.
      * Возвращается `next_state: 'refusal_end'`.
  * **Робот:** "Хорошо. Благодарю за уделённое время. Всего доброго." (После этого диалог завершается, попыток вернуться к старым задачам нет).

Эта спецификация описывает движок, который является не просто исполнителем, а **адаптивным менеджером диалога**. Он готов к хаосу реального разговора.