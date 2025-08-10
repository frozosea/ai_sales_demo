# Отчет о тестировании IntentClassifier
**Время генерации:** 2025-08-10 20:50:29

## 1. Сводная статистика

| Метрика | Значение |
|:---|:---|
| Общая точность (Accuracy) | 46.46% |
| Средняя уверенность (Score) | 0.6627 |
| P50 Latency (ms) | 2.69 |
| P95 Latency (ms) | 5.41 |

## 2. Результаты по интентам

| Интент | Точность | Ср. Score | Кол-во ошибок |
|:---|:---|:---|:---|
| `confirm_yes` | 85.00% | 0.6446 | 3 |
| `confirm_no` | 31.58% | 0.6367 | 13 |
| `provide_number` | 100.00% | 0.9500 | 0 |
| `ask_where_number` | 21.43% | 0.5830 | 11 |
| `ask_previous_client` | 23.08% | 0.5231 | 10 |
| `ask_policy_used` | 8.33% | 0.6165 | 11 |
| `ask_company` | 15.38% | 0.5953 | 11 |
| `ask_purpose` | 61.54% | 0.5339 | 5 |
| `ask_robot` | 15.38% | 0.4662 | 11 |
| `ask_cost` | 61.54% | 0.6176 | 5 |
| `has_insurance` | 83.33% | 0.6099 | 2 |
| `request_callback` | 38.46% | 0.5311 | 8 |
| `provide_reject_reason` | 46.15% | 0.5668 | 7 |
| `silence` | 100.00% | 0.9204 | 0 |
| `ask_program_details` | 0.00% | 0.0000 | 12 |
| `ask_limits` | 41.67% | 0.5234 | 7 |
| `government_compensation` | 54.55% | 0.6042 | 5 |
| `ask_other_products` | 50.00% | 0.4787 | 6 |
| `request_extension` | 25.00% | 0.4881 | 9 |

## 3. Список ошибок

