import json
from pathlib import Path
from flow_engine.engine import FlowEngine
from domain.models import FlowResult, Task, SessionState

def run_stress_test():
    """
    Запускает стресс-тест для FlowEngine, симулируя сложный диалог.
    """
    goals_path = "configs/goals.json"
    dialogue_map_path = "configs/dialogue_flow.json"
    
    engine = FlowEngine(goals_config_path=goals_path, dialogue_map_path=dialogue_map_path)
    
    def get_initial_session() -> SessionState:
        return SessionState(
            call_id="stress_test_call",
            variables={},
            task_stack=[],
            current_state_id="start_greeting" # A more realistic starting point
        )

    def print_state(scenario: str, action: str, result: FlowResult):
        print(f"--- SCENARIO: {scenario} ---")
        print(f"ACTION: {action}")
        print(f"Next State: {result.next_state}")
        print(f"Should Guide Back: {result.should_guide_back}")
        print("Task Stack:")
        if not result.task_stack:
            print("  <empty>")
        for i, task in enumerate(result.task_stack):
            print(f"  [{i}] Goal: {task.goal_id}, Status: {task.status}, Mode: {task.mode}, Return: {task.return_state_id}")
        print("-" * 60 + "\n")

    def run_interaction(session: SessionState, intent: str, scenario_name: str, action_description: str) -> FlowResult:
        result = engine.process_event(session, intent)
        session.task_stack = result.task_stack
        session.current_state_id = result.next_state
        print_state(scenario_name, action_description, result)
        return result

    # =================================================================
    # --- Сценарий: "Супер-хаотичный пользователь" ---
    # =================================================================
    scenario_name = "Super-Chaotic User Journey"
    session = get_initial_session()
    
    # 1. Начинаем, пользователь подтверждает имя
    run_interaction(session, "start_dialogue", scenario_name, "1. Start & provide name")
    session.variables['contact_name'] = 'Александр'
    
    # 2. Пользователь сразу уходит в сторону
    run_interaction(session, "ask_company", scenario_name, "2. User asks about the company (digression 1)")
    
    # 3. Не дослушав, задает еще один вопрос
    run_interaction(session, "ask_robot", scenario_name, "3. User asks if it's a robot (digression 2)")
    
    # 4. Пользователь внезапно требует цену (из глубины стека)
    run_interaction(session, "demand_final_answer_cost", scenario_name, "4. User DEMANDS the price (forcing)")
    
    # 5. Движок должен был очистить стек от прерываний и задать форсированный вопрос.
    # Пользователь отвечает.
    session.variables['property_value'] = 5000000
    run_interaction(session, "provide_number", scenario_name, "5. User provides property value")
    
    # 6. Движок в режиме FORCED, должен спросить про страховку отделки.
    # Но пользователь снова перебивает и спрашивает про гос. компенсацию.
    run_interaction(session, "government_compensation", scenario_name, "6. User asks about gov help (digression while FORCED)")
    
    # 7. Пользователь решает вернуться
    run_interaction(session, "return_to_main_goal", scenario_name, "7. User returns to the main goal")
    
    # 8. Движок все еще в FORCED режиме и должен продолжить сбор данных.
    # Пользователь соглашается на страховку отделки.
    session.variables['wants_inner_insurance'] = True
    run_interaction(session, "confirm_yes", scenario_name, "8. User agrees to inner insurance")
    
    # 9. Пользователь предоставляет сумму отделки.
    session.variables['inner_amount'] = 1000000
    run_interaction(session, "provide_number", scenario_name, "9. User provides inner amount")
    
    # 10. Остался только адрес. Но пользователь решает отказаться.
    run_interaction(session, "provide_reject_reason", scenario_name, "10. User suddenly refuses the whole deal (TERMINAL)")

    print("===== STRESS TEST COMPLETED =====")
    print("Final session state:")
    print(session.model_dump_json(indent=2))


if __name__ == "__main__":
    run_stress_test()
