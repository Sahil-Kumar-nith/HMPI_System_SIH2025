import speech_recognition as sr
from gtts import gTTS
import os

def speech_to_text(audio_file_path):
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_file_path) as source:
        audio = recognizer.record(source)
    text = recognizer.recognize_google(audio)
    return text

def text_to_speech(text, output_file_path):
    tts = gTTS(text=text, lang='en')
    tts.save(output_file_path)
