# Отчет о тестировании IntentClassifier
**Время генерации:** 2025-08-11 09:52:03

## 1. Сводная статистика

| Метрика | Значение |
|:---|:---|
| Общая точность (Accuracy) | 46.46% |
| Средняя уверенность (Score) | 0.7837 |
| P50 Latency (ms) | 41.92 |
| P95 Latency (ms) | 54.18 |

## 2. Результаты по интентам

| Интент | Точность | Ср. Score | Кол-во ошибок |
|:---|:---|:---|:---|
| `confirm_yes` | 75.00% | 0.7412 | 5 |
| `confirm_no` | 31.58% | 0.7142 | 13 |
| `provide_number` | 100.00% | 0.9500 | 0 |
| `ask_where_number` | 21.43% | 0.7462 | 11 |
| `ask_previous_client` | 23.08% | 0.6927 | 10 |
| `ask_policy_used` | 8.33% | 0.8255 | 11 |
| `ask_company` | 46.15% | 0.7378 | 7 |
| `ask_purpose` | 53.85% | 0.7691 | 6 |
| `ask_robot` | 30.77% | 0.7197 | 9 |
| `ask_cost` | 69.23% | 0.7762 | 4 |
| `has_insurance` | 75.00% | 0.7864 | 3 |
| `request_callback` | 23.08% | 0.7390 | 10 |
| `provide_reject_reason` | 15.38% | 0.7062 | 11 |
| `silence` | 37.50% | 0.6634 | 5 |
| `ask_program_details` | 8.33% | 0.7657 | 11 |
| `ask_limits` | 91.67% | 0.7717 | 1 |
| `government_compensation` | 54.55% | 0.8239 | 5 |
| `ask_other_products` | 75.00% | 0.7257 | 3 |
| `request_extension` | 8.33% | 0.7733 | 11 |

## 3. Список ошибок

