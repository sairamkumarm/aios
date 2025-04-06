import json
from classes.notes import notes
from classes.alarm import alarms
from datetime import datetime

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
        try:
            # Get actual notes list from the notes script
            notes_instance = notes("list_notes")
            notes_list = notes_instance.run({})
            if notes_list and not notes_list.startswith("Error"):
                cnxt = notes_list
            else:
                # Fallback in case of error
                cnxt = "No notes found or error retrieving notes."
        except Exception as e:
            # Fallback in case of exception
            cnxt = f"Error accessing notes: {str(e)}"
    elif main_intent == 'alarms':
        current_time = datetime.now().astimezone().strftime("%A, %B %d, %Y at %I:%M:%S.%f %p %Z (UTC%z)")
        try :
            alarms_instance = alarms("list_scheduled_alarms")
            alarms_list = alarms_instance.run({})
            if alarms_list and not alarms_list.startswith("Error"):
                cnxt = alarms_list + "\n" + f"Current date time is {current_time}"
            else:
                # Fallback in case of error
                cnxt = "No alarms found or error retrieving notes." + "\n" + f"Current date time is {current_time}"
        except Exception as e:
            # Fallback in case of exception
            cnxt = f"Error accessing alarm: {str(e)}" + "\n" + f"Current date time is {current_time}"

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

def get_class_name(main_intent: str, detailed_intent: str):
    mapper = {
        "notes": notes(detailed_intent),
        "alarms" : alarms(detailed_intent)
    }
    return mapper.get(main_intent)