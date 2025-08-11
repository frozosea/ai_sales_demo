# Отчет о тестировании IntentClassifier
**Время генерации:** 2025-08-11 10:24:52

## 1. Сводная статистика

| Метрика | Значение |
|:---|:---|
| Общая точность (Accuracy) | 51.57% |
| Средняя уверенность (Score) | 0.8043 |
| P50 Latency (ms) | 44.45 |
| P95 Latency (ms) | 63.49 |

## 2. Результаты по интентам

| Интент | Точность | Ср. Score | Кол-во ошибок |
|:---|:---|:---|:---|
| `confirm_yes` | 75.00% | 0.7476 | 5 |
| `confirm_no` | 78.95% | 0.7605 | 4 |
| `provide_number` | 100.00% | 0.9500 | 0 |
| `ask_where_number` | 28.57% | 0.7103 | 10 |
| `ask_previous_client` | 23.08% | 0.7269 | 10 |
| `ask_policy_used` | 33.33% | 0.8321 | 8 |
| `ask_company` | 69.23% | 0.7662 | 4 |
| `ask_purpose` | 53.85% | 0.7616 | 6 |
| `ask_robot` | 38.46% | 0.7256 | 8 |
| `ask_cost` | 84.62% | 0.8079 | 2 |
| `has_insurance` | 50.00% | 0.7822 | 6 |
| `request_callback` | 15.38% | 0.7650 | 11 |
| `provide_reject_reason` | 0.00% | 0.0000 | 13 |
| `silence` | 100.00% | 0.9182 | 0 |
| `ask_program_details` | 0.00% | 0.0000 | 12 |
| `ask_limits` | 75.00% | 0.7592 | 3 |
| `government_compensation` | 63.64% | 0.8494 | 4 |
| `ask_other_products` | 58.33% | 0.7511 | 5 |
| `request_extension` | 0.00% | 0.0000 | 12 |

## 3. Список ошибок

