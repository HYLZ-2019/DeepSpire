import os
# Put upper layer directory into sys.path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from API_KEYS import VOICE_API_KEY
import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer
from playsound import playsound
import threading
import time

dashscope.api_key = VOICE_API_KEY
model = "cosyvoice-v2"
#voice = "longxiaoxia_v2"
voice = "longcheng_v2"

def log_error(error):
	with open("D:/DeepSpire/deepspire/voice_error.log", "a", encoding="UTF-8") as f:
		f.write(error + "\n")

output_path = "D:/DeepSpire/deepspire/output.mp3"

status_bar_file = "D:/DeepSpire/deepspire/status_bar.txt"

def speak(text):
	# 在等待的过程中，往status_bar写入“语音合成中....”
	try:
		with open(status_bar_file, "w", encoding="UTF-8") as f:
			f.write("语音合成中")

		synthesizer = SpeechSynthesizer(model=model, voice=voice)

		# Create an event to signal when to stop adding dots
		dots_event = threading.Event()

		def append_dots():
			while not dots_event.is_set():
				with open(status_bar_file, "a", encoding="UTF-8") as f:
					f.write(".")
				time.sleep(1)

		# Start thread to append dots
		dot_thread = threading.Thread(target=append_dots)
		dot_thread.daemon = True
		dot_thread.start()
		
		audio = synthesizer.call(text)
		# print('[Metric] requestId: {}, first package delay ms: {}'.format(
		# 	synthesizer.get_last_request_id(),
		# 	synthesizer.get_first_package_delay()))
		with open(output_path, 'wb') as f:
			f.write(audio)
			# Play the audio file
		# Play the audio file in a non-blocking way
		play_thread = threading.Thread(target=playsound, args=(output_path,))
		play_thread.daemon = True
		play_thread.start()
		
	except Exception as e:
		log_error(str(e))

	# Stop the dot appender thread
	dots_event.set()
	dot_thread.join(timeout=0.1)
