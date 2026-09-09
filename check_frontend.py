# -*- coding: utf-8 -*-
import os
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend')

for f in ['index.html', 'dashboard.html', 'herbs.html', 'users.html', 'logs.html']:
    text = open(os.path.join(BASE, f), encoding='utf-8').read()
    ls = re.findall(r'localStorage\.\w+\([^)]*\)', text)
    ss = re.findall(r'sessionStorage\.\w+\([^)]*\)', text)
    api_calls = len(re.findall(r"api\('", text)) + len(re.findall(r"api\(`", text))
    print('--- %s ---' % f)
    print('  localStorage:', ls if ls else '无')
    print('  sessionStorage:', ss)
    print('  api调用数:', api_calls)
