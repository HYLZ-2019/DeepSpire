from openai import OpenAI
from API_KEYS import DEEPSEEK_API_KEY, VOICE_API_KEY
import threading
import time
import os

# 重载一下json dumps时list的表示方法。
# 一般来说是这样的：
# [a, b, c] -> "[a, b, c]"
# 为了方便大模型计数，改成这样：
# [a, b, c] -> "[(0)a, (1)b, (2)c]"
def list_encoder(obj):
	if isinstance(obj, list):
		return "[" + ", ".join(f"({i}){list_encoder(item)}" for i, item in enumerate(obj)) + "]"
	if isinstance(obj, dict):
		return "{" + ", ".join(f"{k}: {list_encoder(v)}" for k, v in obj.items()) + "}"
	return str(obj)



def get_prompt(silu, game_json, emph=None):
	p = f'''
	【摘要】
	现在，你需要扮演一个游玩杀戮尖塔的AI主播，你的名字叫DeepSpire。由于你只能和游戏通过文字交互，每次需要操作时，我会向你描述游戏状态，请你给出操作指令。我会告诉你如下信息：
	（1）游戏交互规则说明。
	（2）你在本局中的游玩思路。你可以通过在输出中包含<silu>[思路内容]</silu>来记录你的本局思路，在下一次交互中，这一部分内容会作为提示展示给你。如果你有其他希望下一回合用到的信息，也可以记录在这里。每次新生成的思路会覆盖上一次的思路，所以请保留你认为重要的内容。【如果本回合完成了商店购物，请标记下回合要proceed，否则会在商店里无限循环。】【在战斗过程中，请在这里记录你本回合的出牌记录和后面计划出的牌。】
	（3）目前局面的json格式描述。你需要根据这个局面来决定下一步的操作。

	你应当在输出中包含<command>[你下一步的操作对应的指令]</command>，我会解析这一格式并传输给游戏执行。如果你输出的指令格式不正确，游戏会崩溃。
	由于你正在B站上直播，你需要边打边解说，请把你的解说内容包含在<comment>[解说内容]</comment>中，我会让TTS软件把它读出来。每次解说要短一点，你可以抒发自己的情感，也可以简单介绍你的操作思路，或者打牌的时候说一个词也行，例如打出一张攻击牌时说一个字“杀”。注意：游戏操作界面和指令都是英文的，因为软件不支持中文，但你的观众都是中国人，所以你要用中文卡牌名称和术语，多用塔圈黑话（如牌和怪物的昵称）。攻击性和娱乐性都强一点，针对观众抱怨你太慢，以一定概率喷他们。用抽象怪话向观众索要赞美点赞和礼物。

	【游戏交互规则说明】
	你应该已经知道《杀戮尖塔》中的游戏规则，以及所有卡牌、遗物、事件、怪物的中英文名称与描述。以下是关于文字交互的额外说明。
	杀戮尖塔局面json描述中的screen_type分为：
	（1）EVENT：事件界面，有多个选项供你选择。你需要在options里选择一个disabled==False的选项。假如你要选第一个选项（choice_list[0]），指令应为`<command>choose 0</command>`。
	（2）MAP：你面前是地图，你需要从next_nodes里选择下一个房间。symbol表示房间类型：'M'-怪物，'?'-未知，'$'-商店，'R'-火堆，'E'-精英怪，'T'-宝箱。你需要从可选列表里选一个房间，假如你要选第一个房间（next_nodes[0]），指令应为`<command>choose 0</command>`。
	（3）SHOP_ROOM：商店界面。根据choice_list，可以用<command>choose 0</command>来和商人交互（choice_list=['shop']时），或者购买第0个物品（对应的商品信息和价格在screen_state中，你的金币数是gold的数值）。使用<command>proceed</command>离开商店。
	（4）CHEST：宝箱界面。根据choice_list交互。
	（5）COMBAT_REWARD：奖励界面。通过proceed离开。
	（6）REST：火堆。根据choice_list交互。
	（7）GRID：卡牌选择界面。根据choice_list交互。（注意：如果你选择在火堆smith升级卡牌，或者在商店purge移除卡牌，请在<silu>中记一下，否则下回合你不知道这是在干什么。）
	（8）NONE：说明你正在战斗中。你可以选择通过<command>play x y</command>打出hand列表里的第x张卡牌到monsters列表里的第y个怪物（手牌x从1开始计数，怪物y从0开始计数，has_target=False的卡牌不需要y），或者<command>end</command>结束回合。你可以通过<command>potion x</command>使用第x个药水。
	
	以上规则只是近似，最重要的是要让输出符合“目前可用的指令有：……”中的一个，例如在一些场景中你需要灵活使用<command>confirm</command>。随便选一个优于用一个不可用的。

	【你上次交互留下的思路和笔记】
	{silu}

	【目前局面的信息】
	{game_json["json_state"]}

	提醒：目前可用的指令有：{game_json["available_commands"]}。
	'''

	if emph is not None:
		p += f'''【重点信息】
	{emph}
	'''

	return p

client = None

# client = OpenAI(api_key=VOICE_API_KEY, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")

repo_root = os.path.dirname(os.path.abspath(__file__))
status_bar_file = os.path.join(repo_root, "status_bar.txt")

models = {
	"deepseek-chat": (DEEPSEEK_API_KEY, "https://api.deepseek.com", "deepseek-chat"),
	"deepseek-reasoner": (DEEPSEEK_API_KEY, "https://api.deepseek.com", "deepseek-reasoner"),
	"deepseek-v3": (VOICE_API_KEY, "https://dashscope.aliyuncs.com/compatible-mode/v1", "deepseek-v3"),
	"qwen-max": (VOICE_API_KEY, "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-max"),
	"qwen-plus": (VOICE_API_KEY, "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
	"qwen-turbo": (VOICE_API_KEY, "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-turbo"),
}

def ask_deepseek(prompt, model_name="deepseek-chat"):

	api_key, base_url, model_name = models[model_name]

	global client
	if client is None:
		client = OpenAI(api_key=api_key, base_url=base_url)
		
	# 在等待response的过程中，往status_bar写入“Deepseek正在回答中....”
	with open(status_bar_file, "w", encoding="UTF-8") as f:
		f.write(f"{model_name}正在思考中")

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

	response = client.chat.completions.create(
		model=model_name,
		messages=[
			{"role": "system", "content": prompt},
			{"role": "user", "content": "请你生成下一步的指令<command>[你的指令]</command>、解说<comment>[你的解说]</comment>，并为下一次操作留下思路<silu>[思路内容]</silu>。指代卡牌的时候要用对应的中文术语。"},
		],
		stream=False
	)

	# response = client.chat.completions.create(
	# 	model="deepseek-v3",  # 此处以 deepseek-r1 为例，可按需更换模型名称。
	# 	messages=[
	# 		{"role": "system", "content": prompt},
	# 		{"role": "user", "content": "请你生成下一步的指令<command>[你的指令]</command>、解说<comment>[你的解说]</comment>，并为下一次操作留下思路<silu>[思路内容]</silu>。指代卡牌的时候要用对应的中文术语。"},
	# 	],
	# 	stream=False
	# )

	# Stop the dot appender thread
	dots_event.set()
	dot_thread.join(timeout=0.1)

	return response.choices[0].message.content