| Исходный интент | Фраза | Распознано как | Score |
|:---|:---|:---|:---|
| `confirm_yes` | `ага` | `None` | 0.0000 |
| `confirm_yes` | `угу` | `None` | 0.0000 |
| `confirm_yes` | `правильно` | `None` | 0.0000 |
| `confirm_yes` | `конеч` | `None` | 0.0000 |
| `confirm_yes` | `ага, давай` | `None` | 0.0000 |
| `confirm_no` | `неа` | `None` | 0.0000 |
| `confirm_no` | `неправильно` | `None` | 0.0000 |
| `confirm_no` | `отрицаю` | `None` | 0.0000 |
| `confirm_no` | `отмена` | `None` | 0.0000 |
| `confirm_no` | `отбой` | `None` | 0.0000 |
| `confirm_no` | `не согласен` | `None` | 0.0000 |
| `confirm_no` | `я против` | `None` | 0.0000 |
| `confirm_no` | `нет, не надо` | `None` | 0.0000 |
| `confirm_no` | `нет, спасибо` | `None` | 0.0000 |
| `confirm_no` | `не хочу` | `None` | 0.0000 |
| `confirm_no` | `нет, это` | `None` | 0.0000 |
| `confirm_no` | `нет, от` | `None` | 0.0000 |
| `confirm_no` | `не, не хочу` | `None` | 0.0000 |
| `ask_where_number` | `откуда номер` | `None` | 0.0000 |
| `ask_where_number` | `кто вам дал` | `None` | 0.0000 |
| `ask_where_number` | `откуда знаете` | `None` | 0.0000 |
| `ask_where_number` | `как вы нашли` | `None` | 0.0000 |
| `ask_where_number` | `почему по этому` | `ask_purpose` | 0.6914 |
| `ask_where_number` | `как вы полу` | `None` | 0.0000 |
| `ask_where_number` | `с какого сайта` | `None` | 0.0000 |
| `ask_where_number` | `кто вам слил` | `None` | 0.0000 |
| `ask_where_number` | `откуда у вас` | `None` | 0.0000 |
| `ask_where_number` | `почему вы мне` | `None` | 0.0000 |
| `ask_where_number` | `откуда инфа` | `None` | 0.0000 |
| `ask_previous_client` | `я ваш клиент?` | `None` | 0.0000 |
| `ask_previous_client` | `я у вас был?` | `None` | 0.0000 |
| `ask_previous_client` | `уже был клиентом` | `None` | 0.0000 |
| `ask_previous_client` | `я делал расчет` | `None` | 0.0000 |
| `ask_previous_client` | `я был клиентом ингос` | `None` | 0.0000 |
| `ask_previous_client` | `я страховался` | `has_insurance` | 0.8633 |
| `ask_previous_client` | `я покупал` | `None` | 0.0000 |
| `ask_previous_client` | `мы имели` | `None` | 0.0000 |
| `ask_previous_client` | `я был у вас` | `None` | 0.0000 |
| `ask_previous_client` | `я уже` | `has_insurance` | 0.7250 |
| `ask_policy_used` | `я оформлял` | `None` | 0.0000 |
| `ask_policy_used` | `у меня был` | `None` | 0.0000 |
| `ask_policy_used` | `я пользовался` | `None` | 0.0000 |
| `ask_policy_used` | `у меня уже` | `has_insurance` | 0.7799 |
| `ask_policy_used` | `вы мне выдавали` | `None` | 0.0000 |
| `ask_policy_used` | `я покупал полис` | `None` | 0.0000 |
| `ask_policy_used` | `был ли у меня` | `None` | 0.0000 |
| `ask_policy_used` | `я брал страховку` | `None` | 0.0000 |
| `ask_policy_used` | `моя предыдущая` | `None` | 0.0000 |
| `ask_policy_used` | `я оформлял полис` | `None` | 0.0000 |
| `ask_policy_used` | `я что-то покупал` | `None` | 0.0000 |
| `ask_company` | `кто звонит` | `ask_purpose` | 0.8246 |
| `ask_company` | `откуда вы` | `None` | 0.0000 |
| `ask_company` | `вы кто` | `None` | 0.0000 |
| `ask_company` | `это какая` | `None` | 0.0000 |
| `ask_company` | `вы от какой` | `None` | 0.0000 |
| `ask_company` | `как называется` | `None` | 0.0000 |
| `ask_company` | `из какой вы` | `None` | 0.0000 |
| `ask_purpose` | `о чем речь` | `None` | 0.0000 |
| `ask_purpose` | `почему мне` | `None` | 0.0000 |
| `ask_purpose` | `по какому вопросу` | `None` | 0.0000 |
| `ask_purpose` | `в чем дело` | `None` | 0.0000 |
| `ask_purpose` | `с какой целью` | `None` | 0.0000 |
| `ask_purpose` | `зачем вы мне` | `None` | 0.0000 |
| `ask_robot` | `со мной машина` | `None` | 0.0000 |
| `ask_robot` | `вы человек` | `None` | 0.0000 |
| `ask_robot` | `это голосовой` | `None` | 0.0000 |
| `ask_robot` | `вы человек или` | `None` | 0.0000 |
| `ask_robot` | `это запись` | `None` | 0.0000 |
| `ask_robot` | `это программа` | `None` | 0.0000 |
| `ask_robot` | `я с кем говорю` | `None` | 0.0000 |
| `ask_robot` | `это не человек` | `None` | 0.0000 |
| `ask_robot` | `я с ботом` | `None` | 0.0000 |
| `ask_cost` | `сколько будет` | `None` | 0.0000 |
| `ask_cost` | `почем` | `ask_purpose` | 0.6679 |
| `ask_cost` | `сколько денег` | `None` | 0.0000 |
| `ask_cost` | `сколько?` | `None` | 0.0000 |
| `has_insurance` | `у меня есть полис` | `None` | 0.0000 |
| `has_insurance` | `у меня действует` | `None` | 0.0000 |
| `has_insurance` | `полис оформлен` | `None` | 0.0000 |
| `request_callback` | `перезвоните` | `None` | 0.0000 |
| `request_callback` | `неудобно` | `None` | 0.0000 |
| `request_callback` | `позвоните позже` | `None` | 0.0000 |
| `request_callback` | `я не могу` | `None` | 0.0000 |
| `request_callback` | `можно позже` | `None` | 0.0000 |
| `request_callback` | `не сейчас` | `None` | 0.0000 |
| `request_callback` | `отложите` | `None` | 0.0000 |
| `request_callback` | `не могу говорить` | `None` | 0.0000 |
| `request_callback` | `занят` | `None` | 0.0000 |
| `request_callback` | `попозже` | `None` | 0.0000 |
| `provide_reject_reason` | `не интересно` | `None` | 0.0000 |
| `provide_reject_reason` | `не устраивает` | `None` | 0.0000 |
| `provide_reject_reason` | `дорого` | `ask_cost` | 0.7053 |
| `provide_reject_reason` | `не хочу` | `None` | 0.0000 |
| `provide_reject_reason` | `не нужно` | `None` | 0.0000 |
| `provide_reject_reason` | `отказываюсь` | `None` | 0.0000 |
| `provide_reject_reason` | `не подходит` | `None` | 0.0000 |
| `provide_reject_reason` | `не планирую` | `None` | 0.0000 |
| `provide_reject_reason` | `не надо` | `None` | 0.0000 |
| `provide_reject_reason` | `нет, спасибо` | `None` | 0.0000 |
| `provide_reject_reason` | `это мне не интересно` | `None` | 0.0000 |
| `silence` | `хм` | `None` | 0.0000 |
| `silence` | `ммм` | `None` | 0.0000 |
| `silence` | `эм` | `None` | 0.0000 |
| `silence` | `ааа` | `None` | 0.0000 |
| `silence` | `эээ` | `confirm_yes` | 0.6413 |
| `ask_program_details` | `что за программа` | `None` | 0.0000 |
| `ask_program_details` | `что за страховка` | `None` | 0.0000 |
| `ask_program_details` | `какие риски` | `None` | 0.0000 |
| `ask_program_details` | `в чем суть` | `None` | 0.0000 |
| `ask_program_details` | `что входит` | `None` | 0.0000 |
| `ask_program_details` | `что за продукт` | `None` | 0.0000 |
| `ask_program_details` | `подробнее про` | `None` | 0.0000 |
| `ask_program_details` | `чем полезна` | `None` | 0.0000 |
| `ask_program_details` | `что покрывает` | `None` | 0.0000 |
| `ask_program_details` | `что это` | `None` | 0.0000 |
| `ask_program_details` | `расскажите` | `None` | 0.0000 |
| `ask_limits` | `какие там рамки` | `None` | 0.0000 |
| `government_compensation` | `зачем, если есть` | `ask_purpose` | 0.7240 |
| `government_compensation` | `зачем, если платит` | `None` | 0.0000 |
| `government_compensation` | `меня спасет` | `None` | 0.0000 |
| `government_compensation` | `я рассчитываю` | `None` | 0.0000 |
| `government_compensation` | `ведь есть же выплаты` | `None` | 0.0000 |
| `ask_other_products` | `другие страховки` | `None` | 0.0000 |
| `ask_other_products` | `еще полисы` | `None` | 0.0000 |
| `ask_other_products` | `хочу узнать про` | `None` | 0.0000 |
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
