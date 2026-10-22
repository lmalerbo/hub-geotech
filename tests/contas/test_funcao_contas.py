"""Função "contas" publicada, com a conta de teste promovida a admin só durante
o teste. Cria um acesso @hub.local SEM GeoMap (não toca no GeoMap de produção),
redefine a senha, remove — e apaga a conta de teste criada no fim."""
import json
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'ingestao'))
from comum import Hub, carregar_env  # noqa: E402

# Sem HUB_CONTA_TESTE o módulo ainda é coletado (e pulado): ler a variável no import quebrava a suíte toda.
pytestmark = [pytest.mark.banco,
              pytest.mark.skipif(not os.environ.get('HUB_CONTA_TESTE'), reason='HUB_CONTA_TESTE não definida')]
CONTA = json.load(open(os.environ['HUB_CONTA_TESTE'], encoding='utf-8')) if os.environ.get('HUB_CONTA_TESTE') else {}
EMAIL = 'funcao-contas@hub.local'
URL = 'https://dpvsivypabmvmrrpgmhc.supabase.co'
CHAVE = 'sb_publishable_3xv0R1kmhSXkoUh3i4vN0A_Q5oLBbVL'


def entrar(email, senha):
    r = requests.post(f'{URL}/auth/v1/token?grant_type=password', headers={'apikey': CHAVE},
                      json={'email': email, 'password': senha}, timeout=30)
    return r.json().get('access_token') if r.ok else None


def contas(token, **corpo):
    r = requests.post(f'{URL}/functions/v1/contas', headers={'apikey': CHAVE, 'Authorization': f'Bearer {token}'},
                      json=corpo, timeout=60)
    return r.status_code, r.json()


@pytest.fixture
def admin_token():
    hub = Hub()
    hub.atualizar('usuarios', {'id': f"eq.{CONTA['id']}"}, {'admin': True})
    hub.upsert('acessos', [{'email': CONTA['email'], 'nome': 'Teste Automatizado', 'admin': True}], 'email')
    try:
        yield entrar(CONTA['email'], CONTA['senha'])
    finally:
        hub.atualizar('usuarios', {'id': f"eq.{CONTA['id']}"}, {'admin': False})
        requests.delete(f'{hub.url}/acessos', params={'email': f"eq.{CONTA['email']}"}, headers=hub.headers, timeout=30)
        requests.delete(f'{hub.url}/acessos', params={'email': f'eq.{EMAIL}'}, headers=hub.headers, timeout=30)
        env = carregar_env()
        adm = {'apikey': env['SUPABASE_SERVICE_ROLE_KEY'], 'Authorization': f"Bearer {env['SUPABASE_SERVICE_ROLE_KEY']}"}
        lista = requests.get(f'{URL}/auth/v1/admin/users', headers=adm, params={'per_page': 200}, timeout=30).json()['users']
        for u in lista:
            if u['email'] == EMAIL:
                requests.delete(f"{URL}/auth/v1/admin/users/{u['id']}", headers=adm, timeout=30)


def test_nao_admin_recebe_403():
    token = entrar(CONTA['email'], CONTA['senha'])
    status, corpo = contas(token, acao='grupos_geomap')
    assert status == 403


def test_fluxo_completo(admin_token):
    status, grupos = contas(admin_token, acao='grupos_geomap')
    assert status == 200 and isinstance(grupos, list) and grupos

    status, mapas = contas(admin_token, acao='mapas_geomap')
    assert status == 200 and isinstance(mapas, list)

    status, r = contas(admin_token, acao='salvar', email=EMAIL, nome='Funcao Contas', niveis={'plantio': 'leitura'},
                       admin=False, geomap_ativo=False, geomap_admin=False, geomap_grupos=[], geomap_mapas=[])
    assert status == 200 and r['senhaProvisoria'] and len(r['senhaProvisoria']) == 10 and r['avisoGeomap'] is None
    token_novo = entrar(EMAIL, r['senhaProvisoria'])
    assert token_novo, 'a senha provisória entra'
    hub = Hub()
    linha = hub.selecionar('usuarios', 'precisa_trocar_senha', {'nome': 'eq.Funcao Contas'})
    assert linha == [{'precisa_trocar_senha': True}]

    status, r2 = contas(admin_token, acao='redefinir_senha', email=EMAIL)
    assert status == 200 and r2['senhaProvisoria'] != r['senhaProvisoria']
    assert entrar(EMAIL, r['senhaProvisoria']) is None and entrar(EMAIL, r2['senhaProvisoria'])

    status, r3 = contas(admin_token, acao='remover', email=EMAIL)
    assert status == 200
    assert entrar(EMAIL, r2['senhaProvisoria']) is None, 'conta removida fica bloqueada'
