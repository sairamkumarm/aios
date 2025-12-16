## Prompt Chaining and agentic ai meets OS
1. rich
1. python-dotenv
1. google-generativeai
1. sounddevice
1. keyboard
1. numpy
1. wave
1. pyaudio


###  Notification service start
`sudo apt install at libnotify-bin`

`sudo systemctl start atd`

`sudo systemctl enable atd`

### Audio Service (Note: Install before pyaudio)
`sudo apt install portaudio19-dev`

### Script init
Install and chmod the scripts in the scripts directory, make sure they are available on the path.

### Install dependencies
Install using requirements.txt

### Update ENV
set the paths of the scripts, and the API keys in the ENV file

### Running
`python main.py`
