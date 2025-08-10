# Отчет о тестировании IntentClassifier
**Время генерации:** 2025-08-10 20:24:33

## 1. Сводная статистика

| Метрика | Значение |
|:---|:---|
| Общая точность (Accuracy) | 40.94% |
| Средняя уверенность (Score) | 0.7558 |
| P50 Latency (ms) | 4.80 |
| P95 Latency (ms) | 7.48 |

## 2. Результаты по интентам

| Интент | Точность | Ср. Score | Кол-во ошибок |
|:---|:---|:---|:---|
| `confirm_yes` | 95.00% | 0.8492 | 1 |
| `confirm_no` | 78.95% | 0.7276 | 4 |
| `provide_number` | 100.00% | 0.9500 | 0 |
| `ask_where_number` | 14.29% | 0.6355 | 12 |
| `ask_previous_client` | 7.69% | 0.4883 | 12 |
| `ask_policy_used` | 25.00% | 0.5685 | 9 |
| `ask_company` | 30.77% | 0.5873 | 9 |
| `ask_purpose` | 15.38% | 0.6127 | 11 |
| `ask_robot` | 15.38% | 0.5205 | 11 |
| `ask_cost` | 61.54% | 0.6643 | 5 |
| `has_insurance` | 33.33% | 0.6480 | 8 |
| `request_callback` | 38.46% | 0.6755 | 8 |
| `provide_reject_reason` | 15.38% | 0.6149 | 11 |
| `silence` | 75.00% | 1.0000 | 2 |
| `ask_program_details` | 8.33% | 0.5644 | 11 |
| `ask_limits` | 25.00% | 0.6405 | 9 |
| `government_compensation` | 54.55% | 0.5774 | 5 |
| `ask_other_products` | 16.67% | 0.4805 | 10 |
| `request_extension` | 0.00% | 0.0000 | 12 |

## 3. Список ошибок

