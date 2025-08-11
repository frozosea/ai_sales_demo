# Отчет о тестировании IntentClassifier
**Время генерации:** 2025-08-11 10:32:11

## 1. Сводная статистика

| Метрика | Значение |
|:---|:---|
| Общая точность (Accuracy) | 56.30% |
| Средняя уверенность (Score) | 0.8869 |
| P50 Latency (ms) | 43.68 |
| P95 Latency (ms) | 63.11 |

## 2. Результаты по интентам

| Интент | Точность | Ср. Score | Кол-во ошибок |
|:---|:---|:---|:---|
| `confirm_yes` | 80.00% | 0.8786 | 4 |
| `confirm_no` | 57.89% | 0.8895 | 8 |
| `provide_number` | 100.00% | 0.9500 | 0 |
| `ask_where_number` | 71.43% | 0.8421 | 4 |
| `ask_previous_client` | 61.54% | 0.8494 | 5 |
| `ask_policy_used` | 0.00% | 0.0000 | 12 |
| `ask_company` | 53.85% | 0.8809 | 6 |
| `ask_purpose` | 23.08% | 0.8952 | 10 |
| `ask_robot` | 61.54% | 0.8484 | 5 |
| `ask_cost` | 84.62% | 0.9028 | 2 |
| `has_insurance` | 50.00% | 0.9053 | 6 |
| `request_callback` | 30.77% | 0.8708 | 9 |
| `provide_reject_reason` | 38.46% | 0.8396 | 8 |
| `silence` | 100.00% | 0.9470 | 0 |
| `ask_program_details` | 33.33% | 0.7933 | 8 |
| `ask_limits` | 75.00% | 0.8623 | 3 |
| `government_compensation` | 54.55% | 0.9351 | 5 |
| `ask_other_products` | 58.33% | 0.8636 | 5 |
| `request_extension` | 8.33% | 0.8637 | 11 |

## 3. Список ошибок

