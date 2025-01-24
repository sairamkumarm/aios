from utils import get_detailed_intents, get_main_intents, get_params

output = get_params({"main_intent":"file_operation","detailed_intent":"move_file"})
print(f"\n\n{output}")
