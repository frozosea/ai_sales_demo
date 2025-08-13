from typing import Dict, Any, Optional
import json

from domain.models import Task, FlowResult, SessionState
from flow_engine.utils import load_json_config

class FlowEngine:
    def __init__(self, goals_config_path: str, dialogue_map_path: str):
        self.goals = load_json_config(goals_config_path)
        self.dialogue_map = load_json_config(dialogue_map_path)

    def _get_goal_by_intent(self, intent_id: str) -> Optional[Dict[str, Any]]:
        # This is a simplified mapping. In a real scenario, you might have a more complex
        # mapping from intent to goal, or the intent ID might directly be the goal ID.
        if intent_id in self.goals:
            return self.goals[intent_id]
        
        # Fallback for intents that don't directly map to a goal name
        # This is important for intents like 'demand_final_answer_cost'
        for goal_id, goal_data in self.goals.items():
            if goal_id == intent_id or goal_data.get('intent') == intent_id:
                return goal_data
        return None

    def _find_next_required_param(self, goal: Dict[str, Any], session_variables: Dict[str, Any], force_mode: bool) -> Optional[Dict[str, Any]]:
        """Finds the next required parameter that is not yet filled."""
        for param in goal.get("parameters", []):
            # 1. Check if parameter is already filled
            if param["name"] in session_variables:
                continue

            # 2. Check if the parameter is required
            is_required_condition = param.get("is_required", False)
            required = False
            if isinstance(is_required_condition, bool):
                required = is_required_condition
            elif isinstance(is_required_condition, str):
                # SUPER DANGEROUS, but for this demo, we use eval.
                # In production, use a safe expression evaluator (e.g., `asteval`).
                try:
                    context = {"session": {"variables": session_variables}}
                    required = eval(is_required_condition, {}, context)
                except Exception:
                    # If evaluation fails, assume not required for safety.
                    required = False
            
            if required:
                return param
        return None

    def process_event(self, session_state: SessionState, intent_id: str) -> FlowResult:
        """
        Main event processing algorithm based on the specification.
        """
        task_stack = session_state.task_stack
        session_variables = session_state.variables
        current_dialogue_state_id = session_state.current_state_id
        
        goal_for_intent = self._get_goal_by_intent(intent_id)

        # PRIORITY 0: TERMINAL INTENT
        if goal_for_intent and goal_for_intent.get("is_terminal"):
            new_task = Task(goal_id=intent_id, status='IN_PROGRESS')
            task_stack = [new_task]
            # Simplified: assume the first transition from the ask state is the one we take.
            param_to_ask = goal_for_intent['parameters'][0]
            dialogue_state = self.dialogue_map[param_to_ask['dialogue_state_to_ask']]
            next_state = dialogue_state["transitions"][intent_id]["next_state"]
            return FlowResult(next_state=next_state, task_stack=task_stack)

        # PRIORITY 1: FORCING INTENT
        if goal_for_intent and goal_for_intent.get("is_forcing"):
            # Find the main business goal and force it
            main_task = next((t for t in reversed(task_stack) if not self.goals.get(t.goal_id, {}).get("is_digression")), None)
            if main_task:
                main_task.mode = 'FORCED'
                # Clean up digressions from the top of the stack
                while task_stack and self.goals.get(task_stack[-1].goal_id, {}).get("is_digression"):
                    task_stack.pop()
                
                # After forcing, immediately find the next required parameter to ask the forced question
                current_goal = self.goals[main_task.goal_id]
                next_param = self._find_next_required_param(current_goal, session_variables, force_mode=True)
                if next_param:
                    next_state = next_param.get("force_dialogue_state_to_ask", next_param["dialogue_state_to_ask"])
                    return FlowResult(next_state=next_state, task_stack=task_stack)

        # PRIORITY 2: USER-INITIATED RETURN
        if intent_id == 'return_to_main_goal' and len(task_stack) > 1:
            task_stack.pop()
            current_task = task_stack[-1]
            current_task.status = 'IN_PROGRESS'
            return FlowResult(next_state=current_task.return_state_id or "start_greeting", task_stack=task_stack)

        # PRIORITY 3: GLOBAL DIGRESSION (FAQ)
        if goal_for_intent and goal_for_intent.get("is_digression"):
            should_guide_back = len(task_stack) >= 3
            if task_stack:
                task_stack[-1].status = 'PAUSED'
                task_stack[-1].return_state_id = current_dialogue_state_id
            
            new_task = Task(goal_id=intent_id, status='IN_PROGRESS')
            task_stack.append(new_task)
            
            # Simplified: take the next state from the first transition
            dialogue_state_name_for_faq = goal_for_intent.get("dialogue_state_to_ask") or f"info_{intent_id.split('_')[-1]}"
            dialogue_state = self.dialogue_map.get(dialogue_state_name_for_faq, {})
            next_state = dialogue_state.get("transitions", {}).get(intent_id, {}).get("next_state")
            
            if not next_state:
                # Fallback if the structure is different
                next_state = dialogue_state.get("next_state", "fallback_faq_state")

            return FlowResult(next_state=next_state, should_guide_back=should_guide_back, task_stack=task_stack)
            
        # PRIORITY 4: PROCESS CURRENT TASK (HAPPY PATH)
        return self._process_current_task(task_stack, session_variables, current_dialogue_state_id, intent_id)

    def _process_current_task(self, task_stack: list[Task], session_variables: Dict[str, Any], current_dialogue_state_id: str, intent_id: str) -> FlowResult:
        if not task_stack:
            # Start of a new conversation
            main_goal_id = "provide_total_price"
            task_stack.append(Task(goal_id=main_goal_id, status='IN_PROGRESS'))

        current_task = task_stack[-1]
        current_goal = self.goals[current_task.goal_id]
        
        # --- Execute code for the current transition (not implemented for demo) ---

        if current_task.mode == 'FORCED':
            next_param = self._find_next_required_param(current_goal, session_variables, force_mode=True)
            if next_param:
                # Ask the forced question for this param
                next_state = next_param.get("force_dialogue_state_to_ask", next_param["dialogue_state_to_ask"])
                return FlowResult(next_state=next_state, task_stack=task_stack)
            else:
                # All params collected, finish the task
                current_task.status = 'COMPLETED' # You might want a completed status
                # Return a summary state
                return FlowResult(next_state="summary_single", task_stack=task_stack)

        else: # NORMAL mode
            # Find next required param
            next_param = self._find_next_required_param(current_goal, session_variables, force_mode=False)
            if next_param:
                return FlowResult(next_state=next_param["dialogue_state_to_ask"], task_stack=task_stack)
            
            # If no more params, maybe move to next state from dialogue map
            if current_dialogue_state_id and intent_id in self.dialogue_map.get(current_dialogue_state_id, {}).get("transitions", {}):
                next_state = self.dialogue_map[current_dialogue_state_id]["transitions"][intent_id]["next_state"]
                
                if next_state == "RUN_FORCE_CHECK":
                    current_task.mode = 'FORCED'
                    # After providing a value in a forced dialog, we immediately check for the next required param
                    return self._process_current_task(task_stack, session_variables, current_dialogue_state_id, intent_id)

                return FlowResult(next_state=next_state, task_stack=task_stack)
            
            # Fallback if no transition found, which is common. Ask for the next required param.
            next_param_after_transition = self._find_next_required_param(current_goal, session_variables, force_mode=False)
            if next_param_after_transition:
                 return FlowResult(next_state=next_param_after_transition["dialogue_state_to_ask"], task_stack=task_stack)

        # Default fallback if all params are filled or something went wrong.
        return FlowResult(next_state="summary_single", task_stack=task_stack)
