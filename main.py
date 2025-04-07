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
import sounddevice as sd
import numpy as np
import wave
import requests
import uuid
import threading
import os
import signal

WIT_TOKEN = "Bearer 5YCZYHOW6DIYF2AQT53XAYVKPT2YIGRZ"
TEMP_AUDIO_FILENAME = "temp_audio.wav"  # Fixed filename for temp audio

custom_theme = Theme({
    "user": "bold cyan",
    "system": "dim cyan",
    "plan": "yellow",
    "action": "blue",
    "observation": "magenta",
    "output": "green",
    "error": "red",
    "voice": "purple",
    "info": "italic dim white"
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
            word_wrap=True
        )
        terminal_width = console.width or 100
        panel_width = max(80, min(terminal_width - 5, 120))
        
        console.print(Panel(
            Padding(syntax, 1),
            title=title,
            border_style=msg_type,
            title_align="left",
            width=panel_width,
            expand=False
        ))
    elif mode == "training":
        console.print(json.dumps(data, indent=2))

def get_retry_delay_from_error(error):
    """
    Extract the retry delay from a GoogleAPI ResourceExhausted error.
    """
    error_str = str(error)
    try:
        if "retry_delay" in error_str and "seconds" in error_str:
            import re
            match = re.search(r'retry_delay \{\s*seconds: (\d+)\s*\}', error_str)
            if match:
                return int(match.group(1))
    except Exception:
        pass
    return 5

def listen_and_send_to_wit(silence_threshold=250, silence_duration=0.5):
    sample_rate = 16000
    blocksize = 512
    chunk_duration = blocksize / sample_rate
    filename = TEMP_AUDIO_FILENAME  # Use the fixed filename

    # Clean up any existing temp file
    if os.path.exists(filename):
        try:
            os.remove(filename)
        except:
            pass

    console.print("[voice]🎤 Recording... (Press Enter to stop)[/voice]")
    
    recorded_chunks = []
    stop_flag = threading.Event()
    
    def callback(indata, frames, time_info, status):
        nonlocal recorded_chunks
        
        if stop_flag.is_set():
            raise sd.CallbackStop

        # Record all audio regardless of volume
        recorded_chunks.append(indata.copy())
        
        # Update recording duration occasionally
        if len(recorded_chunks) % 20 == 0:  # Update roughly every second
            duration = len(recorded_chunks) * chunk_duration
            console.print(f"[voice]🎤 Recording... ({duration:.1f}s) Press Enter to stop[/voice]", end="\r")

    def check_for_enter():
        try:
            print("")  # Add a line for input to appear on
            input()
            console.print("[voice]🛑 Recording stopped by user[/voice]")
            stop_flag.set()
        except Exception as e:
            console.print(f"[error]Error in input thread: {e}[/error]")

    enter_thread = threading.Thread(target=check_for_enter, daemon=True)
    enter_thread.start()

    try:
        with sd.InputStream(callback=callback, channels=1, samplerate=sample_rate, 
                           dtype='int16', blocksize=blocksize):
            while not stop_flag.is_set():
                sd.sleep(100)  # Check more frequently
    except sd.CallbackStop:
        pass
    except Exception as e:
        console.print(f"[error]Error in audio stream: {e}[/error]")

    if not recorded_chunks:
        console.print("[voice]❌ No recording data or recording cancelled.[/voice]")
        return None

    if len(recorded_chunks) > 0:
        duration = len(recorded_chunks) * chunk_duration
        
        console.print(f"[voice]✅ Recording complete ({duration:.1f}s)[/voice]")
        
        audio_data = np.concatenate(recorded_chunks, axis=0)
        
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data.tobytes())

        console.print("[voice]📤 Processing speech...[/voice]")
        with open(filename, 'rb') as f:
            headers = {
                'Authorization': WIT_TOKEN,
                'Content-Type': 'audio/wav'
            }
            try:
                response = requests.post(
                    'https://api.wit.ai/speech?v=20230202',
                    headers=headers,
                    data=f
                )
            except Exception as e:
                console.print(f"[error]Error sending to Wit.ai: {e}[/error]")
                return None

        try:
            # Split the response by newlines and parse each line as JSON
            json_objects = []
            for line in response.text.strip().split('\r'):
                line = line.strip()
                if line:  # Skip empty lines
                    try:
                        json_obj = json.loads(line)
                        json_objects.append(json_obj)
                    except json.JSONDecodeError:
                        # Skip invalid JSON
                        pass
            
            # Get the last valid JSON object
            if json_objects:
                last_response = json_objects[-1]
                final_text = last_response.get("text", "")
                console.print(f"[voice]🗣️ You said: \"{final_text}\"[/voice]")
                return final_text
            else:
                console.print("[error]No valid JSON objects found in response[/error]")
                return None
                
        except Exception as e:
            console.print(f"[error]Error processing response: {e}[/error]")
            return None
    
    return None

