# Отчет о тестировании IntentClassifier
**Время генерации:** 2025-08-11 10:41:20

## 1. Сводная статистика

| Метрика | Значение |
|:---|:---|
| Общая точность (Accuracy) | 77.17% |
| Средняя уверенность (Score) | 0.8757 |
| P50 Latency (ms) | 43.67 |
| P95 Latency (ms) | 70.40 |

## 2. Результаты по интентам

| Интент | Точность | Ср. Score | Кол-во ошибок |
|:---|:---|:---|:---|
| `confirm_yes` | 85.00% | 0.8744 | 3 |
| `confirm_no` | 78.95% | 0.8783 | 4 |
| `provide_number` | 100.00% | 0.9500 | 0 |
| `ask_where_number` | 85.71% | 0.8388 | 2 |
| `ask_previous_client` | 69.23% | 0.8477 | 4 |
| `ask_policy_used` | 16.67% | 0.8933 | 10 |
| `ask_company` | 76.92% | 0.8727 | 3 |
| `ask_purpose` | 76.92% | 0.8524 | 3 |
| `ask_robot` | 84.62% | 0.8383 | 2 |
| `ask_cost` | 92.31% | 0.9007 | 1 |
| `has_insurance` | 100.00% | 0.8815 | 0 |
| `request_callback` | 69.23% | 0.8532 | 4 |
| `provide_reject_reason` | 61.54% | 0.8520 | 5 |
| `silence` | 100.00% | 0.9470 | 0 |
| `ask_program_details` | 66.67% | 0.8201 | 4 |
| `ask_limits` | 91.67% | 0.8722 | 1 |
| `government_compensation` | 63.64% | 0.9186 | 4 |
| `ask_other_products` | 83.33% | 0.8471 | 2 |
| `request_extension` | 50.00% | 0.8480 | 6 |

## 3. Список ошибок

| Исходный интент | Фраза | Распознано как | Score |
|:---|:---|:---|:---|
| `confirm_yes` | `ага` | `None` | 0.0000 |
| `confirm_yes` | `угу` | `None` | 0.0000 |
| `confirm_yes` | `конеч` | `None` | 0.0000 |
| `confirm_no` | `отбой` | `None` | 0.0000 |
| `confirm_no` | `не хочу` | `provide_reject_reason` | 0.8986 |
| `confirm_no` | `нет, это` | `None` | 0.0000 |
| `confirm_no` | `не, не хочу` | `None` | 0.0000 |
| `ask_where_number` | `почему по этому` | `ask_purpose` | 0.8222 |
| `ask_where_number` | `почему вы мне` | `ask_purpose` | 0.7862 |
| `ask_previous_client` | `я делал расчет` | `has_insurance` | 0.8035 |
| `ask_previous_client` | `я страховался` | `has_insurance` | 0.9215 |
| `ask_previous_client` | `я покупал` | `has_insurance` | 0.8249 |
| `ask_previous_client` | `я уже` | `has_insurance` | 0.8266 |
| `ask_policy_used` | `я оформлял` | `has_insurance` | 0.8728 |
| `ask_policy_used` | `у меня был` | `None` | 0.0000 |
| `ask_policy_used` | `я пользовался` | `ask_previous_client` | 0.8560 |
| `ask_policy_used` | `у меня уже` | `has_insurance` | 0.8914 |
| `ask_policy_used` | `вы мне выдавали` | `None` | 0.0000 |
| `ask_policy_used` | `я покупал полис` | `None` | 0.0000 |
| `ask_policy_used` | `был ли у меня` | `ask_previous_client` | 0.8616 |
| `ask_policy_used` | `я брал страховку` | `None` | 0.0000 |
| `ask_policy_used` | `моя предыдущая` | `ask_previous_client` | 0.8373 |
| `ask_policy_used` | `я что-то покупал` | `has_insurance` | 0.7901 |
| `ask_company` | `кто звонит` | `ask_purpose` | 0.8654 |
| `ask_company` | `это какая` | `ask_program_details` | 0.8488 |
| `ask_company` | `как называется` | `None` | 0.0000 |
| `ask_purpose` | `зачем звоните` | `None` | 0.0000 |
| `ask_purpose` | `о чем речь` | `ask_program_details` | 0.9055 |
| `ask_purpose` | `что хотели` | `None` | 0.0000 |
| `ask_robot` | `со мной машина` | `None` | 0.0000 |
| `ask_robot` | `это программа` | `None` | 0.0000 |
| `ask_cost` | `почем` | `None` | 0.0000 |
| `request_callback` | `неудобно` | `provide_reject_reason` | 0.8207 |
| `request_callback` | `я не могу` | `provide_reject_reason` | 0.8243 |
| `request_callback` | `не сейчас` | `None` | 0.0000 |
| `request_callback` | `не могу говорить` | `None` | 0.0000 |
| `provide_reject_reason` | `дорого` | `ask_cost` | 0.8602 |
| `provide_reject_reason` | `не нужно` | `None` | 0.0000 |
| `provide_reject_reason` | `не подходит` | `None` | 0.0000 |
| `provide_reject_reason` | `не надо` | `confirm_no` | 0.8552 |
| `provide_reject_reason` | `нет, спасибо` | `confirm_no` | 0.8325 |
| `ask_program_details` | `о бастионе` | `None` | 0.0000 |
| `ask_program_details` | `что входит` | `None` | 0.0000 |
| `ask_program_details` | `что покрывает` | `None` | 0.0000 |
| `ask_program_details` | `что это` | `None` | 0.0000 |
| `ask_limits` | `какие там рамки` | `ask_program_details` | 0.7855 |
| `government_compensation` | `зачем, если есть` | `ask_purpose` | 0.8345 |
| `government_compensation` | `зачем, если платит` | `None` | 0.0000 |
| `government_compensation` | `меня спасет` | `has_insurance` | 0.7698 |
| `government_compensation` | `я рассчитываю` | `None` | 0.0000 |
| `ask_other_products` | `что еще` | `None` | 0.0000 |
| `ask_other_products` | `хочу узнать про` | `None` | 0.0000 |
| `request_extension` | `больше времени` | `None` | 0.0000 |
| `request_extension` | `оставьте ссылку` | `ask_where_number` | 0.7723 |
| `request_extension` | `могу оплатить` | `None` | 0.0000 |
| `request_extension` | `не получится` | `provide_reject_reason` | 0.8333 |
| `request_extension` | `дайте время` | `None` | 0.0000 |
| `request_extension` | `не сегодня` | `None` | 0.0000 |