| Исходный интент | Фраза | Распознано как | Score |
|:---|:---|:---|:---|
| `confirm_yes` | `ага` | `None` | 0.0000 |
| `confirm_yes` | `угу` | `None` | 0.0000 |
| `confirm_yes` | `я согласен` | `None` | 0.0000 |
| `confirm_yes` | `конеч` | `None` | 0.0000 |
| `confirm_yes` | `ага, давай` | `None` | 0.0000 |
| `confirm_no` | `отбой` | `None` | 0.0000 |
| `confirm_no` | `не хочу` | `None` | 0.0000 |
| `confirm_no` | `нет, это` | `None` | 0.0000 |
| `confirm_no` | `не, не хочу` | `None` | 0.0000 |
| `ask_where_number` | `где мой номер` | `None` | 0.0000 |
| `ask_where_number` | `кто вам дал` | `None` | 0.0000 |
| `ask_where_number` | `откуда знаете` | `None` | 0.0000 |
| `ask_where_number` | `как вы нашли` | `None` | 0.0000 |
| `ask_where_number` | `почему по этому` | `ask_purpose` | 0.7195 |
| `ask_where_number` | `как вы полу` | `None` | 0.0000 |
| `ask_where_number` | `с какого сайта` | `None` | 0.0000 |
| `ask_where_number` | `кто вам слил` | `None` | 0.0000 |
| `ask_where_number` | `откуда у вас` | `None` | 0.0000 |
| `ask_where_number` | `почему вы мне` | `None` | 0.0000 |
| `ask_previous_client` | `я ваш клиент?` | `None` | 0.0000 |
| `ask_previous_client` | `я у вас был?` | `None` | 0.0000 |
| `ask_previous_client` | `уже был клиентом` | `None` | 0.0000 |
| `ask_previous_client` | `я делал расчет` | `None` | 0.0000 |
| `ask_previous_client` | `я был клиентом ингос` | `None` | 0.0000 |
| `ask_previous_client` | `я страховался` | `None` | 0.0000 |
| `ask_previous_client` | `я покупал` | `None` | 0.0000 |
| `ask_previous_client` | `мы имели` | `None` | 0.0000 |
| `ask_previous_client` | `я был у вас` | `None` | 0.0000 |
| `ask_previous_client` | `я уже` | `has_insurance` | 0.7513 |
| `ask_policy_used` | `я оформлял` | `None` | 0.0000 |
| `ask_policy_used` | `у меня был` | `None` | 0.0000 |
| `ask_policy_used` | `я пользовался` | `None` | 0.0000 |
| `ask_policy_used` | `у меня уже` | `has_insurance` | 0.8101 |
| `ask_policy_used` | `был ли у меня` | `None` | 0.0000 |
| `ask_policy_used` | `я брал страховку` | `None` | 0.0000 |
| `ask_policy_used` | `моя предыдущая` | `None` | 0.0000 |
| `ask_policy_used` | `я что-то покупал` | `None` | 0.0000 |
| `ask_company` | `кто звонит` | `ask_purpose` | 0.7574 |
| `ask_company` | `откуда вы` | `None` | 0.0000 |
| `ask_company` | `это какая` | `None` | 0.0000 |
| `ask_company` | `как называется` | `None` | 0.0000 |
| `ask_purpose` | `зачем звоните` | `None` | 0.0000 |
| `ask_purpose` | `для чего вы` | `None` | 0.0000 |
| `ask_purpose` | `что вы хотите` | `None` | 0.0000 |
| `ask_purpose` | `о чем речь` | `None` | 0.0000 |
| `ask_purpose` | `что хотели` | `None` | 0.0000 |
| `ask_purpose` | `зачем вы мне` | `None` | 0.0000 |
| `ask_robot` | `со мной машина` | `None` | 0.0000 |
| `ask_robot` | `вы человек` | `None` | 0.0000 |
| `ask_robot` | `это голосовой` | `None` | 0.0000 |
| `ask_robot` | `вы человек или` | `None` | 0.0000 |
| `ask_robot` | `это запись` | `None` | 0.0000 |
| `ask_robot` | `это программа` | `None` | 0.0000 |
| `ask_robot` | `я с кем говорю` | `None` | 0.0000 |
| `ask_robot` | `я с ботом` | `None` | 0.0000 |
| `ask_cost` | `почем` | `None` | 0.0000 |
| `ask_cost` | `сколько?` | `None` | 0.0000 |
| `has_insurance` | `я застрахован` | `None` | 0.0000 |
| `has_insurance` | `у меня есть полис` | `None` | 0.0000 |
| `has_insurance` | `уже застраховал` | `None` | 0.0000 |
| `has_insurance` | `полис оформлен` | `None` | 0.0000 |
| `has_insurance` | `страховка есть` | `None` | 0.0000 |
| `has_insurance` | `я защитил` | `None` | 0.0000 |
| `request_callback` | `перезвоните` | `None` | 0.0000 |
| `request_callback` | `неудобно` | `None` | 0.0000 |
| `request_callback` | `давайте потом` | `None` | 0.0000 |
| `request_callback` | `я не могу` | `None` | 0.0000 |
| `request_callback` | `можно позже` | `None` | 0.0000 |
| `request_callback` | `не сейчас` | `None` | 0.0000 |
| `request_callback` | `отложите` | `None` | 0.0000 |
| `request_callback` | `давайте перенесем` | `None` | 0.0000 |
| `request_callback` | `не могу говорить` | `None` | 0.0000 |
| `request_callback` | `занят` | `None` | 0.0000 |
| `request_callback` | `попозже` | `None` | 0.0000 |
| `provide_reject_reason` | `не интересно` | `None` | 0.0000 |
| `provide_reject_reason` | `не устраивает` | `None` | 0.0000 |
| `provide_reject_reason` | `дорого` | `ask_cost` | 0.7698 |
| `provide_reject_reason` | `не хочу` | `None` | 0.0000 |
| `provide_reject_reason` | `не нужно` | `None` | 0.0000 |
| `provide_reject_reason` | `отказываюсь` | `None` | 0.0000 |
| `provide_reject_reason` | `не подходит` | `None` | 0.0000 |
| `provide_reject_reason` | `не планирую` | `None` | 0.0000 |
| `provide_reject_reason` | `не вижу смысла` | `None` | 0.0000 |
| `provide_reject_reason` | `не хочу обсуждать` | `None` | 0.0000 |
| `provide_reject_reason` | `не надо` | `None` | 0.0000 |
| `provide_reject_reason` | `нет, спасибо` | `confirm_no` | 0.7118 |
| `provide_reject_reason` | `это мне не интересно` | `None` | 0.0000 |
| `ask_program_details` | `что за программа` | `None` | 0.0000 |
| `ask_program_details` | `о бастионе` | `None` | 0.0000 |
| `ask_program_details` | `что за страховка` | `ask_policy_used` | 0.8015 |
| `ask_program_details` | `какие риски` | `None` | 0.0000 |
| `ask_program_details` | `в чем суть` | `None` | 0.0000 |
| `ask_program_details` | `что входит` | `None` | 0.0000 |
| `ask_program_details` | `что за продукт` | `None` | 0.0000 |
| `ask_program_details` | `подробнее про` | `None` | 0.0000 |
| `ask_program_details` | `чем полезна` | `None` | 0.0000 |
| `ask_program_details` | `что покрывает` | `None` | 0.0000 |
| `ask_program_details` | `что это` | `None` | 0.0000 |
| `ask_program_details` | `расскажите` | `None` | 0.0000 |
| `ask_limits` | `от какой суммы` | `None` | 0.0000 |
| `ask_limits` | `до какой суммы` | `None` | 0.0000 |
| `ask_limits` | `какие там рамки` | `None` | 0.0000 |
| `government_compensation` | `зачем, если есть` | `ask_purpose` | 0.7303 |
| `government_compensation` | `зачем, если платит` | `None` | 0.0000 |
| `government_compensation` | `меня спасет` | `None` | 0.0000 |
| `government_compensation` | `я рассчитываю` | `None` | 0.0000 |
| `ask_other_products` | `что еще` | `None` | 0.0000 |
| `ask_other_products` | `другие страховки` | `None` | 0.0000 |
| `ask_other_products` | `еще полисы` | `None` | 0.0000 |
| `ask_other_products` | `хочу узнать про` | `None` | 0.0000 |
| `ask_other_products` | `расскажите о других` | `None` | 0.0000 |
| `request_extension` | `не успею` | `None` | 0.0000 |
| `request_extension` | `оплачу позже` | `None` | 0.0000 |
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