| Исходный интент | Фраза | Распознано как | Score |
|:---|:---|:---|:---|
| `confirm_yes` | `конеч` | `None` | 0.0000 |
| `confirm_no` | `отмена` | `None` | 0.0000 |
| `confirm_no` | `отбой` | `None` | 0.0000 |
| `confirm_no` | `не хочу` | `None` | 0.0000 |
| `confirm_no` | `не, не хочу` | `None` | 0.0000 |
| `ask_where_number` | `откуда номер` | `provide_number` | 0.8157 |
| `ask_where_number` | `кто вам дал` | `None` | 0.0000 |
| `ask_where_number` | `откуда знаете` | `confirm_yes` | 0.5433 |
| `ask_where_number` | `как вы нашли` | `confirm_yes` | 0.4774 |
| `ask_where_number` | `почему по этому` | `confirm_yes` | 0.5182 |
| `ask_where_number` | `где взяли` | `confirm_yes` | 0.5611 |
| `ask_where_number` | `как вы полу` | `confirm_yes` | 0.5974 |
| `ask_where_number` | `с какого сайта` | `None` | 0.0000 |
| `ask_where_number` | `кто вам слил` | `None` | 0.0000 |
| `ask_where_number` | `откуда у вас` | `None` | 0.0000 |
| `ask_where_number` | `почему вы мне` | `None` | 0.0000 |
| `ask_where_number` | `откуда инфа` | `None` | 0.0000 |
| `ask_previous_client` | `мы работали?` | `None` | 0.0000 |
| `ask_previous_client` | `я у вас был?` | `None` | 0.0000 |
| `ask_previous_client` | `уже был клиентом` | `None` | 0.0000 |
| `ask_previous_client` | `я делал расчет` | `None` | 0.0000 |
| `ask_previous_client` | `мы раньше` | `None` | 0.0000 |
| `ask_previous_client` | `я был клиентом ингос` | `None` | 0.0000 |
| `ask_previous_client` | `я страховался` | `ask_policy_used` | 0.5982 |
| `ask_previous_client` | `я покупал` | `ask_policy_used` | 0.5315 |
| `ask_previous_client` | `мы имели` | `confirm_yes` | 0.5923 |
| `ask_previous_client` | `я был у вас` | `None` | 0.0000 |
| `ask_previous_client` | `мы сотрудничали` | `confirm_yes` | 0.4456 |
| `ask_previous_client` | `я уже` | `confirm_yes` | 0.7297 |
| `ask_policy_used` | `я оформлял` | `None` | 0.0000 |
| `ask_policy_used` | `у меня был` | `None` | 0.0000 |
| `ask_policy_used` | `какой полис` | `confirm_yes` | 0.5173 |
| `ask_policy_used` | `я пользовался` | `confirm_yes` | 0.6006 |
| `ask_policy_used` | `у меня уже` | `confirm_yes` | 0.6397 |
| `ask_policy_used` | `вы мне выдавали` | `None` | 0.0000 |
| `ask_policy_used` | `я брал страховку` | `None` | 0.0000 |
| `ask_policy_used` | `моя предыдущая` | `None` | 0.0000 |
| `ask_policy_used` | `я оформлял полис` | `None` | 0.0000 |
| `ask_company` | `кто звонит` | `ask_purpose` | 0.6630 |
| `ask_company` | `откуда вы` | `None` | 0.0000 |
| `ask_company` | `кто вы` | `None` | 0.0000 |
| `ask_company` | `вы кто` | `None` | 0.0000 |
| `ask_company` | `это какая` | `confirm_yes` | 0.7188 |
| `ask_company` | `вы от какой` | `None` | 0.0000 |
| `ask_company` | `как называется` | `None` | 0.0000 |
| `ask_company` | `кто это` | `None` | 0.0000 |
| `ask_company` | `из какой вы` | `None` | 0.0000 |
| `ask_purpose` | `зачем звоните` | `None` | 0.0000 |
| `ask_purpose` | `по какому поводу` | `confirm_yes` | 0.6948 |
| `ask_purpose` | `для чего вы` | `None` | 0.0000 |
| `ask_purpose` | `что вы хотите` | `confirm_yes` | 0.5580 |
| `ask_purpose` | `о чем речь` | `None` | 0.0000 |
| `ask_purpose` | `почему мне` | `confirm_yes` | 0.5040 |
| `ask_purpose` | `по какому вопросу` | `None` | 0.0000 |
| `ask_purpose` | `в чем дело` | `confirm_yes` | 0.6602 |
| `ask_purpose` | `что хотели` | `None` | 0.0000 |
| `ask_purpose` | `с какой целью` | `confirm_yes` | 0.4822 |
| `ask_purpose` | `зачем вы мне` | `None` | 0.0000 |
| `ask_robot` | `это автомат` | `None` | 0.0000 |
| `ask_robot` | `со мной машина` | `None` | 0.0000 |
| `ask_robot` | `вы человек` | `confirm_yes` | 0.5487 |
| `ask_robot` | `это голосовой` | `None` | 0.0000 |
| `ask_robot` | `вы человек или` | `confirm_yes` | 0.5132 |
| `ask_robot` | `это запись` | `None` | 0.0000 |
| `ask_robot` | `меня набрал бот` | `None` | 0.0000 |
| `ask_robot` | `это программа` | `ask_program_details` | 0.5598 |
| `ask_robot` | `я с кем говорю` | `None` | 0.0000 |
| `ask_robot` | `это не человек` | `confirm_no` | 0.4890 |
| `ask_robot` | `я с ботом` | `confirm_yes` | 0.6181 |
| `ask_cost` | `сколько будет` | `None` | 0.0000 |
| `ask_cost` | `сколько обойдется` | `None` | 0.0000 |
| `ask_cost` | `ценник` | `None` | 0.0000 |
| `ask_cost` | `почем` | `None` | 0.0000 |
| `ask_cost` | `сколько?` | `provide_number` | 0.6771 |
| `has_insurance` | `у меня есть` | `confirm_yes` | 0.6050 |
| `has_insurance` | `я оформил` | `None` | 0.0000 |
| `has_insurance` | `я купил` | `None` | 0.0000 |
| `has_insurance` | `у меня действует` | `confirm_yes` | 0.6970 |
| `has_insurance` | `полис оформлен` | `confirm_yes` | 0.5372 |
| `has_insurance` | `я защитил` | `None` | 0.0000 |
| `has_insurance` | `у меня уже есть` | `None` | 0.0000 |
| `has_insurance` | `я уже` | `confirm_yes` | 0.7297 |
| `request_callback` | `перезвоните` | `None` | 0.0000 |
| `request_callback` | `неудобно` | `None` | 0.0000 |
| `request_callback` | `я не могу` | `None` | 0.0000 |
| `request_callback` | `не сейчас` | `confirm_no` | 0.5670 |
| `request_callback` | `отложите` | `None` | 0.0000 |
| `request_callback` | `давайте перенесем` | `None` | 0.0000 |
| `request_callback` | `не могу говорить` | `None` | 0.0000 |
| `request_callback` | `занят` | `None` | 0.0000 |
| `provide_reject_reason` | `не интересно` | `confirm_no` | 0.6842 |
| `provide_reject_reason` | `не устраивает` | `confirm_no` | 0.6880 |
| `provide_reject_reason` | `дорого` | `ask_cost` | 0.5361 |
| `provide_reject_reason` | `не хочу` | `None` | 0.0000 |
| `provide_reject_reason` | `не нужно` | `confirm_no` | 0.7111 |
| `provide_reject_reason` | `отказываюсь` | `confirm_no` | 0.7113 |
| `provide_reject_reason` | `не подходит` | `confirm_no` | 0.7273 |
| `provide_reject_reason` | `не планирую` | `None` | 0.0000 |
| `provide_reject_reason` | `не вижу смысла` | `None` | 0.0000 |
| `provide_reject_reason` | `не надо` | `confirm_no` | 0.7694 |
| `provide_reject_reason` | `нет, спасибо` | `confirm_no` | 0.6336 |
| `silence` | ` ` | `confirm_yes` | 0.7244 |
| `silence` | `` | `confirm_yes` | 0.7244 |
| `ask_program_details` | `о бастионе` | `None` | 0.0000 |
| `ask_program_details` | `что за страховка` | `None` | 0.0000 |
| `ask_program_details` | `какие риски` | `None` | 0.0000 |
| `ask_program_details` | `в чем суть` | `confirm_yes` | 0.6262 |
| `ask_program_details` | `что входит` | `None` | 0.0000 |
| `ask_program_details` | `что за продукт` | `None` | 0.0000 |
| `ask_program_details` | `подробнее про` | `confirm_yes` | 0.6408 |
| `ask_program_details` | `чем полезна` | `confirm_yes` | 0.5358 |
| `ask_program_details` | `что покрывает` | `None` | 0.0000 |
| `ask_program_details` | `что это` | `None` | 0.0000 |
| `ask_program_details` | `расскажите` | `confirm_yes` | 0.7144 |
| `ask_limits` | `максимальная` | `None` | 0.0000 |
| `ask_limits` | `лимит` | `None` | 0.0000 |
| `ask_limits` | `от какой суммы` | `None` | 0.0000 |
| `ask_limits` | `до какой суммы` | `None` | 0.0000 |
| `ask_limits` | `сколько минимум` | `None` | 0.0000 |
| `ask_limits` | `сколько максимум` | `None` | 0.0000 |
| `ask_limits` | `мин и макс` | `None` | 0.0000 |
| `ask_limits` | `какие там рамки` | `None` | 0.0000 |
| `ask_limits` | `какой потолок` | `None` | 0.0000 |
| `government_compensation` | `зачем, если есть` | `confirm_yes` | 0.6910 |
| `government_compensation` | `зачем, если платит` | `None` | 0.0000 |
| `government_compensation` | `меня спасет` | `confirm_yes` | 0.5242 |
| `government_compensation` | `я рассчитываю` | `None` | 0.0000 |
| `government_compensation` | `ведь есть же выплаты` | `None` | 0.0000 |
| `ask_other_products` | `что еще` | `None` | 0.0000 |
| `ask_other_products` | `другие страховки` | `None` | 0.0000 |
| `ask_other_products` | `еще полисы` | `confirm_yes` | 0.6070 |
| `ask_other_products` | `что еще можно` | `confirm_yes` | 0.6151 |
| `ask_other_products` | `хочу узнать про` | `confirm_yes` | 0.6527 |
| `ask_other_products` | `еще предложения` | `None` | 0.0000 |
| `ask_other_products` | `расскажите о других` | `None` | 0.0000 |
| `ask_other_products` | `какие еще программы` | `ask_program_details` | 0.5004 |
| `ask_other_products` | `а что еще есть` | `confirm_yes` | 0.5474 |
| `ask_other_products` | `кроме этого` | `None` | 0.0000 |
| `request_extension` | `не успею` | `confirm_no` | 0.6804 |
| `request_extension` | `оплачу позже` | `None` | 0.0000 |
| `request_extension` | `больше времени` | `None` | 0.0000 |
| `request_extension` | `смогу через пару` | `confirm_yes` | 0.5731 |
| `request_extension` | `оставьте ссылку` | `confirm_yes` | 0.4883 |
| `request_extension` | `я оплачу потом` | `None` | 0.0000 |
| `request_extension` | `сейчас нет времени` | `None` | 0.0000 |
| `request_extension` | `могу оплатить` | `confirm_yes` | 0.5529 |
| `request_extension` | `позже оформлю` | `None` | 0.0000 |
| `request_extension` | `не получится` | `confirm_no` | 0.6975 |
| `request_extension` | `дайте время` | `None` | 0.0000 |
| `request_extension` | `не сегодня` | `confirm_no` | 0.4824 |
