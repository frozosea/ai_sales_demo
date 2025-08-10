### **Задача: Модуль FlowEngine (v2, отказоустойчивая версия)**

Этот документ описывает обновленную спецификацию для модуля FlowEngine. Версия 2 добавляет механизмы возврата состояния, валидации данных и обработки ошибок, делая систему значительно более надежной и готовой к реальным сценариям.

#### **1. Контекст и цель модуля (CONTEXT)**

**FlowEngine — это "мозг" диалогового сценария. Его задача — управлять ходом диалога, изменять состояние сессии и выполнять бизнес-логику (расчеты, проверки) на основе команд от Orchestrator. Он отвечает на вопрос: "Что делать дальше по сценарию?**

#### **2. Архитектура и компоненты**

**Модуль будет состоять из одного основного класса, находящегося в пакете flow_engine/.**

**2.1. flow_engine/engine.py -> Класс FlowEngine**

* **Назначение: Реализует всю логику управления состоянием и выполнения кода из сценария.**  
* **Зависимости:**  
* **dialogue_map: Загруженный в память словарь из dialogue_map.json.** 
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
                      "execute_code": "session['variables']['engine_power'] = entities['value']nif entities['value'] > 200:n    session['variables']['base_tariff'] = 15000nelse:n    session['variables']['base_tariff'] = 12000"
                  }
              },
              "long_operation": true
          }
      }
    }
  ```
* **Данные, с которыми оперирует:**  
  * **SessionState: data class. FlowEngine получает его на вход, модифицирует и возвращает обратно.**:
  * ```python
    @dataclass
    class SessionState:
        """
        Полное состояние одного звонка.
        Этот объект — "единый источник правды" для Оркестратора.
        """
        call_id: str
        current_state_id: str = "start"
        variables: Dict[str, Any] = field(default_factory=dict)
        state_history: List[str] = field(default_factory=list)  # Для логики возврата
        previous_intent_leader: Optional[str] = None
        turn_state: Literal['BOT_TURN', 'USER_TURN'] = 'BOT_TURN'
    ```
  * **IntentResult: Объект (или словарь) от IntentClassifier, содержащий intent_id и извлеченные entities.**

#### **3. Детальная спецификация FlowEngine (v2)**

**3.1. __init__(self, dialogue_map_path: str)**

* **Назначение: Конструктор класса.**  
* **Логика:**  
  * **Принимает путь к файлу dialogue_map.json.**  
  * **Загружает и парсит JSON в атрибут self.dialogue_map.**  
  * **Выполняет валидацию карты диалога (проверяет целостность ссылок next_state и т.д.), чтобы упасть при старте, а не во время звонка.**
  * Каждый transition и каждый блок execute_code вызываются в последовательности, чтобы избежать кривого кода. Делается это через отдельный метод utils.check_exec_valid()

**3.2. process_event(self, session_state: SessionState, intent_id: str, entities: Optional[Dict]) -> FlowResult**

* **Назначение:** Основной метод, который теперь возвращает не просто словарь, а структурированный объект FlowResult, содержащий статус выполнения. Метод process_event должен быть полностью самодостаточным. Он получает entities и сам проверяет наличие всех полей, которые нужны ему для конкретного шага сценария. Это полностью убирает «вакуумность» и делает контракт явным: «Дайте мне entities в любом виде, я сам разберусь, подходят они или нет, и верну вам статус».
* **Логика:**  
  1. Получает на вход session_state, intent_id и entities.  
  2. ** Шаг валидации:** Перед выполнением, проверяет, что entities содержат необходимые данные, если они требуются для execute_code. Например, если код использует entities['value'], а оно None, немедленно возвращает FlowResult(status='MISSING_ENTITY').  
  3. Находит соответствующий блок transition в dialogue_map.json.  
  4. Извлекает execute_code и next_state.  
  5. **Безопасное выполнение кода с обработкой ошибок:**  
     * Использование copy.deepcopy(session_state) внутри FlowEngine гарантирует атомарнось операции
     * Оборачивает вызов exec() в try...except Exception as e.  
     * **В случае успеха:** exec() модифицирует session_state.  
     * **В случае ошибки:** Логирует исключение e и немедленно возвращает FlowResult(status='EXECUTION_ERROR').  
  6. **Логика возврата состояния:** Если intent_id — это интент коррекции (например, intent_correction_sum_1), то execute_code должен содержать логику очистки зависимых переменных (например, session.variables['coast_1'] = None), а next_state будет указывать на предыдущее состояние (например, ask_initial_sum).  
  7. Обновляет session_state.current_state_id = next_state.  
  8. Возвращает FlowResult(status='SUCCESS', updated_session=session_state).

**3.3. Класс FlowResult**

* Это простой dataclass для структурирования ответа от FlowEngine, чтобы Orchestrator четко понимал результат.  
  from dataclasses import dataclass  
  from typing import Optional, Literal

  Status = Literal['SUCCESS', 'EXECUTION_ERROR', 'MISSING_ENTITY']

  @dataclass  
  class FlowResult:  
      status: Status  
      updated_session: Optional[SessionState] = None

#### **4. Обработка исключительных ситуаций (Ответы на твои вопросы)**

**4.1. Возврат состояния (User-driven Rollback)**

* **Решение:** В dialogue_map.json мы создаем специальные интенты, например, intent_correction_sum_1. В любом состоянии, где пользователь может "передумать", мы добавляем переход для этого интента.  
  "final_confirmation": {  
      "transitions": {  
          "intent_correction_sum_1": {  
              "next_state": "ask_initial_sum", // Возвращаемся к шагу задания суммы  
              "execute_code": "session['variables']['sum_1'] = Nonensession['variables']['coast_1'] = Nonensession['variables']['final_price'] = None" // Очищаем все зависимые расчеты  
          }  
      }  
  }

**4.2. Валидация данных и отсутствующие сущности**

* **Решение:** Ответственность разделена.  
  1. **IntentClassifier:** Если он должен был извлечь число, но не смог, он вернет entities=None.  
  2. **Orchestrator:** Перед вызовом FlowEngine, он проверяет: если интент требует сущность, а entities пусто, он **не вызывает FlowEngine**, а сразу запускает аудио-филлер "Не расслышал, повторите, пожалуйста".  
  3. **FlowEngine:** Как вторая линия защиты, он выполняет базовую проверку типов внутри себя (шаг 3.2.2).

**4.3. Ошибки выполнения кода (System-driven Fallback)**

* **Решение:** FlowEngine теперь всегда возвращает FlowResult.  
  * **Orchestrator:** result = flow_engine.process_event(...)  
  * if result.status == 'EXECUTION_ERROR':  
    * // Запускаем аудио-филлер "Извините, технические неполадки"  
  * elif result.status == 'SUCCESS':  
    * // Продолжаем нормальный флоу

