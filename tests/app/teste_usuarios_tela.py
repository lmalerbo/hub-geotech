"""Teste da tela Usuarios (Playwright + Edge), com o Supabase SIMULADO por page.route.
Nao conecta no banco: nenhuma credencial e necessaria. Roda com:
    python -m pytest tests/app/teste_usuarios_tela.py -q
ou, direto:  python tests/app/teste_usuarios_tela.py
Confere: filtros e busca; niveis por modulo; mapas do GeoMap (grupo, individual, resultado);
o que vai na chamada "contas" ao salvar; e a largura de 390 px sem rolagem horizontal."""
import functools
import http.server
import json
import socketserver
import threading
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
SB = 'https://dpvsivypabmvmrrpgmhc.supabase.co'
ADMIN_ID = '00000000-0000-4000-8000-00000000a001'
CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*',
        'Access-Control-Allow-Methods': '*'}

USUARIO = {'id': ADMIN_ID, 'email': 'leo@teste.local', 'aud': 'authenticated', 'role': 'authenticated'}
SESSAO = {'access_token': 'token-falso', 'token_type': 'bearer', 'expires_in': 3600,
          'expires_at': 4102444800, 'refresh_token': 'refresh-falso', 'user': USUARIO}
# Pessoas ficticias (acessos_situacao)
ACESSOS = [
    {'email': 'ana@teste.local', 'nome': 'Ana Teste', 'admin': False, 'niveis': {'plantio': 'editor'},
     'geomap_ativo': True, 'geomap_admin': False, 'geomap_grupos': [], 'geomap_mapas': [],
     'atualizado_em': None, 'usuario_id': None, 'conta_criada': True, 'bloqueado': False,
     'ultimo_login': '2026-10-21T12:00:00+00:00', 'precisa_trocar_senha': False},
    {'email': 'bruno@teste.local', 'nome': 'Bruno Teste', 'admin': False, 'niveis': {'drone': 'solicitante'},
     'geomap_ativo': False, 'geomap_admin': False, 'geomap_grupos': [], 'geomap_mapas': [],
     'atualizado_em': None, 'usuario_id': None, 'conta_criada': True, 'bloqueado': False,
     'ultimo_login': None, 'precisa_trocar_senha': False},
    {'email': 'carla@teste.local', 'nome': 'Carla Teste', 'admin': True,
     'niveis': {'colheita': 'leitura', 'corretivos': 'editor'}, 'geomap_ativo': False, 'geomap_admin': False,
     'geomap_grupos': [], 'geomap_mapas': [], 'atualizado_em': None, 'usuario_id': None, 'conta_criada': True,
     'bloqueado': False, 'ultimo_login': None, 'precisa_trocar_senha': True},
]
GRUPOS_GM = [{'id': 1, 'nome': 'Voos'}, {'id': 2, 'nome': 'Operação'}]
MAPAS_GM = [
    {'id': 7, 'nome': 'Fazenda Norte', 'grupos': [{'grupoId': 1, 'podeEditar': True}]},
    {'id': 8, 'nome': 'Fazenda Sul', 'grupos': [{'grupoId': 2, 'podeEditar': False}]},
    {'id': 9, 'nome': 'Pista de voo', 'grupos': []},
]
SALVOS = []  # corpos enviados a "contas" com acao=salvar


def responde(route, corpo=None, status=200):
    route.fulfill(status=status, headers=CORS, content_type='application/json', body=json.dumps(corpo))


def atende(route):
    req = route.request
    if req.method == 'OPTIONS':
        return route.fulfill(status=204, headers=CORS)
    path = urlparse(req.url).path
    if path == '/auth/v1/token':
        return responde(route, SESSAO)
    if path == '/auth/v1/user':
        return responde(route, USUARIO)
    if path == '/functions/v1/contas':
        corpo = req.post_data_json
        if corpo.get('acao') == 'salvar':
            SALVOS.append(corpo)
            return responde(route, {})
        if corpo.get('acao') == 'grupos_geomap':
            return responde(route, GRUPOS_GM)
        if corpo.get('acao') == 'mapas_geomap':
            return responde(route, MAPAS_GM)
        return responde(route, {})
    if path.startswith('/rest/v1/rpc/'):
        nome = path.rsplit('/', 1)[-1]
        return responde(route, {'acessos_situacao': ACESSOS, 'meu_acesso_geomap': True,
                                'drone_resumo': [], 'senha_definida': True}.get(nome))
    if path == '/rest/v1/usuarios':
        return responde(route, [{'id': ADMIN_ID, 'nome': 'Leo Teste', 'admin': True,
                                 'precisa_trocar_senha': False,
                                 'usuario_modulos': [{'modulo_id': 'plantio', 'nivel': 'editor'}]}])
    return responde(route, [])


