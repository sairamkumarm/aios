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
import pvporcupine

WIT_TOKEN = f"Bearer {os.environ.get('WIT_TOKEN')}"
TEMP_AUDIO_FILENAME = "temp_audio.wav"  # Fixed filename for temp audio
VOICE_TRIGGER_PHRASE = "hey assistant"  # Voice trigger phrase

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

def listen_for_trigger_word(max_retries=3, retry_delay=2):
    """
    Continuously listen for the trigger phrase 'hey assistant' using pvporcupine.
    Returns True when the trigger word is detected.
    
    Args:
        max_retries: Maximum number of retries if device error occurs
        retry_delay: Delay in seconds between retries
    """
    # Fallback to simple volume-based detection if we can't use pvporcupine
    use_fallback = False
    retries = 0
    
    while retries <= max_retries:
        if use_fallback:
            return listen_for_sound_activity()
            
        console.print(f"[voice]🎧 Listening for trigger phrase '{VOICE_TRIGGER_PHRASE}'...[/voice]")
        
        # Initialize pvporcupine for hotword detection
        porcupine = None
        audio_stream = None
        
        try:
            # Create a porcupine instance for the 'hey assistant' keyword
            # Using 'jarvis' as a substitute for demo since 'hey assistant' would need a custom model
            porcupine = pvporcupine.create(
                keywords=['jarvis'],
                access_key=os.environ.get('PICO_TOKEN')
            )
            
            # Audio parameters
            sample_rate = porcupine.sample_rate
            frame_length = porcupine.frame_length
            
            # Setup audio stream with explicit device selection
            # Try to use default device (device=None)
            audio_stream = sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype='int16',
                blocksize=frame_length,
                callback=None,
                device=None  # Use default device
            )
            
            audio_stream.start()
            
            console.print(f"[voice]🔊 Say '{VOICE_TRIGGER_PHRASE}' to activate voice mode (Press Ctrl+C to cancel)[/voice]")
            
            # Process audio frames
            while True:
                # Check for user input to exit (non-blocking)
                if check_for_user_input():
                    console.print("[voice]Exiting trigger mode due to user input[/voice]")
                    return False
                    
                # Read audio frame
                audio_frame, overflowed = audio_stream.read(frame_length)
                audio_frame = audio_frame.flatten().astype(np.int16)
                
                # Process with porcupine
                keyword_index = porcupine.process(audio_frame)
                
                # If keyword detected
                if keyword_index >= 0:
                    console.print("[voice]✅ Trigger phrase detected![/voice]")
                    return True
                    
        except KeyboardInterrupt:
            console.print("[voice]🛑 Trigger word detection cancelled[/voice]")
            return False
        except Exception as e:
            console.print(f"[error]Error in trigger word detection: {e}[/error]")
            retries += 1
            
            if retries > max_retries:
                console.print("[warning]Maximum retries exceeded. Switching to fallback detection method.[/warning]")
                use_fallback = True
            else:
                console.print(f"[warning]Retrying in {retry_delay} seconds... (Attempt {retries}/{max_retries})[/warning]")
                time.sleep(retry_delay)
        finally:
            # Clean up resources
            try:
                if audio_stream is not None:
                    audio_stream.stop()
                if porcupine is not None:
                    porcupine.delete()
            except Exception as cleanup_error:
                console.print(f"[error]Error during cleanup: {cleanup_error}[/error]")
    
    return False

