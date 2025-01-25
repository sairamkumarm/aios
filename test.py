from utils import get_params_and_context

output = get_params_and_context({"main_intent":"alarms","detailed_intent":"add_alarm"})
print(f"\n\n{output}")
