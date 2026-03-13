import requests
import sys
sys.stdout.reconfigure(encoding='utf-8')

# 使用 Bing RSS 接口
url = 'https://www.bing.com/search?format=rss&q=今天新闻'
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
r = requests.get(url, headers=headers, timeout=15)
print('Status:', r.status_code)
print('Content:', r.text[:1500])