def main():
    console.clear()
    console.print(Panel.fit("🎙️ Voice-Enabled AI Chat Interface", style="bold cyan"))
    
    voice_mode = False
    
    while True:
        mode = Prompt.ask("Select mode", choices=["chat", "debug", "training", "exit"])
        if mode == 'exit':
            console.print(Panel("\nGoodbye!\n", border_style="yellow"))
            break
        
        input_method = Prompt.ask("Input method", choices=["text", "voice"])
        voice_mode = (input_method == "voice")
        
        if voice_mode:
            voice_instructions = """
            [info]Voice mode instructions:[/info]
            [info]- Press Enter to start/stop recording[/info]
            [info]- Recording will automatically stop after silence[/info]
            [info]- Type 'exit' to quit at any time[/info]
            """
            console.print(Panel(voice_instructions, border_style="cyan", title="Voice Mode"))
            
        console.print(f"Operating in {mode} mode with {input_method} input\n")
        
        with Progress() as progress:
            task = progress.add_task("Initializing AI...", total=100)
            model = configure_model(SYSTEMPROMPT)
            progress.update(task, advance=100)
            chat = model.start_chat()

        try:
            while True:
                uinput = ""
                if voice_mode:
                    # Simple prompt to indicate readiness
                    console.print("[voice]📝 Ready for input - Press Enter to speak or type your message[/voice]")
                    
                    # Check if user presses Enter (for voice) or types anything else
                    user_action = input()
                    
                    if not user_action.strip():  # Empty input (Enter pressed)
                        uinput = listen_and_send_to_wit(silence_threshold=250, silence_duration=0.5)
                        if not uinput:
                            console.print("[voice]No voice input detected. Please try again.[/voice]")
                            continue
                    else:
                        # User typed something instead of using voice
                        uinput = user_action
                else:
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
                                    # Simplified user response prompt
                                    if voice_mode:
                                        console.print(f'[cyan]{ipt["response"]}[/cyan]')
                                        console.print("[voice]Press Enter to speak your response or type it:[/voice]")
                                        
                                        user_action = input()
                                        
                                        if not user_action.strip():  # Empty input (Enter pressed)
                                            pmessage = listen_and_send_to_wit(silence_threshold=250, silence_duration=0.5)
                                            if not pmessage:
                                                pmessage = Prompt.ask(f'[cyan]Voice not detected. Please type response[/cyan]')
                                        else:
                                            pmessage = user_action
                                    else:
                                        pmessage = Prompt.ask(f'[cyan]{ipt["response"]}[/cyan]')
                                    
                                    payload = {
                                        "type": "preoutput_user_answer",
                                        "preoutput_user_answer": pmessage
                                    }
                                    try:
                                        response = chat.send_message(json.dumps(payload))
                                    except google.api_core.exceptions.ResourceExhausted as e:
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
                                    ai_response_text = (jres.get("response") or 
                                                  jres.get("output", {}).get("response", 
                                                  "No response available"))
                                    try:
                                        class_name = get_class_name(jres["output"]["main_intent"], jres["output"]["detailed_intent"])
                                        if class_name is not None:
                                            response_text = class_name.run(jres["output"]["params"])
                                    except Exception as e:
                                        console.print(Panel(f"Error executing command: {str(e)}", border_style="red"))
                                    
                                    console.print(Panel(
                                        str(ai_response_text),
                                        title="Response",
                                        border_style="green",
                                        padding=(1, 2),
                                        expand=False  # Allow text to wrap naturally
                                    ))
                                else:
                                    display_json(jres, mode)
                                    try:
                                        class_name = get_class_name(jres["output"]["main_intent"], jres["output"]["detailed_intent"])
                                        if class_name is not None:
                                            response_text = class_name.run(jres["output"]["params"])
                                    except Exception as e:
                                        console.print(Panel(f"Error executing command: {str(e)}", border_style="red"))
                                break
                        except Exception as e:
                            console.print(Panel(f"Error processing response: {str(e)}", border_style="red"))
                            break

                    if mode != "chat":
                        console.print(f"Finished in {(time.time() - start_time):.2f}s\n")
                except google.api_core.exceptions.ResourceExhausted as e:
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
        finally:
            # Clean up the temp audio file before exiting
            if os.path.exists(TEMP_AUDIO_FILENAME):
                try:
                    os.remove(TEMP_AUDIO_FILENAME)
                except:
                    pass

if __name__ == "__main__":
    main()