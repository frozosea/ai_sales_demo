# Отчет о тестировании IntentClassifier
**Время генерации:** 2025-08-11 09:48:13

## 1. Сводная статистика

| Метрика | Значение |
|:---|:---|
| Общая точность (Accuracy) | 37.40% |
| Средняя уверенность (Score) | 0.7780 |
| P50 Latency (ms) | 45.94 |
| P95 Latency (ms) | 70.61 |

## 2. Результаты по интентам

| Интент | Точность | Ср. Score | Кол-во ошибок |
|:---|:---|:---|:---|
| `confirm_yes` | 75.00% | 0.6949 | 5 |
| `confirm_no` | 73.68% | 0.7034 | 5 |
| `provide_number` | 100.00% | 0.9500 | 0 |
| `ask_where_number` | 50.00% | 0.7147 | 7 |
| `ask_previous_client` | 0.00% | 0.0000 | 13 |
| `ask_policy_used` | 0.00% | 0.0000 | 12 |
| `ask_company` | 15.38% | 0.7350 | 11 |
| `ask_purpose` | 23.08% | 0.7199 | 10 |
| `ask_robot` | 23.08% | 0.6890 | 10 |
| `ask_cost` | 69.23% | 0.7262 | 4 |
| `has_insurance` | 16.67% | 0.7501 | 10 |
| `request_callback` | 15.38% | 0.8078 | 11 |
| `provide_reject_reason` | 0.00% | 0.0000 | 13 |
| `silence` | 75.00% | 1.0000 | 2 |
| `ask_program_details` | 8.33% | 0.7055 | 11 |
| `ask_limits` | 41.67% | 0.6805 | 7 |
| `government_compensation` | 45.45% | 0.7422 | 6 |
| `ask_other_products` | 16.67% | 0.7106 | 10 |
| `request_extension` | 0.00% | 0.0000 | 12 |

## 3. Список ошибок

