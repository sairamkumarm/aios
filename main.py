import json
import time
import traceback
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
import google.api_core.exceptions

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
            background_color="default",
            word_wrap=True  # Enable word wrapping
        )
        # Get terminal width and use it for panel width with some margin
        terminal_width = console.width or 100
        panel_width = max(80, min(terminal_width - 5, 120))  # Between 80 and 120, or terminal width - 5
        
        console.print(Panel(
            Padding(syntax, 1),
            title=title,
            border_style=msg_type,
            title_align="left",
            width=panel_width,  # Dynamic width based on terminal
            expand=False  # Prevent expanding beyond specified width
        ))
    elif mode == "training":
        console.print(json.dumps(data, indent=2))

def get_retry_delay_from_error(error):
    """
    Extract the retry delay from a GoogleAPI ResourceExhausted error.
    """
    error_str = str(error)
    try:
        # Try to extract retry delay from the error message
        if "retry_delay" in error_str and "seconds" in error_str:
            import re
            match = re.search(r'retry_delay \{\s*seconds: (\d+)\s*\}', error_str)
            if match:
                return int(match.group(1))
    except Exception:
        pass
    # Default retry delay if we couldn't extract it
    return 5

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
                
                try:
                    response = chat.send_message(json.dumps(payload))

                    while True:
                        try:
                            res = response.text.strip('```json').strip('\n```').strip()
                            try:
                                jres = json.loads(res)
                                if mode in ["debug", "training"]:
                                    display_json(jres, mode)
                            except json.JSONDecodeError:
                                console.print(Panel("Error: Invalid JSON response", border_style="red"))
                                payload = {"type": "SYSTEM", "SYSTEM": f"Response format incorrect. Please correct. \n\n{FORMAT_PROMPT}"}
                                try:
                                    response = chat.send_message(json.dumps(payload))
                                except google.api_core.exceptions.ResourceExhausted as e:
                                    # Handle rate limit exceeded
                                    retry_delay = get_retry_delay_from_error(e)
                                    console.print(Panel(
                                        f"API rate limit exceeded. Please wait {retry_delay} seconds before trying again.",
                                        border_style="yellow",
                                        title="Rate Limit"
                                    ))
                                    break
                                except Exception as e:
                                    console.print(Panel(f"Error: {str(e)}", border_style="red"))
                                    break
                                continue

                            if jres["type"] == 'plan':
                                payload = {"type": "SYSTEM", "SYSTEM": "Proceed as strictly per protocol"}
                                try:
                                    response = chat.send_message(json.dumps(payload))
                                except google.api_core.exceptions.ResourceExhausted as e:
                                    # Handle rate limit exceeded
                                    retry_delay = get_retry_delay_from_error(e)
                                    console.print(Panel(
                                        f"API rate limit exceeded. Please wait {retry_delay} seconds before trying again.",
                                        border_style="yellow",
                                        title="Rate Limit"
                                    ))
                                    break
                                except Exception as e:
                                    console.print(Panel(f"Error: {str(e)}", border_style="red"))
                                    break

                            elif jres["type"] == 'action':
                                fcn, ipt = jres["function"], jres["input"]

                                if fcn == 'preoutput':
                                    pmessage = Prompt.ask(f'[cyan]{ipt["response"]}[/cyan]')
                                    payload = {
                                        "type": "preoutput_user_answer",
                                        "preoutput_user_answer": pmessage
                                    }
                                    try:
                                        response = chat.send_message(json.dumps(payload))
                                    except google.api_core.exceptions.ResourceExhausted as e:
                                        # Handle rate limit exceeded
                                        retry_delay = get_retry_delay_from_error(e)
                                        console.print(Panel(
                                            f"API rate limit exceeded. Please wait {retry_delay} seconds before trying again.",
                                            border_style="yellow",
                                            title="Rate Limit"
                                        ))
                                        break
                                    except Exception as e:
                                        console.print(Panel(f"Error: {str(e)}", border_style="red"))
                                        break

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
                                    try:
                                        response = chat.send_message(json.dumps(observation_payload))
                                    except google.api_core.exceptions.ResourceExhausted as e:
                                        # Handle rate limit exceeded
                                        retry_delay = get_retry_delay_from_error(e)
                                        console.print(Panel(
                                            f"API rate limit exceeded. Please wait {retry_delay} seconds before trying again.",
                                            border_style="yellow",
                                            title="Rate Limit"
                                        ))
                                        break
                                    except Exception as e:
                                        console.print(Panel(f"Error: {str(e)}", border_style="red"))
                                        break

                            elif jres["type"] == 'output':
                                if mode == "chat":
                                    response_text = (jres.get("response") or 
                                                  jres.get("output", {}).get("response", 
                                                  "No response available"))
                                    try:
                                        class_name = get_class_name(jres["output"]["main_intent"], jres["output"]["detailed_intent"])
                                        if class_name is not None:
                                            response_text = class_name.run(jres["output"]["params"])
                                    except Exception as e:
                                        console.print(Panel(f"Error executing command: {str(e)}", border_style="red"))
                                        # Fall back to the response from the AI
                                    
                                    console.print(Panel(
                                        str(response_text),
                                        title="Response",
                                        border_style="green",
                                        padding=(1, 2),
                                        width=80
                                    ))
                                else:
                                    display_json(jres, mode)
                                    try:
                                        class_name = get_class_name(jres["output"]["main_intent"], jres["output"]["detailed_intent"])
                                        if class_name is not None:
                                            response_text = class_name.run(jres["output"]["params"])
                                    except Exception as e:
                                        console.print(Panel(f"Error executing command: {str(e)}", border_style="red"))
                                        # Fall back to the response from the AI
                                break
                        except Exception as e:
                            console.print(Panel(f"Error processing response: {str(e)}", border_style="red"))
                            break

                    if mode != "chat":
                        console.print(f"Finished in {(time.time() - start_time):.2f}s\n")
                except google.api_core.exceptions.ResourceExhausted as e:
                    # Handle rate limit exceeded
                    retry_delay = get_retry_delay_from_error(e)
                    console.print(Panel(
                        f"API rate limit exceeded. Please wait {retry_delay} seconds before trying again.",
                        border_style="yellow",
                        title="Rate Limit"
                    ))
                except Exception as e:
                    console.print(Panel(f"Error: {str(e)}\n{traceback.format_exc()}", border_style="red"))

        except KeyboardInterrupt:
            console.print("\n")
            console.print(Panel("\nClosing session. Goodbye!\n", border_style="yellow"))
            break

if __name__ == "__main__":
    main()