def test_tela_usuarios():
    SALVOS.clear()
    falhas = []

    def confere(cond, msg):
        print(('ok    ' if cond else 'FALHOU ') + msg)
        if not cond:
            falhas.append(msg)

    H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(RAIZ / 'app'))
    H.log_message = lambda *a: None
    srv = socketserver.TCPServer(('127.0.0.1', 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{srv.server_address[1]}/index.html'
    try:
        with sync_playwright() as p:
            nav = p.chromium.launch(channel='msedge')
            pg = nav.new_page(viewport={'width': 1400, 'height': 900})
            erros = []
            pg.on('pageerror', lambda e: erros.append(str(e)))
            pg.route(f'{SB}/**', atende)
            pg.goto(url)
            pg.fill('#f-email', 'leo@teste.local')
            pg.fill('#f-pass', 'senha-falsa')
            pg.click('#btn-entrar')
            pg.wait_for_function('typeof EU!=="undefined" && EU && EU.niveis', timeout=60000)
            pg.evaluate("trocar('usuarios',document.querySelector('.ni[onclick*=\"usuarios\"]'))")
            pg.wait_for_selector('.usr-card', timeout=20000)
            confere(pg.locator('.usr-card').count() == 3, 'lista com as tres pessoas')

            # 1. Filtros e busca
            pg.click('.usr-chip[data-f="drone"]')
            emails = pg.eval_on_selector_all('.usr-card', 'els => els.map(e => e.dataset.email)')
            confere(emails == ['bruno@teste.local'], f'filtro Drone deixa so quem tem Drone {emails}')
            pg.click('.usr-chip[data-f="todos"]')
            pg.fill('input.usr-busca', 'carla')
            emails = pg.eval_on_selector_all('.usr-card', 'els => els.map(e => e.dataset.email)')
            confere(emails == ['carla@teste.local'], f'busca por nome/e-mail acha a pessoa {emails}')
            pg.fill('input.usr-busca', '')

            # 2. Niveis por modulo
            pg.click('.usr-card[data-email="ana@teste.local"]')
            pg.wait_for_selector('#dpanel-u .usr-panel')
            pg.click('[role="tab"][data-aba="modulos"]')
            pg.click('[data-mod="plantio"][data-n="editor"]')
            confere(pg.evaluate('document.querySelector(\'[data-mod="plantio"][data-n="editor"]\').classList.contains("on")'),
                    'Editor marcado no Plantio')
            confere(pg.locator('[data-mod="plantio"][data-n="solicitante"]').count() == 0,
                    'Plantio nao oferece Solicitante')
            pg.click('[data-mod="drone"][data-n="solicitante"]')
            confere(pg.evaluate('document.querySelector(\'[data-mod="drone"][data-n="solicitante"]\').classList.contains("on")'),
                    'Solicitante marcado no Drone')

            # 3. Mapas do GeoMap
            pg.click('[role="tab"][data-aba="ferramentas"]')
            pg.wait_for_selector('#u-gm-grupos input[value="1"]')
            pg.wait_for_selector('#u-mapas tr:has-text("Pista de voo")')

            def celula(mapa, col):
                return pg.inner_text(f'#u-mapas tr:has-text("{mapa}") td:nth-child({col})').strip()

            confere(celula('Pista de voo', 4) == 'Sem acesso', 'mapa sem grupo começa Sem acesso')
            pg.click('#u-gm-grupos input[value="1"]')
            confere(celula('Fazenda Norte', 2) == 'Ver e editar', 'marcar o grupo Voos muda Pelos grupos')
            pg.click('button[data-mapa="9"]')
            confere(celula('Pista de voo', 4) == 'Ver', 'Individual num mapa sem grupo leva o Resultado a Ver')
            pg.click('button[data-mapa="7"]')
            confere(celula('Fazenda Norte', 4) == 'Ver e editar',
                    'Ver individual num mapa com grupo Ver e editar mantem Ver e editar')

            # 4. Salvar: o que vai para a funcao contas
            pg.click('.usr-salvar')
            pg.wait_for_timeout(1200)
            confere(len(SALVOS) == 1, 'salvar chama contas uma vez')
            if SALVOS:
                c = SALVOS[0]
                confere(c.get('email') == 'ana@teste.local' and c.get('niveis') == {'plantio': 'editor', 'drone': 'solicitante'},
                        f"niveis enviados {c.get('niveis')}")
                confere(c.get('geomap_grupos') == [1], f"grupos enviados {c.get('geomap_grupos')}")
                confere(c.get('geomap_mapas') == [{'mapa_id': 7, 'pode_editar': False}, {'mapa_id': 9, 'pode_editar': False}],
                        f"mapas individuais enviados {c.get('geomap_mapas')}")
                confere(c.get('admin') is False, 'admin enviado como false')
                confere('papel' not in c and 'modulos' not in c, 'corpo sem papel nem modulos')

            # 5. Celular de 390 px: sem rolagem horizontal da pagina
            pg.set_viewport_size({'width': 390, 'height': 844})
            pg.wait_for_timeout(400)
            pg.click('[role="tab"][data-aba="ferramentas"]')
            pg.wait_for_selector('#u-mapas table')
            larg = pg.evaluate('[document.documentElement.scrollWidth, document.documentElement.clientWidth]')
            confere(larg[0] <= larg[1], f'390 px sem rolagem horizontal {larg}')
            confere(not erros, f'sem erro de JavaScript {erros[:2]}')
            nav.close()
    finally:
        srv.shutdown()
    print('FALHAS:', falhas if falhas else 'nenhuma')
    assert not falhas, falhas


if __name__ == '__main__':
    test_tela_usuarios()
