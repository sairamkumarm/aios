import json
import time
from config import configure_model
from prompts import SYSTEMPROMPT, FORMAT_PROMPT
from utils import get_detailed_intents, get_main_intents, get_params_and_context
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Prompt
from rich.theme import Theme
from rich.padding import Padding
from rich.progress import Progress
from utils import get_class_name

custom_theme = Theme({
    "user": "bold cyan",
    "system": "dim cyan",
    "plan": "yellow",
    "action": "blue",
    "observation": "magenta",
    "output": "green",
    "error": "red"
})

console = Console(theme=custom_theme)

def display_json(data: dict, mode: str):
    msg_type = data.get('type', '').lower()
    if mode == "debug":
        title = f"[{msg_type}]{msg_type.upper()}[/{msg_type}]"
        syntax = Syntax(
            json.dumps(data, indent=2),
            "json",
            theme="monokai",
            background_color="default"
        )
        console.print(Panel(
            Padding(syntax, 1),
            title=title,
            border_style=msg_type,
            title_align="left",
            width=100
        ))
    elif mode == "training":
        console.print(json.dumps(data, indent=2))

def main():
    console.clear()
    console.print(Panel.fit("AI Chat Interface", style="bold cyan"))
    
    while True:
        mode = Prompt.ask("Select mode", choices=["chat", "debug", "training", "exit"])
        if mode == 'exit':
            console.print(Panel("\nGoodbye!\n", border_style="yellow"))
            break
            
        console.print(f"Operating in {mode} mode\n")
        
        with Progress() as progress:
            task = progress.add_task("Initializing AI...", total=100)
            model = configure_model(SYSTEMPROMPT)
            progress.update(task, advance=100)
            chat = model.start_chat()

        try:
            while True:
                uinput = Prompt.ask(">> ")
                if uinput.lower() in ['exit', 'quit', 'bye']:
                    raise KeyboardInterrupt
                    
                start_time = time.time()

                payload = {
                    "type": "user",
                    "user": uinput,
                    "intents": get_main_intents()
                }
                
                if mode in ["debug", "training"]:
                    display_json(payload, mode)
                
                response = chat.send_message(json.dumps(payload))

                while True:
                    res = response.text.strip('```json').strip('\n```').strip()
                    try:
                        jres = json.loads(res)
                        if mode in ["debug", "training"]:
                            display_json(jres, mode)
                    except json.JSONDecodeError:
                        console.print(Panel("Error: Invalid JSON response", border_style="red"))
                        payload = {"type": "SYSTEM", "SYSTEM": "Response format incorrect. Please correct."}
                        response = chat.send_message(json.dumps(payload))
                        continue

                    if jres["type"] == 'plan':
                        payload = {"type": "SYSTEM", "SYSTEM": "Proceed as strictly per protocol"}
                        response = chat.send_message(json.dumps(payload))

                    elif jres["type"] == 'action':
                        fcn, ipt = jres["function"], jres["input"]

                        if fcn == 'preoutput':
                            pmessage = Prompt.ask(f'[cyan]{ipt["response"]}[/cyan]')
                            payload = {
                                "type": "preoutput_user_answer",
                                "preoutput_user_answer": pmessage
                            }
                            response = chat.send_message(json.dumps(payload))

                        else:
                            output = None
                            if fcn == 'get_detailed_intents':
                                output = get_detailed_intents(ipt)
                            elif fcn == 'get_params_and_context':
                                output = get_params_and_context({
                                    "main_intent": ipt["main_intent"],
                                    "detailed_intent": ipt["detailed_intent"]
                                })

                            observation_payload = {
                                "type": "observation",
                                "observation": output
                            }
                            response = chat.send_message(json.dumps(observation_payload))

                    elif jres["type"] == 'output':
                        if mode == "chat":
                            response_text = (jres.get("response") or 
                                          jres.get("output", {}).get("response", 
                                          "No response available"))
                            class_name = get_class_name(jres["main_intent"], jres["detailed_intent"])
                            response_text = class_name.run(jres["params"])
                            console.print(Panel(
                                str(response_text),
                                title="Response",
                                border_style="green",
                                padding=(1, 2),
                                width=80
                            ))
                        else:
                            display_json(jres, mode)
                        break

                if mode != "chat":
                    console.print(f"Finished in {(time.time() - start_time):.2f}s\n")

        except KeyboardInterrupt:
            console.print("\n")
            console.print(Panel("\nClosing session. Goodbye!\n", border_style="yellow"))
            break

if __name__ == "__main__":
    main()