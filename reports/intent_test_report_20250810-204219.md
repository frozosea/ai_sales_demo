# Отчет о тестировании IntentClassifier
**Время генерации:** 2025-08-10 20:42:19

## 1. Сводная статистика

| Метрика | Значение |
|:---|:---|
| Общая точность (Accuracy) | 32.28% |
| Средняя уверенность (Score) | 0.7526 |
| P50 Latency (ms) | 1.62 |
| P95 Latency (ms) | 3.16 |

## 2. Результаты по интентам

| Интент | Точность | Ср. Score | Кол-во ошибок |
|:---|:---|:---|:---|
| `confirm_yes` | 50.00% | 0.7048 | 10 |
| `confirm_no` | 15.79% | 0.7963 | 16 |
| `provide_number` | 100.00% | 0.9500 | 0 |
| `ask_where_number` | 14.29% | 0.6017 | 12 |
| `ask_previous_client` | 15.38% | 0.5796 | 11 |
| `ask_policy_used` | 0.00% | 0.0000 | 12 |
| `ask_company` | 23.08% | 0.6063 | 10 |
| `ask_purpose` | 23.08% | 0.6200 | 10 |
| `ask_robot` | 15.38% | 0.6210 | 11 |
| `ask_cost` | 46.15% | 0.6652 | 7 |
| `has_insurance` | 41.67% | 0.6588 | 7 |
| `request_callback` | 15.38% | 0.6051 | 11 |
| `provide_reject_reason` | 30.77% | 0.6790 | 9 |
| `silence` | 100.00% | 0.9505 | 0 |
| `ask_program_details` | 0.00% | 0.0000 | 12 |
| `ask_limits` | 8.33% | 0.7005 | 11 |
| `government_compensation` | 54.55% | 0.6413 | 5 |
| `ask_other_products` | 25.00% | 0.5990 | 9 |
| `request_extension` | 25.00% | 0.5947 | 9 |

## 3. Список ошибок

