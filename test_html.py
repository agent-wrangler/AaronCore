# -*- coding: utf-8 -*-
import requests
r = requests.get('http://127.0.0.1:8090/')
with open(r'C:\Users\36459\NovaCore\output.html', 'w', encoding='utf-8') as f:
    f.write(r.text[-1500:])
print('OK')
