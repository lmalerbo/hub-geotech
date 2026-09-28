"""Testa o login no Hub com e-mail e senha (a senha é digitada escondida e
não é gravada em lugar nenhum).

Uso:  python ingestao/testar_login.py
"""

import getpass

import requests

from comum import carregar_env

env = carregar_env()
email = input('E-mail: ').strip()
senha = getpass.getpass('Senha (a mesma do GeoMap, não aparece ao digitar): ')
r = requests.post(
    env['SUPABASE_URL'].rstrip('/') + '/auth/v1/token',
    params={'grant_type': 'password'},
    headers={'apikey': env['SUPABASE_ANON_KEY'], 'Content-Type': 'application/json'},
    json={'email': email, 'password': senha},
    timeout=60,
)
if r.ok:
    print('✓ Login OK — a senha do GeoMap funciona no Hub.')
else:
    print(f"✗ Login recusado: {r.json().get('error_description') or r.json().get('msg') or r.text[:200]}")
