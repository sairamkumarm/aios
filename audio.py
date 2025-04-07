import sounddevice as sd
import numpy as np
import wave
import requests
import uuid
import threading
import json
import time
import os

WIT_TOKEN = str("Bearer "+os.environ.get('WIT_TOKEN'))

def listen_and_send_to_wit(silence_threshold=250, silence_duration=0.5, max_record_seconds=10):
    sample_rate = 16000
    # Use smaller chunks for more frequent updates
    blocksize = 512  # Smaller block size for more frequent callback calls
    chunk_duration = blocksize / sample_rate
    max_chunks = int(max_record_seconds / chunk_duration)
    silence_limit = int(silence_duration / chunk_duration)
    filename = f"{uuid.uuid4()}.wav"

    print("🎤 Listening... (start speaking or press ENTER to stop manually)")

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
                print("🎙️ Detected speech, recording...")
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
                print(f"⏱️ Stopping in {remaining:.1f}s...")

        # Stop if silence threshold is reached after speech was detected
        if started_talking and silence_chunks >= silence_limit:
            print("🔇 Silence detected, stopping...")
            stop_flag.set()
            raise sd.CallbackStop
            
        # Also stop if we've recorded for too long
        if len(recorded_chunks) >= max_chunks:
            print("⏱️ Maximum duration reached, stopping...")
            stop_flag.set()
            raise sd.CallbackStop

    def wait_for_enter():
        input()
        print("🛑 Manual stop")
        stop_flag.set()

    input_thread = threading.Thread(target=wait_for_enter, daemon=True)
    input_thread.start()

    start_time = time.time()
    try:
        with sd.InputStream(callback=callback, channels=1, samplerate=sample_rate, 
                           dtype='int16', blocksize=blocksize):
            while not stop_flag.is_set():
                # Use shorter sleep intervals for more responsive UI
                sd.sleep(50)
                
                # Add a timeout if speech hasn't started after a while
                if not started_talking and time.time() - start_time > 10:
                    print("⏱️ No speech detected, stopping...")
                    break
    except sd.CallbackStop:
        pass
    except Exception as e:
        print(f"Error in audio stream: {e}")

    if not recorded_chunks:
        print("❌ No speech detected.")
        return None

    duration = len(recorded_chunks) * chunk_duration
    print(f"✅ Recording complete: {duration:.1f} seconds")
    
    audio_data = np.concatenate(recorded_chunks, axis=0)
    print("💾 Saving audio...")

    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())

    print("📤 Sending to Wit.ai...")
    with open(filename, 'rb') as f:
        headers = {
            'Authorization': WIT_TOKEN,
            'Content-Type': 'audio/wav'
        }
        response = requests.post(
            'https://api.wit.ai/speech?v=20230202',
            headers=headers,
            data=f
        )

    print("✅ Wit.ai response:")
    
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
            print(f"Final recognized text: {final_text}")
            return final_text
        else:
            print("No valid JSON objects found")
            return None
            
    except Exception as e:
        print("⚠️ Error processing response:", e)
        return None


if __name__ == "__main__":
    # Use a shorter silence duration (0.5s) and keep threshold at 250
    result = listen_and_send_to_wit(silence_threshold=250, silence_duration=0.5)
    if result:
        print(f"Successfully recognized: '{result}'")