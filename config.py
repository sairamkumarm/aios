import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

def configure_model(SYSTEMPROMPT):
    api_key = os.environ.get('API_KEY')
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name='gemini-1.5-flash', system_instruction=SYSTEMPROMPT)
    return model