| Исходный интент | Фраза | Распознано как | Score |
|:---|:---|:---|:---|
| `confirm_yes` | `угу` | `None` | 0.0000 |
| `confirm_yes` | `конеч` | `None` | 0.0000 |
| `confirm_yes` | `ага, давай` | `None` | 0.0000 |
| `confirm_no` | `нет` | `None` | 0.0000 |
| `confirm_no` | `не` | `None` | 0.0000 |
| `confirm_no` | `не верно` | `confirm_yes` | 0.5570 |
| `confirm_no` | `неправильно` | `None` | 0.0000 |
| `confirm_no` | `отмена` | `None` | 0.0000 |
| `confirm_no` | `отбой` | `None` | 0.0000 |
| `confirm_no` | `я против` | `None` | 0.0000 |
| `confirm_no` | `нет, спасибо` | `None` | 0.0000 |
| `confirm_no` | `не хочу` | `provide_reject_reason` | 0.6248 |
| `confirm_no` | `нет, это` | `None` | 0.0000 |
| `confirm_no` | `нет, не так` | `None` | 0.0000 |
| `confirm_no` | `нет, от` | `None` | 0.0000 |
| `confirm_no` | `не, не хочу` | `None` | 0.0000 |
| `ask_where_number` | `кто вам дал` | `None` | 0.0000 |
| `ask_where_number` | `откуда знаете` | `None` | 0.0000 |
| `ask_where_number` | `как вы нашли` | `None` | 0.0000 |
| `ask_where_number` | `почему по этому` | `ask_purpose` | 0.4288 |
| `ask_where_number` | `кто дал контакты` | `None` | 0.0000 |
| `ask_where_number` | `где взяли` | `None` | 0.0000 |
| `ask_where_number` | `как вы полу` | `None` | 0.0000 |
| `ask_where_number` | `с какого сайта` | `None` | 0.0000 |
| `ask_where_number` | `кто вам слил` | `None` | 0.0000 |
| `ask_where_number` | `почему вы мне` | `None` | 0.0000 |
| `ask_where_number` | `откуда инфа` | `None` | 0.0000 |
| `ask_previous_client` | `я ваш клиент?` | `None` | 0.0000 |
| `ask_previous_client` | `я у вас был?` | `None` | 0.0000 |
| `ask_previous_client` | `уже был клиентом` | `None` | 0.0000 |
| `ask_previous_client` | `я делал расчет` | `None` | 0.0000 |
| `ask_previous_client` | `я был клиентом ингос` | `None` | 0.0000 |
| `ask_previous_client` | `я страховался` | `has_insurance` | 0.6593 |
| `ask_previous_client` | `я покупал` | `None` | 0.0000 |
| `ask_previous_client` | `мы имели` | `None` | 0.0000 |
| `ask_previous_client` | `мы сотрудничали` | `None` | 0.0000 |
| `ask_previous_client` | `я уже` | `has_insurance` | 0.6063 |
| `ask_policy_used` | `я оформлял` | `None` | 0.0000 |
| `ask_policy_used` | `у меня был` | `None` | 0.0000 |
| `ask_policy_used` | `я пользовался` | `None` | 0.0000 |
| `ask_policy_used` | `у меня уже` | `has_insurance` | 0.6468 |
| `ask_policy_used` | `вы мне выдавали` | `None` | 0.0000 |
| `ask_policy_used` | `я покупал полис` | `None` | 0.0000 |
| `ask_policy_used` | `был ли у меня` | `None` | 0.0000 |
| `ask_policy_used` | `я брал страховку` | `None` | 0.0000 |
| `ask_policy_used` | `моя предыдущая` | `has_insurance` | 0.4268 |
| `ask_policy_used` | `я оформлял полис` | `None` | 0.0000 |
| `ask_policy_used` | `я что-то покупал` | `has_insurance` | 0.5194 |
| `ask_company` | `кто звонит` | `ask_purpose` | 0.5602 |
| `ask_company` | `откуда вы` | `None` | 0.0000 |
| `ask_company` | `кто вы` | `None` | 0.0000 |
| `ask_company` | `вы кто` | `None` | 0.0000 |
| `ask_company` | `что за фирма` | `None` | 0.0000 |
| `ask_company` | `это какая` | `None` | 0.0000 |
| `ask_company` | `вы от какой` | `None` | 0.0000 |
| `ask_company` | `как называется` | `None` | 0.0000 |
| `ask_company` | `кто это` | `None` | 0.0000 |
| `ask_company` | `из какой вы` | `None` | 0.0000 |
| `ask_company` | `что за организация` | `None` | 0.0000 |
| `ask_purpose` | `зачем звоните` | `None` | 0.0000 |
| `ask_purpose` | `о чем речь` | `None` | 0.0000 |
| `ask_purpose` | `почему мне` | `None` | 0.0000 |
| `ask_purpose` | `в чем дело` | `None` | 0.0000 |
| `ask_purpose` | `что хотели` | `None` | 0.0000 |
| `ask_robot` | `я с роботом` | `None` | 0.0000 |
| `ask_robot` | `со мной машина` | `None` | 0.0000 |
| `ask_robot` | `вы человек` | `None` | 0.0000 |
| `ask_robot` | `это голосовой` | `None` | 0.0000 |
| `ask_robot` | `вы человек или` | `None` | 0.0000 |
| `ask_robot` | `это запись` | `None` | 0.0000 |
| `ask_robot` | `меня набрал бот` | `None` | 0.0000 |
| `ask_robot` | `это программа` | `None` | 0.0000 |
| `ask_robot` | `я с кем говорю` | `None` | 0.0000 |
| `ask_robot` | `это не человек` | `confirm_no` | 0.5096 |
| `ask_robot` | `я с ботом` | `None` | 0.0000 |
| `ask_cost` | `сколько будет` | `provide_number` | 0.5895 |
| `ask_cost` | `ценник` | `None` | 0.0000 |
| `ask_cost` | `почем` | `None` | 0.0000 |
| `ask_cost` | `сколько денег` | `None` | 0.0000 |
| `ask_cost` | `сколько?` | `None` | 0.0000 |
| `has_insurance` | `у меня есть полис` | `None` | 0.0000 |
| `has_insurance` | `полис оформлен` | `None` | 0.0000 |
| `request_callback` | `перезвоните` | `None` | 0.0000 |
| `request_callback` | `неудобно` | `None` | 0.0000 |
| `request_callback` | `я не могу` | `None` | 0.0000 |
| `request_callback` | `можно позже` | `None` | 0.0000 |
| `request_callback` | `не сейчас` | `None` | 0.0000 |
| `request_callback` | `не могу говорить` | `silence` | 0.4138 |
| `request_callback` | `занят` | `silence` | 0.5465 |
| `request_callback` | `попозже` | `None` | 0.0000 |
| `provide_reject_reason` | `не устраивает` | `None` | 0.0000 |
| `provide_reject_reason` | `дорого` | `ask_cost` | 0.5796 |
| `provide_reject_reason` | `не нужно` | `None` | 0.0000 |
| `provide_reject_reason` | `отказываюсь` | `None` | 0.0000 |
| `provide_reject_reason` | `не подходит` | `None` | 0.0000 |
| `provide_reject_reason` | `не надо` | `None` | 0.0000 |
| `provide_reject_reason` | `нет, спасибо` | `None` | 0.0000 |
| `ask_program_details` | `что за программа` | `None` | 0.0000 |
| `ask_program_details` | `о бастионе` | `None` | 0.0000 |
| `ask_program_details` | `что за страховка` | `has_insurance` | 0.5286 |
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
| `ask_limits` | `сколько минимум` | `None` | 0.0000 |
| `ask_limits` | `сколько максимум` | `None` | 0.0000 |
| `ask_limits` | `мин и макс` | `None` | 0.0000 |
| `ask_limits` | `какие там рамки` | `None` | 0.0000 |
| `ask_limits` | `какой потолок` | `None` | 0.0000 |
| `government_compensation` | `зачем, если есть` | `ask_purpose` | 0.4729 |
| `government_compensation` | `зачем, если платит` | `None` | 0.0000 |
| `government_compensation` | `меня спасет` | `None` | 0.0000 |
| `government_compensation` | `я рассчитываю` | `has_insurance` | 0.5165 |
| `government_compensation` | `ведь есть же выплаты` | `confirm_yes` | 0.4658 |
| `ask_other_products` | `что еще` | `None` | 0.0000 |
| `ask_other_products` | `еще полисы` | `None` | 0.0000 |
| `ask_other_products` | `что еще можно` | `None` | 0.0000 |
| `ask_other_products` | `хочу узнать про` | `None` | 0.0000 |
| `ask_other_products` | `а что еще есть` | `None` | 0.0000 |
| `ask_other_products` | `кроме этого` | `None` | 0.0000 |
| `request_extension` | `смогу через пару` | `None` | 0.0000 |
| `request_extension` | `оставьте ссылку` | `None` | 0.0000 |
| `request_extension` | `я оплачу потом` | `None` | 0.0000 |
| `request_extension` | `сейчас нет времени` | `None` | 0.0000 |
| `request_extension` | `могу оплатить` | `has_insurance` | 0.4902 |
| `request_extension` | `позже оформлю` | `None` | 0.0000 |
| `request_extension` | `не получится` | `confirm_no` | 0.4157 |
| `request_extension` | `дайте время` | `request_callback` | 0.5013 |
| `request_extension` | `не сегодня` | `None` | 0.0000 |
