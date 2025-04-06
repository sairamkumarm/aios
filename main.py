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
import keyboard
import os

WIT_TOKEN = "Bearer 5YCZYHOW6DIYF2AQT53XAYVKPT2YIGRZ"
VOICE_TRIGGER_PHRASE = "hey assistant"  # Voice trigger phrase

custom_theme = Theme({
    "user": "bold cyan",
    "system": "dim cyan",
    "plan": "yellow",
    "action": "blue",
    "observation": "magenta",
    "output": "green",
    "error": "red",
    "voice": "purple"
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

def listen_and_send_to_wit(silence_threshold=250, silence_duration=0.5, max_record_seconds=10):
    sample_rate = 16000
    # Use smaller chunks for more frequent updates
    blocksize = 512  # Smaller block size for more frequent callback calls
    chunk_duration = blocksize / sample_rate
    max_chunks = int(max_record_seconds / chunk_duration)
    silence_limit = int(silence_duration / chunk_duration)
    filename = f"{uuid.uuid4()}.wav"

    console.print("[voice]🎤 Listening... (start speaking or press ESC to cancel)[/voice]")

    recorded_chunks = []
    silence_chunks = 0
    started_talking = False
    stop_flag = threading.Event()
    
    # Keep track of how long we've been recording
    recording_start_time = None
    last_ui_update = 0

    def callback(indata, frames, time_info, status):
        nonlocal recorded_chunks, silence_chunks, started_talking, recording_start_time, last_ui_update
        current_time = time.time()

        if stop_flag.is_set():
            raise sd.CallbackStop

        volume = np.abs(indata).mean() * 1000

        if volume > silence_threshold:
            if not started_talking:
                console.print("[voice]🎙️ Detected speech, recording...[/voice]")
                recording_start_time = current_time
                last_ui_update = current_time
            started_talking = True
            silence_chunks = 0
            recorded_chunks.append(indata.copy())
        elif started_talking:
            silence_chunks += 1
            recorded_chunks.append(indata.copy())
            
            # Display remaining time more consistently - update every 0.25 seconds
            if current_time - last_ui_update >= 0.25 and silence_chunks < silence_limit:
                last_ui_update = current_time
                remaining = (silence_limit - silence_chunks) * chunk_duration
                console.print(f"[voice]⏱️ Stopping in {remaining:.1f}s...[/voice]")

        # Stop if silence threshold is reached after speech was detected
        if started_talking and silence_chunks >= silence_limit:
            console.print("[voice]🔇 Silence detected, stopping...[/voice]")
            stop_flag.set()
            raise sd.CallbackStop
            
        # Also stop if we've recorded for too long
        if len(recorded_chunks) >= max_chunks:
            console.print("[voice]⏱️ Maximum duration reached, stopping...[/voice]")
            stop_flag.set()
            raise sd.CallbackStop

    def check_for_escape():
        while not stop_flag.is_set():
            if keyboard.is_pressed('esc'):
                console.print("[voice]🛑 Cancelled by user[/voice]")
                stop_flag.set()
                break
            time.sleep(0.1)

    escape_thread = threading.Thread(target=check_for_escape, daemon=True)
    escape_thread.start()

    start_time = time.time()
    try:
        with sd.InputStream(callback=callback, channels=1, samplerate=sample_rate, 
                           dtype='int16', blocksize=blocksize):
            while not stop_flag.is_set():
                # Use shorter sleep intervals for more responsive UI
                sd.sleep(50)
                
                # Add a timeout if speech hasn't started after a while
                if not started_talking and time.time() - start_time > 6:
                    console.print("[voice]⏱️ No speech detected, stopping...[/voice]")
                    break
    except sd.CallbackStop:
        pass
    except Exception as e:
        console.print(f"[error]Error in audio stream: {e}[/error]")

    if not recorded_chunks or stop_flag.is_set() and not started_talking:
        console.print("[voice]❌ No speech detected or recording cancelled.[/voice]")
        return None

    if stop_flag.is_set() and started_talking:
        duration = len(recorded_chunks) * chunk_duration
        console.print(f"[voice]✅ Recording complete: {duration:.1f} seconds[/voice]")
        
        audio_data = np.concatenate(recorded_chunks, axis=0)
        console.print("[voice]💾 Saving audio...[/voice]")

        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data.tobytes())

        console.print("[voice]📤 Sending to Wit.ai...[/voice]")
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

        console.print("[voice]✅ Wit.ai response received[/voice]")
        
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
                console.print(f"[voice]You said: \"{final_text}\"[/voice]")
                
                # Clean up temp file
                try:
                    os.remove(filename)
                except:
                    pass
                    
                return final_text
            else:
                console.print("[error]No valid JSON objects found in response[/error]")
                return None
                
        except Exception as e:
            console.print(f"[error]Error processing response: {e}[/error]")
            return None
    
    return None

def listen_for_trigger(silence_threshold=250, max_wait_seconds=5):
    """
    Continuously listen for a trigger phrase
    """
    sample_rate = 16000
    blocksize = 1024
    trigger_detected = threading.Event()
    
    console.print("[voice]🎧 Listening for trigger phrase...[/voice]")
    
    def callback(indata, frames, time_info, status):
        volume = np.abs(indata).mean() * 1000
        if volume > silence_threshold:
            # Simply detect sound above threshold
            trigger_detected.set()
            raise sd.CallbackStop
    
    try:
        with sd.InputStream(callback=callback, channels=1, samplerate=sample_rate, 
                           dtype='int16', blocksize=blocksize):
            sd.sleep(int(max_wait_seconds * 1000))  # Convert to milliseconds
    except sd.CallbackStop:
        pass
    except Exception as e:
        console.print(f"[error]Error in trigger detection: {e}[/error]")
    
    return trigger_detected.is_set()

def main():
    console.clear()
    console.print(Panel.fit("Voice-Enabled AI Chat Interface", style="bold cyan"))
    
    use_voice_trigger = False
    voice_mode = False
    
    while True:
        mode = Prompt.ask("Select mode", choices=["chat", "debug", "training", "exit"])
        if mode == 'exit':
            console.print(Panel("\nGoodbye!\n", border_style="yellow"))
            break
        
        input_method = Prompt.ask("Input method", choices=["text", "voice"])
        voice_mode = (input_method == "voice")
        
        if voice_mode:
            use_voice_trigger = Prompt.ask("Use voice trigger?", choices=["yes", "no"]) == "yes"
            if use_voice_trigger:
                console.print(Panel(f"Voice trigger enabled. Say or make a sound to trigger listening.", border_style="green"))
            
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
                    if use_voice_trigger:
                        # Wait for trigger sound
                        if listen_for_trigger():
                            uinput = listen_and_send_to_wit(silence_threshold=250, silence_duration=0.5)
                    else:
                        # Direct voice command without trigger
                        uinput = listen_and_send_to_wit(silence_threshold=250, silence_duration=0.5)
                        
                    if not uinput:
                        console.print("[voice]No voice input detected. Try again or type 'exit'.[/voice]")
                        # Fallback to text input if voice fails
                        uinput = Prompt.ask(">> ")
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
                                    # For voice mode, we'll also support voice response option
                                    if voice_mode:
                                        options = ["voice", "text"]
                                        resp_method = Prompt.ask(
                                            f'[cyan]{ipt["response"]}[/cyan]\nRespond with', 
                                            choices=options, 
                                            default="text"
                                        )
                                        
                                        if resp_method == "voice":
                                            console.print("[voice]Speak your response...[/voice]")
                                            pmessage = listen_and_send_to_wit(silence_threshold=250, silence_duration=0.5)
                                            if not pmessage:
                                                # Fallback to text
                                                pmessage = Prompt.ask(f'[cyan]Voice not detected. Please type response[/cyan]')
                                        else:
                                            pmessage = Prompt.ask(f'[cyan]Type your response[/cyan]')
                                    else:
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
                                    ai_response_text = (jres.get("response") or 
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
                                        str(ai_response_text),
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