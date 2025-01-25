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

def get_params_and_context(intents):
    """Retrieve parameters for a specific detailed intent under a main intent."""
    params = []
    main_intent, detailed_intent = intents["main_intent"],intents["detailed_intent"]
    if main_intent in data:
        for intent in data[main_intent]:
            if intent["name"] == detailed_intent:
                params =  intent.get("params", [])
    cnxt = 'no special context required'
    inst = " no special instructions, "
    if main_intent == 'file_operation':
        # TODO: switch with actual retrieval
        inst = "These are the contents of the current filesystem for your reference, when dealing with paths always consult this, try your best to infer which files the user is thinking about from this, the user most likely doesnt remember the proper filenames or the extensions, extralopolate from the data. if there is not match here preoutput the user to specify the files while giving the ones you think are likely as options to the user\n"
        cnxt = ".\nDocuments \nDocuments/project_notes.txt \nDocuments/budget.xlsx \nDownloads \nDownloads/photo.jpg \nDownloads/video.mp4 \nDownloads/Installers \nDownloads/Installers/app_installer.deb \nMusic \nMusic/song.mp3 \nMusic/podcast.wav \nPictures \nPictures/wallpaper.png \nPictures/profile.jpg \nVideos \nVideos/movie.mkv \nVideos/tutorial.mp4"
    elif main_intent == 'task_management':
        inst = "Given below is the current task list. refer to this and extrapolate the task names to match existing ones. if nothing is even a remote match then use the preoutput to ask the user and give them options if possible. i repeat only move forward with something that is an exact match of the context.\n"
        cnxt = "ID Age   Description Urg\n1 19s   test 1         0\n2 13s   test 2         0\n3  3s   test 3         0"
    elif main_intent == 'notes':
        inst = "Given below is the current notes list. refer to this and extrapolate the note names to match existing ones. if nothing is even a remote match then use the preoutput to ask the user and give them options if possible. i repeat only move forward with something that is an exact match of the context.\n"
        cnxt = "TITLE \t DATE \n shopping list \t 2025-01-25 18:31:41 \n important memos \t 2025-01-25 18:31:57 \n meeting notes 3 \t 2025-01-25 18:32:06"
    context = inst + ' \n ' + cnxt
    output = {"params":params,"context":context}
    # print(output)
    return output

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

