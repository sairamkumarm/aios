from sysconfig import get_paths
import json, time
from config import configure_model
from prompts import SYSTEMPROMPT
from utils import get_detailed_intents, get_main_intents, get_params_and_context


model = configure_model(SYSTEMPROMPT)
chat = model.start_chat()
try:
    while True:
        uinput = input(">> ")
        start_time = time.time()
        response = chat.send_message(f"{{'type': 'user', 'user': {uinput}, 'intents':{get_main_intents()}}}")
        while True:
            res = response.text.strip('```json').strip('\n```').strip()
            # print(res,end='\n\n')
            jres = json.loads(res)
            if jres["type"] == 'plan':
                response = chat.send_message("Proceed as you see fit.")
                print(f"{jres['plan']}")
            elif jres["type"] == 'action':
                fcn,ipt = jres["function"],jres["input"]
                if fcn == 'preoutput':
                    message = input(f'{ipt["response"]} \n>> ')
                    response = chat.send_message(message)
                else:
                    if fcn == 'get_detailed_intents':
                        output = get_detailed_intents(ipt)
                        # print(output)
                    elif fcn == 'get_params_and_context':
                        output = get_params_and_context({"main_intent": ipt["main_intent"], "detailed_intent": ipt["detailed_intent"]})
                    # print(output)
                    response = chat.send_message(f'{{"type":"observation","observation":{output}}}')
            elif jres["type"] == 'output':
                print(jres["output"])
                break
        end_time=time.time()
        print(f"finished in {(end_time-start_time):.2f} sec\n")
except KeyboardInterrupt:
    print(f"Forcefully closing session, Goodbye.\n")
    
    