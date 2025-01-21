import json
from config import configure_model
from prompts import SYSTEMPROMPT
from utils import get_detailed_intents, get_main_intents, get_params, preoutput


model = configure_model(SYSTEMPROMPT)
chat = model.start_chat()
uinput = input(">> ")
response = chat.send_message(f"{{'type': 'user', 'user': {uinput}, 'intents':{get_main_intents()}}}")
while True:
    res = response.text.strip('```json').strip('\n```').strip()
    print(res)
    jres = json.loads(res)
    if jres["type"] == 'plan':
        response = chat.send_message("Proceed as you see fit.")
    elif jres["type"] == 'action':
        fcn,ipt = jres["function"],jres["input"]
        if fcn == 'preoutput':
            print(ipt["status"],ipt["params"],ipt["main_intent"],ipt["detailed_intent"],ipt["response"],sep="\n")
            message = input(f'{ipt["response"]} \n>> ')
            response = chat.send_message(message)
        else:
            if fcn == 'get_detailed_intents':
                output = get_detailed_intents(ipt)
            elif fcn == 'get_params':
                output = get_params({"main_intent": ipt["main_intent"], "detailed_intent": ipt["detailed_intent"]})
            print(output)
            response = chat.send_message(f'{{"type":"observation","observation":{output}}}')
    elif jres["type"] == 'output':
        print(jres["output"])
        break
