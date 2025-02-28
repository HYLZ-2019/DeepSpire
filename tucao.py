import os
from openai import OpenAI
from API_KEYS import DEEPSEEK_API_KEY, VOICE_API_KEY
from utilities.voice import speak_sync
import time
import traceback

cur_dir = os.path.dirname(os.path.abspath(__file__))
mp3_file = os.path.join(cur_dir, "tucao.mp3")
comment_file = os.path.join(cur_dir, "log_comment.txt")
tucao_file = os.path.join(cur_dir, "log_tucao.txt")
with open(tucao_file, "w", encoding="UTF-8") as f:
	pass

sys_prompt = "你的搭档DeepSpire是一个由AI驱动的杀戮尖塔主播，虽然打得速度还行，但水平实在是非常烂。请你根据他的口播台词进行吐槽。你目前在B站上进直播，请你用有网感的方式用抽象怪话向观众索要赞美点赞和礼物。下面我会发给你DeepSpire的最近二十条口播。（短一点，不要输出括号、语气等非语言内容，因为你的所有文本都会直接被转语音。）"

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

def guaihua():

	with open(comment_file, "r", encoding="UTF-8") as f:
		# Read final 20 lines
		lines = f.readlines()[-20:]
		koubo = "".join(lines)

	response = client.chat.completions.create(
		model="deepseek-reasoner",
		messages=[
			{"role": "system", "content": sys_prompt},
			{"role": "user", "content": koubo},
		],
		stream=False
	)
	tucao = response.choices[0].message.content
	with open(tucao_file, "a", encoding="UTF-8") as f:
		f.write(tucao + "\n")

	speak_sync(tucao, mp3_file, voice="longxiaoxia", speech_rate=1.2)


while True:
	print("开始怪话")
	try:
		guaihua()
	except Exception as e:
		print("怪话出错")
		print(e)
		traceback.print_exc()
	print("怪话结束")
	# 休息一下
	time.sleep(60)