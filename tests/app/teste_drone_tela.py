"""Teste da tela do Drone (Playwright + Edge). Roda à mão:
    set HUB_CONTA_TESTE=C:/caminho/conta-teste.json
    python tests/app/teste_drone_tela.py
Dá à conta de teste o papel de editor do Drone só durante o teste e devolve o papel original no fim.
Gera uma prévia da fazenda 10974 e DESCARTA (não publica nada); cancela a solicitação criada."""
import functools
import http.server
import json
import os
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from drone.banco import DroneBanco  # noqa: E402

conta = json.loads(Path(os.environ['HUB_CONTA_TESTE']).read_text(encoding='utf-8'))
b = DroneBanco()
u = b.selecionar('usuarios', 'id,papel', {'nome': 'ilike.*teste*'})[0]
papel_orig = u['papel']
tinha_drone = bool(b.selecionar('usuario_modulos', 'modulo_id', {'usuario_id': f"eq.{u['id']}", 'modulo_id': 'eq.drone'}))
falhas = []


def confere(cond, msg):
    print(('✓ ' if cond else '✗ ') + msg)
    if not cond:
        falhas.append(msg)


H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(RAIZ / 'app'))
srv = socketserver.TCPServer(('127.0.0.1', 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f'http://127.0.0.1:{srv.server_address[1]}/index.html'
sol_criada = None
try:
    b.atualizar('usuarios', {'id': f"eq.{u['id']}"}, {'papel': 'editor'})
    if not tinha_drone:
        b.inserir('usuario_modulos', {'usuario_id': u['id'], 'modulo_id': 'drone'})
    with sync_playwright() as p:
        nav = p.chromium.launch(channel='msedge')
        pg = nav.new_page(viewport={'width': 1400, 'height': 900})
        erros = []
        pg.on('pageerror', lambda e: erros.append(str(e)))
        pg.goto(url)
        pg.fill('#f-email', conta['email']); pg.fill('#f-pass', conta['senha']); pg.click('#btn-entrar')
        pg.wait_for_selector('.ni[onclick*="drone"]', timeout=30000)
        pg.click('.ni[onclick*="drone"]')
        pg.wait_for_selector('#dr-fila .dr-grp', timeout=20000)
        confere(True, 'fila carregou')
        pg.fill('#dr-busca', '10974'); pg.wait_for_selector('#dr-busca-res .dr-it'); pg.click('#dr-busca-res .dr-it')
        pg.wait_for_selector('#dr-map canvas', timeout=20000)
        pg.wait_for_timeout(1500)
        confere(pg.locator('.dr-doc').count() == 2, 'cartões Normal e Catação')
        pg.evaluate("drSelecionarSemProjeto()")
        sem = pg.evaluate("DR.sel.size")
        if sem == 0:
            pg.evaluate("const f=DR.geo.features.find(f=>f.properties.camada==='talhao');drClicarTalhao(f.properties)")
        confere(pg.evaluate("DR.sel.size") > 0, 'seleção de talhões')
        pg.click('text=Gerar prévia')
        pg.wait_for_selector('text=Gerando prévia', timeout=15000)
        confere(True, 'pedido de geração aceito')
        sol_criada = pg.evaluate("drAtual().sol.id")
        os.system(f'"{sys.executable}" -m drone.agente --uma-vez')
        pg.evaluate("drRecarregarFazenda()")
        pg.wait_for_selector('text=Prévia pronta', timeout=60000)
        confere(pg.locator('#dr-pdf iframe').count() == 1, 'PDF da prévia embutido')
        pg.once('dialog', lambda d: d.accept())
        pg.click('button:has-text("Descartar")')
        pg.click('#confirma-sim')
        pg.wait_for_selector('text=Nova revisão', timeout=15000)
        confere(True, 'prévia descartada, seleção liberada')
        confere(not erros, f'sem erro de JavaScript {erros[:2]}')
        nav.close()
finally:
    if sol_criada:
        b.atualizar('drone_solicitacoes', {'id': f'eq.{sol_criada}'}, {'status': 'cancelado'})
    b.atualizar('usuarios', {'id': f"eq.{u['id']}"}, {'papel': papel_orig})
    if not tinha_drone:
        import requests
        requests.delete(f'{b.url}/usuario_modulos', params={'usuario_id': f"eq.{u['id']}", 'modulo_id': 'eq.drone'},
                        headers=b.headers, timeout=60)
    srv.shutdown()
print('FALHAS:', falhas if falhas else 'nenhuma')
sys.exit(1 if falhas else 0)