| Исходный интент | Фраза | Распознано как | Score |
|:---|:---|:---|:---|
| `confirm_yes` | `ага` | `None` | 0.0000 |
| `confirm_yes` | `угу` | `None` | 0.0000 |
| `confirm_yes` | `правильно` | `None` | 0.0000 |
| `confirm_yes` | `конеч` | `None` | 0.0000 |
| `confirm_yes` | `ага, давай` | `None` | 0.0000 |
| `confirm_no` | `отбой` | `None` | 0.0000 |
| `confirm_no` | `нет, не надо` | `None` | 0.0000 |
| `confirm_no` | `нет, спасибо` | `None` | 0.0000 |
| `confirm_no` | `нет, это` | `None` | 0.0000 |
| `confirm_no` | `нет, от` | `None` | 0.0000 |
| `ask_where_number` | `кто вам дал` | `None` | 0.0000 |
| `ask_where_number` | `как вы нашли` | `None` | 0.0000 |
| `ask_where_number` | `почему по этому` | `None` | 0.0000 |
| `ask_where_number` | `как вы полу` | `None` | 0.0000 |
| `ask_where_number` | `с какого сайта` | `None` | 0.0000 |
| `ask_where_number` | `кто вам слил` | `None` | 0.0000 |
| `ask_where_number` | `почему вы мне` | `None` | 0.0000 |
| `ask_previous_client` | `я ваш клиент?` | `None` | 0.0000 |
| `ask_previous_client` | `мы работали?` | `None` | 0.0000 |
| `ask_previous_client` | `я у вас был?` | `None` | 0.0000 |
| `ask_previous_client` | `уже был клиентом` | `None` | 0.0000 |
| `ask_previous_client` | `я делал расчет` | `None` | 0.0000 |
| `ask_previous_client` | `мы раньше` | `None` | 0.0000 |
| `ask_previous_client` | `я был клиентом ингос` | `None` | 0.0000 |
| `ask_previous_client` | `я страховался` | `None` | 0.0000 |
| `ask_previous_client` | `я покупал` | `None` | 0.0000 |
| `ask_previous_client` | `мы имели` | `None` | 0.0000 |
| `ask_previous_client` | `я был у вас` | `None` | 0.0000 |
| `ask_previous_client` | `мы сотрудничали` | `None` | 0.0000 |
| `ask_previous_client` | `я уже` | `has_insurance` | 0.7146 |
| `ask_policy_used` | `я оформлял` | `None` | 0.0000 |
| `ask_policy_used` | `у меня был` | `None` | 0.0000 |
| `ask_policy_used` | `какой полис` | `None` | 0.0000 |
| `ask_policy_used` | `я пользовался` | `None` | 0.0000 |
| `ask_policy_used` | `у меня уже` | `has_insurance` | 0.7706 |
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
| `ask_company` | `какую фирму` | `None` | 0.0000 |
| `ask_company` | `это какая` | `None` | 0.0000 |
| `ask_company` | `вы от какой` | `None` | 0.0000 |
| `ask_company` | `как называется` | `None` | 0.0000 |
| `ask_company` | `кто это` | `None` | 0.0000 |
| `ask_company` | `из какой вы` | `None` | 0.0000 |
| `ask_company` | `что за организация` | `None` | 0.0000 |
| `ask_purpose` | `зачем звоните` | `None` | 0.0000 |
| `ask_purpose` | `цель звонка` | `None` | 0.0000 |
| `ask_purpose` | `по какому поводу` | `None` | 0.0000 |
| `ask_purpose` | `о чем речь` | `None` | 0.0000 |
| `ask_purpose` | `причина звонка` | `None` | 0.0000 |
| `ask_purpose` | `почему мне` | `None` | 0.0000 |
| `ask_purpose` | `по какому вопросу` | `None` | 0.0000 |
| `ask_purpose` | `в чем дело` | `None` | 0.0000 |
| `ask_purpose` | `что хотели` | `None` | 0.0000 |
| `ask_purpose` | `зачем вы мне` | `None` | 0.0000 |
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
| `ask_cost` | `сколько будет` | `None` | 0.0000 |
| `ask_cost` | `почем` | `None` | 0.0000 |
| `ask_cost` | `сколько денег` | `None` | 0.0000 |
| `ask_cost` | `сколько?` | `None` | 0.0000 |
| `has_insurance` | `у меня есть` | `None` | 0.0000 |
| `has_insurance` | `я оформил` | `None` | 0.0000 |
| `has_insurance` | `я застрахован` | `None` | 0.0000 |
| `has_insurance` | `у меня есть полис` | `None` | 0.0000 |
| `has_insurance` | `я купил` | `None` | 0.0000 |
| `has_insurance` | `уже застраховал` | `None` | 0.0000 |
| `has_insurance` | `у меня действует` | `None` | 0.0000 |
| `has_insurance` | `полис оформлен` | `None` | 0.0000 |
| `has_insurance` | `страховка есть` | `None` | 0.0000 |
| `has_insurance` | `я защитил` | `None` | 0.0000 |
| `request_callback` | `перезвоните` | `None` | 0.0000 |
| `request_callback` | `неудобно` | `None` | 0.0000 |
| `request_callback` | `давайте потом` | `None` | 0.0000 |
| `request_callback` | `я не могу` | `confirm_no` | 0.7057 |
| `request_callback` | `можно позже` | `None` | 0.0000 |
| `request_callback` | `не сейчас` | `None` | 0.0000 |
| `request_callback` | `отложите` | `None` | 0.0000 |
| `request_callback` | `давайте перенесем` | `None` | 0.0000 |
| `request_callback` | `не могу говорить` | `silence` | 0.7172 |
| `request_callback` | `занят` | `None` | 0.0000 |
| `request_callback` | `попозже` | `None` | 0.0000 |
| `provide_reject_reason` | `не интересно` | `None` | 0.0000 |
| `provide_reject_reason` | `не устраивает` | `None` | 0.0000 |
| `provide_reject_reason` | `дорого` | `ask_cost` | 0.6390 |
| `provide_reject_reason` | `не хочу` | `confirm_no` | 0.7243 |
| `provide_reject_reason` | `не нужно` | `None` | 0.0000 |
| `provide_reject_reason` | `отказываюсь` | `None` | 0.0000 |
| `provide_reject_reason` | `не подходит` | `confirm_no` | 0.7003 |
| `provide_reject_reason` | `не планирую` | `None` | 0.0000 |
| `provide_reject_reason` | `не вижу смысла` | `None` | 0.0000 |
| `provide_reject_reason` | `не хочу обсуждать` | `None` | 0.0000 |
| `provide_reject_reason` | `не надо` | `None` | 0.0000 |
| `provide_reject_reason` | `нет, спасибо` | `None` | 0.0000 |
| `provide_reject_reason` | `это мне не интересно` | `None` | 0.0000 |
| `silence` | ` ` | `None` | 0.0000 |
| `silence` | `` | `None` | 0.0000 |
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
| `ask_limits` | `минимальная сумма` | `None` | 0.0000 |
| `ask_limits` | `от какой суммы` | `None` | 0.0000 |
| `ask_limits` | `до какой суммы` | `None` | 0.0000 |
| `ask_limits` | `сколько минимум` | `None` | 0.0000 |
| `ask_limits` | `мин и макс` | `None` | 0.0000 |
| `ask_limits` | `какие там рамки` | `None` | 0.0000 |
| `ask_limits` | `какой потолок` | `None` | 0.0000 |
| `government_compensation` | `зачем, если есть` | `None` | 0.0000 |
| `government_compensation` | `зачем, если платит` | `None` | 0.0000 |
| `government_compensation` | `государство платит` | `None` | 0.0000 |
| `government_compensation` | `меня спасет` | `None` | 0.0000 |
| `government_compensation` | `я рассчитываю` | `None` | 0.0000 |
| `government_compensation` | `ведь есть же выплаты` | `None` | 0.0000 |
| `ask_other_products` | `еще продукты` | `None` | 0.0000 |
| `ask_other_products` | `что еще` | `None` | 0.0000 |
| `ask_other_products` | `другие страховки` | `None` | 0.0000 |
| `ask_other_products` | `еще полисы` | `None` | 0.0000 |
| `ask_other_products` | `другие продукты` | `None` | 0.0000 |
| `ask_other_products` | `хочу узнать про` | `None` | 0.0000 |
| `ask_other_products` | `еще предложения` | `None` | 0.0000 |
| `ask_other_products` | `расскажите о других` | `None` | 0.0000 |
| `ask_other_products` | `какие еще программы` | `None` | 0.0000 |
| `ask_other_products` | `кроме этого` | `None` | 0.0000 |
| `request_extension` | `не успею` | `None` | 0.0000 |
| `request_extension` | `оплачу позже` | `None` | 0.0000 |
| `request_extension` | `больше времени` | `None` | 0.0000 |
| `request_extension` | `смогу через пару` | `None` | 0.0000 |
| `request_extension` | `оставьте ссылку` | `None` | 0.0000 |
| `request_extension` | `я оплачу потом` | `None` | 0.0000 |
| `request_extension` | `сейчас нет времени` | `request_callback` | 0.6861 |
| `request_extension` | `могу оплатить` | `None` | 0.0000 |
| `request_extension` | `позже оформлю` | `None` | 0.0000 |
| `request_extension` | `не получится` | `None` | 0.0000 |
| `request_extension` | `дайте время` | `None` | 0.0000 |
| `request_extension` | `не сегодня` | `None` | 0.0000 |