| Исходный интент | Фраза | Распознано как | Score |
|:---|:---|:---|:---|
| `confirm_yes` | `ага` | `None` | 0.0000 |
| `confirm_yes` | `угу` | `None` | 0.0000 |
| `confirm_yes` | `конеч` | `None` | 0.0000 |
| `confirm_yes` | `ага, давай` | `None` | 0.0000 |
| `confirm_no` | `отмена` | `None` | 0.0000 |
| `confirm_no` | `отбой` | `None` | 0.0000 |
| `confirm_no` | `я против` | `None` | 0.0000 |
| `confirm_no` | `нет, не надо` | `None` | 0.0000 |
| `confirm_no` | `нет, спасибо` | `None` | 0.0000 |
| `confirm_no` | `не хочу` | `None` | 0.0000 |
| `confirm_no` | `нет, это` | `None` | 0.0000 |
| `confirm_no` | `не, не хочу` | `None` | 0.0000 |
| `ask_where_number` | `кто вам дал` | `None` | 0.0000 |
| `ask_where_number` | `почему по этому` | `None` | 0.0000 |
| `ask_where_number` | `кто вам слил` | `None` | 0.0000 |
| `ask_where_number` | `почему вы мне` | `None` | 0.0000 |
| `ask_previous_client` | `я делал расчет` | `None` | 0.0000 |
| `ask_previous_client` | `я страховался` | `None` | 0.0000 |
| `ask_previous_client` | `я покупал` | `None` | 0.0000 |
| `ask_previous_client` | `я был у вас` | `None` | 0.0000 |
| `ask_previous_client` | `я уже` | `None` | 0.0000 |
| `ask_policy_used` | `я оформлял` | `None` | 0.0000 |
| `ask_policy_used` | `у меня был` | `None` | 0.0000 |
| `ask_policy_used` | `какой полис` | `None` | 0.0000 |
| `ask_policy_used` | `я пользовался` | `None` | 0.0000 |
| `ask_policy_used` | `у меня уже` | `has_insurance` | 0.8914 |
| `ask_policy_used` | `вы мне выдавали` | `None` | 0.0000 |
| `ask_policy_used` | `я покупал полис` | `None` | 0.0000 |
| `ask_policy_used` | `был ли у меня` | `None` | 0.0000 |
| `ask_policy_used` | `я брал страховку` | `None` | 0.0000 |
| `ask_policy_used` | `моя предыдущая` | `None` | 0.0000 |
| `ask_policy_used` | `я оформлял полис` | `None` | 0.0000 |
| `ask_policy_used` | `я что-то покупал` | `None` | 0.0000 |
| `ask_company` | `кто звонит` | `None` | 0.0000 |
| `ask_company` | `откуда вы` | `None` | 0.0000 |
| `ask_company` | `это какая` | `None` | 0.0000 |
| `ask_company` | `как называется` | `None` | 0.0000 |
| `ask_company` | `кто это` | `None` | 0.0000 |
| `ask_company` | `из какой вы` | `None` | 0.0000 |
| `ask_purpose` | `зачем звоните` | `None` | 0.0000 |
| `ask_purpose` | `для чего вы` | `None` | 0.0000 |
| `ask_purpose` | `что вы хотите` | `None` | 0.0000 |
| `ask_purpose` | `о чем речь` | `None` | 0.0000 |
| `ask_purpose` | `почему мне` | `None` | 0.0000 |
| `ask_purpose` | `по какому вопросу` | `None` | 0.0000 |
| `ask_purpose` | `в чем дело` | `None` | 0.0000 |
| `ask_purpose` | `что хотели` | `None` | 0.0000 |
| `ask_purpose` | `с какой целью` | `None` | 0.0000 |
| `ask_purpose` | `зачем вы мне` | `None` | 0.0000 |
| `ask_robot` | `со мной машина` | `None` | 0.0000 |
| `ask_robot` | `вы человек` | `None` | 0.0000 |
| `ask_robot` | `вы человек или` | `None` | 0.0000 |
| `ask_robot` | `это программа` | `None` | 0.0000 |
| `ask_robot` | `я с кем говорю` | `None` | 0.0000 |
| `ask_cost` | `почем` | `None` | 0.0000 |
| `ask_cost` | `сколько?` | `None` | 0.0000 |
| `has_insurance` | `у меня есть полис` | `None` | 0.0000 |
| `has_insurance` | `я купил` | `None` | 0.0000 |
| `has_insurance` | `у меня действует` | `None` | 0.0000 |
| `has_insurance` | `полис оформлен` | `None` | 0.0000 |
| `has_insurance` | `я защитил` | `None` | 0.0000 |
| `has_insurance` | `я уже` | `None` | 0.0000 |
| `request_callback` | `перезвоните` | `None` | 0.0000 |
| `request_callback` | `неудобно` | `None` | 0.0000 |
| `request_callback` | `я не могу` | `None` | 0.0000 |
| `request_callback` | `можно позже` | `None` | 0.0000 |
| `request_callback` | `не сейчас` | `None` | 0.0000 |
| `request_callback` | `отложите` | `None` | 0.0000 |
| `request_callback` | `не могу говорить` | `None` | 0.0000 |
| `request_callback` | `занят` | `None` | 0.0000 |
| `request_callback` | `попозже` | `None` | 0.0000 |
| `provide_reject_reason` | `не устраивает` | `None` | 0.0000 |
| `provide_reject_reason` | `дорого` | `ask_cost` | 0.8602 |
| `provide_reject_reason` | `не хочу` | `None` | 0.0000 |
| `provide_reject_reason` | `не нужно` | `None` | 0.0000 |
| `provide_reject_reason` | `отказываюсь` | `None` | 0.0000 |
| `provide_reject_reason` | `не подходит` | `None` | 0.0000 |
| `provide_reject_reason` | `не надо` | `None` | 0.0000 |
| `provide_reject_reason` | `нет, спасибо` | `None` | 0.0000 |
| `ask_program_details` | `что за страховка` | `None` | 0.0000 |
| `ask_program_details` | `в чем суть` | `None` | 0.0000 |
| `ask_program_details` | `что входит` | `None` | 0.0000 |
| `ask_program_details` | `что за продукт` | `None` | 0.0000 |
| `ask_program_details` | `чем полезна` | `None` | 0.0000 |
| `ask_program_details` | `что покрывает` | `None` | 0.0000 |
| `ask_program_details` | `что это` | `None` | 0.0000 |
| `ask_program_details` | `расскажите` | `None` | 0.0000 |
| `ask_limits` | `от какой суммы` | `None` | 0.0000 |
| `ask_limits` | `до какой суммы` | `None` | 0.0000 |
| `ask_limits` | `какие там рамки` | `None` | 0.0000 |
| `government_compensation` | `зачем, если есть` | `None` | 0.0000 |
| `government_compensation` | `зачем, если платит` | `None` | 0.0000 |
| `government_compensation` | `меня спасет` | `None` | 0.0000 |
| `government_compensation` | `я рассчитываю` | `None` | 0.0000 |
| `government_compensation` | `ведь есть же выплаты` | `None` | 0.0000 |
| `ask_other_products` | `что еще` | `None` | 0.0000 |
| `ask_other_products` | `другие страховки` | `None` | 0.0000 |
| `ask_other_products` | `хочу узнать про` | `None` | 0.0000 |
| `ask_other_products` | `расскажите о других` | `None` | 0.0000 |
| `ask_other_products` | `какие еще программы` | `None` | 0.0000 |
| `request_extension` | `не успею` | `None` | 0.0000 |
| `request_extension` | `больше времени` | `None` | 0.0000 |
| `request_extension` | `смогу через пару` | `None` | 0.0000 |
| `request_extension` | `оставьте ссылку` | `None` | 0.0000 |
| `request_extension` | `я оплачу потом` | `None` | 0.0000 |
| `request_extension` | `сейчас нет времени` | `None` | 0.0000 |
| `request_extension` | `могу оплатить` | `None` | 0.0000 |
| `request_extension` | `позже оформлю` | `None` | 0.0000 |
| `request_extension` | `не получится` | `None` | 0.0000 |
| `request_extension` | `дайте время` | `None` | 0.0000 |
| `request_extension` | `не сегодня` | `None` | 0.0000 |
