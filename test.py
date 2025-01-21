from utils import preoutput


input_data = {
    "status": "MISSING_PARAMS",
    "main_intent": "file_operation",
    "detailed_intent": "Move",
    "params": {"source_folder": "Downloads", "destination_folder": "MISSING", "contents": "*"},
    "response": "Where should I move the files to?"
}

output = preoutput(
    status=input_data["status"],
    main_intent=input_data["main_intent"],
    detailed_intent=input_data["detailed_intent"],
    params=input_data["params"],
    response=input_data["response"]
)

print(output)