| Исходный интент | Фраза | Распознано как | Score |
|:---|:---|:---|:---|
| `confirm_yes` | `да` | `None` | 0.0000 |
| `confirm_yes` | `ага` | `None` | 0.0000 |
| `confirm_yes` | `угу` | `None` | 0.0000 |
| `confirm_yes` | `верно` | `None` | 0.0000 |
| `confirm_yes` | `точно` | `None` | 0.0000 |
| `confirm_yes` | `конечно` | `None` | 0.0000 |
| `confirm_yes` | `подтверждаю` | `None` | 0.0000 |
| `confirm_yes` | `согласна` | `None` | 0.0000 |
| `confirm_yes` | `правильно` | `None` | 0.0000 |
| `confirm_yes` | `конеч` | `silence` | 0.6920 |
| `confirm_no` | `нет` | `silence` | 0.7876 |
| `confirm_no` | `не` | `silence` | 0.7812 |
| `confirm_no` | `не верно` | `confirm_yes` | 0.7256 |
| `confirm_no` | `неправильно` | `None` | 0.0000 |
| `confirm_no` | `отрицаю` | `None` | 0.0000 |
| `confirm_no` | `отмена` | `silence` | 0.7769 |
| `confirm_no` | `отбой` | `silence` | 0.6368 |
| `confirm_no` | `не согласен` | `None` | 0.0000 |
| `confirm_no` | `я против` | `None` | 0.0000 |
| `confirm_no` | `нет, не надо` | `None` | 0.0000 |
| `confirm_no` | `нет, спасибо` | `None` | 0.0000 |
| `confirm_no` | `не хочу` | `provide_reject_reason` | 0.7071 |
| `confirm_no` | `нет, это` | `None` | 0.0000 |
| `confirm_no` | `нет, не так` | `None` | 0.0000 |
| `confirm_no` | `нет, от` | `None` | 0.0000 |
| `confirm_no` | `не, не хочу` | `None` | 0.0000 |
| `ask_where_number` | `откуда номер` | `None` | 0.0000 |
| `ask_where_number` | `кто вам дал` | `None` | 0.0000 |
| `ask_where_number` | `откуда знаете` | `None` | 0.0000 |
| `ask_where_number` | `почему по этому` | `None` | 0.0000 |
| `ask_where_number` | `кто дал контакты` | `None` | 0.0000 |
| `ask_where_number` | `где взяли` | `silence` | 0.6023 |
| `ask_where_number` | `как вы полу` | `None` | 0.0000 |
| `ask_where_number` | `с какого сайта` | `None` | 0.0000 |
| `ask_where_number` | `кто вам слил` | `None` | 0.0000 |
| `ask_where_number` | `откуда у вас` | `None` | 0.0000 |
| `ask_where_number` | `почему вы мне` | `None` | 0.0000 |
| `ask_where_number` | `откуда инфа` | `silence` | 0.6214 |
| `ask_previous_client` | `я ваш клиент?` | `None` | 0.0000 |
| `ask_previous_client` | `мы работали?` | `None` | 0.0000 |
| `ask_previous_client` | `я у вас был?` | `None` | 0.0000 |
| `ask_previous_client` | `я делал расчет` | `None` | 0.0000 |
| `ask_previous_client` | `я был клиентом ингос` | `None` | 0.0000 |
| `ask_previous_client` | `я страховался` | `None` | 0.0000 |
| `ask_previous_client` | `я покупал` | `None` | 0.0000 |
| `ask_previous_client` | `мы имели` | `None` | 0.0000 |
| `ask_previous_client` | `я был у вас` | `None` | 0.0000 |
| `ask_previous_client` | `мы сотрудничали` | `None` | 0.0000 |
| `ask_previous_client` | `я уже` | `None` | 0.0000 |
| `ask_policy_used` | `я оформлял` | `None` | 0.0000 |
| `ask_policy_used` | `у меня был` | `None` | 0.0000 |
| `ask_policy_used` | `какой полис` | `None` | 0.0000 |
| `ask_policy_used` | `я пользовался` | `None` | 0.0000 |
| `ask_policy_used` | `у меня уже` | `has_insurance` | 0.6645 |
| `ask_policy_used` | `вы мне выдавали` | `None` | 0.0000 |
| `ask_policy_used` | `я покупал полис` | `None` | 0.0000 |
| `ask_policy_used` | `был ли у меня` | `None` | 0.0000 |
| `ask_policy_used` | `я брал страховку` | `None` | 0.0000 |
| `ask_policy_used` | `моя предыдущая` | `None` | 0.0000 |
| `ask_policy_used` | `я оформлял полис` | `None` | 0.0000 |
| `ask_policy_used` | `я что-то покупал` | `None` | 0.0000 |
| `ask_company` | `кто звонит` | `None` | 0.0000 |
| `ask_company` | `откуда вы` | `None` | 0.0000 |
| `ask_company` | `кто вы` | `None` | 0.0000 |
| `ask_company` | `вы кто` | `None` | 0.0000 |
| `ask_company` | `это какая` | `None` | 0.0000 |
| `ask_company` | `вы от какой` | `None` | 0.0000 |
| `ask_company` | `как называется` | `None` | 0.0000 |
| `ask_company` | `кто это` | `None` | 0.0000 |
| `ask_company` | `из какой вы` | `None` | 0.0000 |
| `ask_company` | `что за организация` | `None` | 0.0000 |
| `ask_purpose` | `зачем звоните` | `None` | 0.0000 |
| `ask_purpose` | `цель звонка` | `silence` | 0.6308 |
| `ask_purpose` | `для чего вы` | `None` | 0.0000 |
| `ask_purpose` | `что вы хотите` | `None` | 0.0000 |
| `ask_purpose` | `о чем речь` | `None` | 0.0000 |
| `ask_purpose` | `причина звонка` | `silence` | 0.6214 |
| `ask_purpose` | `почему мне` | `None` | 0.0000 |
| `ask_purpose` | `что хотели` | `None` | 0.0000 |
| `ask_purpose` | `с какой целью` | `None` | 0.0000 |
| `ask_purpose` | `зачем вы мне` | `None` | 0.0000 |
| `ask_robot` | `это автомат` | `None` | 0.0000 |
| `ask_robot` | `со мной машина` | `None` | 0.0000 |
| `ask_robot` | `вы человек` | `None` | 0.0000 |
| `ask_robot` | `это голосовой` | `None` | 0.0000 |
| `ask_robot` | `вы человек или` | `None` | 0.0000 |
| `ask_robot` | `это запись` | `None` | 0.0000 |
| `ask_robot` | `меня набрал бот` | `None` | 0.0000 |
| `ask_robot` | `это программа` | `None` | 0.0000 |
| `ask_robot` | `я с кем говорю` | `None` | 0.0000 |
| `ask_robot` | `это не человек` | `None` | 0.0000 |
| `ask_robot` | `я с ботом` | `None` | 0.0000 |
| `ask_cost` | `стоимость` | `silence` | 0.7297 |
| `ask_cost` | `сколько будет` | `None` | 0.0000 |
| `ask_cost` | `тарифы` | `silence` | 0.7151 |
| `ask_cost` | `ценник` | `None` | 0.0000 |
| `ask_cost` | `почем` | `None` | 0.0000 |
| `ask_cost` | `цена вопроса` | `None` | 0.0000 |
| `ask_cost` | `сколько?` | `None` | 0.0000 |
| `has_insurance` | `у меня есть` | `None` | 0.0000 |
| `has_insurance` | `я оформил` | `None` | 0.0000 |
| `has_insurance` | `я купил` | `None` | 0.0000 |
| `has_insurance` | `у меня действует` | `None` | 0.0000 |
| `has_insurance` | `полис оформлен` | `None` | 0.0000 |
| `has_insurance` | `я защитил` | `None` | 0.0000 |
| `has_insurance` | `я уже` | `None` | 0.0000 |
| `request_callback` | `перезвоните` | `None` | 0.0000 |
| `request_callback` | `неудобно` | `silence` | 0.7669 |
| `request_callback` | `давайте потом` | `None` | 0.0000 |
| `request_callback` | `я не могу` | `None` | 0.0000 |
| `request_callback` | `можно позже` | `None` | 0.0000 |
| `request_callback` | `не сейчас` | `None` | 0.0000 |
| `request_callback` | `отложите` | `None` | 0.0000 |
| `request_callback` | `давайте перенесем` | `None` | 0.0000 |
| `request_callback` | `не могу говорить` | `None` | 0.0000 |
| `request_callback` | `занят` | `silence` | 0.7811 |
| `request_callback` | `попозже` | `None` | 0.0000 |
| `provide_reject_reason` | `не интересно` | `None` | 0.0000 |
| `provide_reject_reason` | `не устраивает` | `None` | 0.0000 |
| `provide_reject_reason` | `дорого` | `silence` | 0.7408 |
| `provide_reject_reason` | `не нужно` | `None` | 0.0000 |
| `provide_reject_reason` | `отказываюсь` | `None` | 0.0000 |
| `provide_reject_reason` | `не подходит` | `None` | 0.0000 |
| `provide_reject_reason` | `не вижу смысла` | `None` | 0.0000 |
| `provide_reject_reason` | `не надо` | `None` | 0.0000 |
| `provide_reject_reason` | `нет, спасибо` | `None` | 0.0000 |
| `ask_program_details` | `что за программа` | `None` | 0.0000 |
| `ask_program_details` | `о бастионе` | `None` | 0.0000 |
| `ask_program_details` | `что за страховка` | `None` | 0.0000 |
| `ask_program_details` | `какие риски` | `None` | 0.0000 |
| `ask_program_details` | `в чем суть` | `None` | 0.0000 |
| `ask_program_details` | `что входит` | `None` | 0.0000 |
| `ask_program_details` | `что за продукт` | `None` | 0.0000 |
| `ask_program_details` | `подробнее про` | `None` | 0.0000 |
| `ask_program_details` | `чем полезна` | `None` | 0.0000 |
| `ask_program_details` | `что покрывает` | `None` | 0.0000 |
| `ask_program_details` | `что это` | `None` | 0.0000 |
| `ask_program_details` | `расскажите` | `silence` | 0.7566 |
| `ask_limits` | `минимальная сумма` | `None` | 0.0000 |
| `ask_limits` | `максимальная` | `silence` | 0.7721 |
| `ask_limits` | `лимит` | `silence` | 0.7803 |
| `ask_limits` | `от какой суммы` | `None` | 0.0000 |
| `ask_limits` | `до какой суммы` | `None` | 0.0000 |
| `ask_limits` | `сколько минимум` | `None` | 0.0000 |
| `ask_limits` | `сколько максимум` | `None` | 0.0000 |
| `ask_limits` | `ограничения по сумме` | `None` | 0.0000 |
| `ask_limits` | `мин и макс` | `None` | 0.0000 |
| `ask_limits` | `какие там рамки` | `None` | 0.0000 |
| `ask_limits` | `какой потолок` | `None` | 0.0000 |
| `government_compensation` | `зачем, если есть` | `None` | 0.0000 |
| `government_compensation` | `зачем, если платит` | `ask_cost` | 0.6226 |
| `government_compensation` | `меня спасет` | `None` | 0.0000 |
| `government_compensation` | `я рассчитываю` | `None` | 0.0000 |
| `government_compensation` | `ведь есть же выплаты` | `None` | 0.0000 |
| `ask_other_products` | `еще продукты` | `None` | 0.0000 |
| `ask_other_products` | `что еще` | `None` | 0.0000 |
| `ask_other_products` | `другие страховки` | `None` | 0.0000 |
| `ask_other_products` | `еще полисы` | `None` | 0.0000 |
| `ask_other_products` | `что еще можно` | `None` | 0.0000 |
| `ask_other_products` | `хочу узнать про` | `None` | 0.0000 |
| `ask_other_products` | `еще предложения` | `None` | 0.0000 |
| `ask_other_products` | `расскажите о других` | `None` | 0.0000 |
| `ask_other_products` | `кроме этого` | `None` | 0.0000 |
| `request_extension` | `не успею` | `None` | 0.0000 |
| `request_extension` | `больше времени` | `None` | 0.0000 |
| `request_extension` | `смогу через пару` | `None` | 0.0000 |
| `request_extension` | `оставьте ссылку` | `None` | 0.0000 |
| `request_extension` | `сейчас нет времени` | `None` | 0.0000 |
| `request_extension` | `могу оплатить` | `None` | 0.0000 |
| `request_extension` | `не получится` | `None` | 0.0000 |
| `request_extension` | `дайте время` | `None` | 0.0000 |
| `request_extension` | `не сегодня` | `None` | 0.0000 |
