import json

with open('intents.json','r') as file:
    data = json.load(file)

def get_main_intents():
    """Retrieve main intents from the JSON data."""
    return list(data.keys())

def get_detailed_intents(main_intent):
    """Retrieve detailed intents under a specified main intent."""
    if main_intent in data:
        return [intent["name"] for intent in data[main_intent]]
    return []

def get_params(intents):
    """Retrieve parameters for a specific detailed intent under a main intent."""
    main_intent, detailed_intent = intents["main_intent"],intents["detailed_intent"]
    if main_intent in data:
        for intent in data[main_intent]:
            if intent["name"] == detailed_intent:
                return intent.get("params", [])
    return []

def preoutput(status: str, main_intent: str, detailed_intent: str, params: dict, response: str):
    """Handles cases where either the main_intent, detailed_intent, or parameters are missing."""
    
    preoutput_data = {
        "status": status,
        "main_intent": main_intent,
        "detailed_intent": detailed_intent,
        "params": params,
        "response": response
    }
    
    # Return the preoutput as a formatted JSON string
    return json.dumps(preoutput_data)