def listen_and_send_to_wit(silence_threshold=250, silence_duration=0.5, max_record_seconds=10):
    sample_rate = 16000
    blocksize = 512
    chunk_duration = blocksize / sample_rate
    max_chunks = int(max_record_seconds / chunk_duration)
    silence_limit = int(silence_duration / chunk_duration)
    filename = TEMP_AUDIO_FILENAME  # Use the fixed filename

    # Clean up any existing temp file
    if os.path.exists(filename):
        try:
            os.remove(filename)
        except:
            pass

    console.print("[voice]🎤 Recording... (Press Enter to stop)[/voice]")
    
    recorded_chunks = []
    silence_chunks = 0
    started_talking = False
    stop_flag = threading.Event()
    
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
                console.print("[voice]🎙️ Speech detected[/voice]", end="\r")
                recording_start_time = current_time
                last_ui_update = current_time
            started_talking = True
            silence_chunks = 0
            recorded_chunks.append(indata.copy())
        elif started_talking:
            silence_chunks += 1
            recorded_chunks.append(indata.copy())
            
            # Show auto-stop countdown only when silence is detected
            if current_time - last_ui_update >= 0.25 and silence_chunks < silence_limit:
                last_ui_update = current_time
                remaining = (silence_limit - silence_chunks) * chunk_duration
                console.print(f"[voice]🎤 Recording... Auto-stop in {remaining:.1f}s (Press Enter to stop manually)[/voice]", end="\r")

        # Stop if silence threshold is reached after speech was detected
        if started_talking and silence_chunks >= silence_limit:
            console.print("[voice]🔇 Silence detected, stopping...[/voice]")
            stop_flag.set()
            raise sd.CallbackStop
            
        # Also stop if we've recorded for too long
        if len(recorded_chunks) >= max_chunks:
            console.print("[voice]⏱️ Maximum duration reached[/voice]")
            stop_flag.set()
            raise sd.CallbackStop

    def check_for_enter():
        # Use signal based approach instead of keyboard library
        while not stop_flag.is_set():
            # Check if enter was pressed using a simple input with timeout
            try:
                # We're using a hacky solution with os.read and select for non-blocking input
                import select
                rlist, _, _ = select.select([0], [], [], 0.1)  # 0 is stdin
                if rlist:
                    key = os.read(0, 1024).decode().strip()
                    if key:  # If Enter was pressed
                        console.print("[voice]🛑 Recording stopped by user[/voice]")
                        stop_flag.set()
                        break
            except Exception:
                time.sleep(0.1)  # Fall back to simple sleep if the above fails

    enter_thread = threading.Thread(target=check_for_enter, daemon=True)
    enter_thread.start()

    start_time = time.time()
    try:
        with sd.InputStream(callback=callback, channels=1, samplerate=sample_rate, 
                           dtype='int16', blocksize=blocksize):
            while not stop_flag.is_set():
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
    trigger_mode = False
    
    while True:
        mode = Prompt.ask("Select mode", choices=["chat", "debug", "training", "exit"])
        if mode == 'exit':
            console.print(Panel("\nGoodbye!\n", border_style="yellow"))
            break
        
        input_method = Prompt.ask("Input method", choices=["text", "voice", "trigger"])
        
        # Set voice mode based on input method
        voice_mode = (input_method == "voice" or input_method == "trigger")
        trigger_mode = (input_method == "trigger")
        
        if voice_mode:
            if trigger_mode:
                voice_instructions = f"""
                [info]Trigger mode instructions:[/info]
                [info]- Say '{VOICE_TRIGGER_PHRASE}' to activate voice input[/info]
                [info]- Recording will automatically stop after silence[/info]
                [info]- Type 'exit' to quit at any time[/info]
                """
                console.print(Panel(voice_instructions, border_style="cyan", title="Trigger Mode"))
            else:
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
                    if trigger_mode:
                        # In trigger mode, continuously listen for the trigger phrase
                        console.print("[voice]🎧 Listening for trigger phrase. Say 'exit' to quit.[/voice]")
                        
                        # Allow user to type 'exit' to quit trigger mode
                        console.print("[info](Type something and press Enter to exit trigger mode)[/info]")
                        
                        # Create a thread to check for user input to exit
                        exit_flag = threading.Event()
                        
                        def check_for_exit():
                            nonlocal exit_flag
                            user_input = input()
                            if user_input.lower() in ['exit', 'quit', 'bye']:
                                exit_flag.set()
                                raise KeyboardInterrupt
                            else:
                                exit_flag.set()
                        
                        exit_thread = threading.Thread(target=check_for_exit, daemon=True)
                        exit_thread.start()
                        
                        # Listen for trigger word until exit_flag is set
                        while not exit_flag.is_set():
                            if listen_for_trigger_word():
                                # Trigger word detected, start recording
                                console.print("[voice]🎤 Trigger word detected! Listening for command...[/voice]")
                                uinput = listen_and_send_to_wit(silence_threshold=250, silence_duration=0.5)
                                if uinput:
                                    break
                                else:
                                    console.print("[voice]No voice input detected after trigger. Listening for trigger again...[/voice]")
                        
                        # If we exited the loop without getting input, check if we should continue
                        if not uinput:
                            if exit_flag.is_set():
                                # User typed something to exit trigger mode
                                console.print("[voice]Exited trigger mode.[/voice]")
                                continue
                    else:
                        # Regular voice mode
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