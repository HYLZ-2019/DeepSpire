import os
from bs4 import BeautifulSoup
import glob
import json

# Read from wiki_raw/{id}.html. Get rid of all the HTML tags and save pure text to wiki/{id}.txt

def clean_page(id):
	# Ensure directories exist
	os.makedirs('wiki', exist_ok=True)

	# Construct file paths
	input_path = os.path.join('wiki_raw', f'{id}.html')
	output_path = os.path.join('wiki', f'{id}.txt')

	# Read HTML content
	try:
		with open(input_path, 'r', encoding='utf-8') as f:
			html_content = f.read()

		soup = BeautifulSoup(html_content, 'html.parser')	

		# Delete the <table class="navbox">  items
		for table in soup.find_all('table', class_='navbox'):
			table.decompose()

		extracted_json = extract(soup)

		# Write the remains into the output file
		with open(output_path, 'w', encoding='utf-8') as f:
			f.write(json.dumps(extracted_json, indent=2, ensure_ascii=False))

	except Exception as e:
		print(f"Error processing file {id}: {e}")
		return False

def page_to_text(id):
	# Ensure directories exist
	os.makedirs('wiki', exist_ok=True)

	# Construct file paths
	input_path = os.path.join('wiki_raw', f'{id}.html')
	output_path = os.path.join('wiki_text', f'{id}.txt')

	# Read HTML content
	try:
		with open(input_path, 'r', encoding='utf-8') as f:
			html_content = f.read()

		soup = BeautifulSoup(html_content, 'html.parser')
		# Delete the <table class="navbox">  items
		for table in soup.find_all('table', class_='navbox'):
			table.decompose()
		# Write the remains into the output file
		with open(output_path, 'w', encoding='utf-8') as f:
			f.write(soup.text)

	except Exception as e:
		print(f"Error processing file {id}: {e}")
		return False


def extract(soup):
	# 首先判断这个页面介绍的是卡牌(card)、遗物(relic)、怪物、还是其他

	# 如果是遗物，html里会包含“遗物 id:”这样的文字
	if '遗物 id:' in soup.get_text():
		# 提取名称（“古茶具套装”）、id（“Ancient Tea Set”）、效果中文描述、效果英文描述、中文引言、英文引言、所属、稀有度。生成json
		name = soup.find('span', style=';text-shadow:0 0 3px #FFFFFF;color:#FFFFFF').text
		id = soup.find('td', string=lambda text: text and '遗物 id:' in text).text.split('遗物 id:')[1].strip()
		effect_zh = soup.find('th', string='效果中文描述').find_next('td').text.strip()
		effect_en = soup.find('th', string='效果英文描述').find_next('td').text.strip()
		intro_zh = soup.find('th', string='中文引言').find_next('td').text.strip()
		intro_en = soup.find('th', string='英文引言').find_next('td').text.strip()
		belong = soup.find('th', string='所属').find_next('td').text.strip()
		rarity = soup.find('th', string='稀有度').find_next('td').text.strip()

		json_obj = {
			"type": "relic",
			"name": name,
			"id": id,
			"effect_zh": effect_zh,
			"effect_en": effect_en,
			"intro_zh": intro_zh,
			"intro_en": intro_en,
			"belong": belong,
			"rarity": rarity
		}
		try:
			hints = soup.find('span', id='注意').find_parent('h2').find_next('ul').get_text()
			json_obj['hints'] = hints
		except:
			pass		

		return json_obj
	
	else:
		return {"type": "unknown"}


all_ids = [os.path.basename(f).split('.')[0] for f in glob.glob('wiki_raw/*.html')]
for id in all_ids:
	page_to_text(id)
	clean_page(id)