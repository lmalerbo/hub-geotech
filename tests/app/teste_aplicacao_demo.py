"""Confere as telas dos Mapas de aplicação em modo demonstração (sem banco). Roda à mão, da raiz do repositório:
    python tests/app/teste_aplicacao_demo.py
Sobe um servidor local para app/, abre aplicacao.html?demo no Edge e salva prints em .prints/."""
import functools
import http.server
import re
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
PRINTS = RAIZ / '.prints'
falhas = []


def confere(cond, msg):
    print(('ok    ' if cond else 'FALHA ') + msg)
    if not cond:
        falhas.append(msg)


class Quieto(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


srv = socketserver.TCPServer(('127.0.0.1', 0), functools.partial(Quieto, directory=str(RAIZ / 'app')))
porta = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
PRINTS.mkdir(exist_ok=True)

try:
    with sync_playwright() as p:
        nav = p.chromium.launch(channel='msedge')
        pg = nav.new_page(viewport={'width': 1440, 'height': 900})
        erros = []
        pg.on('pageerror', lambda e: erros.append(str(e)))
        pg.goto(f'http://127.0.0.1:{porta}/aplicacao.html?demo')
        # a demonstração abre sozinha o primeiro mapa da primeira fazenda
        pg.wait_for_function("typeof CR_ST !== 'undefined' && CR_ST.geo && CR_ST.det", timeout=30000)
        pg.wait_for_selector('#cr-mapa canvas', timeout=30000)

        # ── Tarefa 2: tela cheia e cabeçalho do mapa ──
        caixa = pg.locator('#cr-mapa').bounding_box()
        confere(caixa and caixa['width'] > 900, f"mapa ocupa a largura ({caixa and round(caixa['width'])} px)")
        confere(not pg.locator('.cr-top').is_visible(), 'cabeçalho do app some na tela do mapa')
        confere(pg.locator('.cr-trab-top #cr-pdf button').first.is_visible(), 'Baixar PDF no cabeçalho do mapa')
        tit = pg.locator('#cr-trab-tit').inner_text()
        confere(bool(re.match(r'^\S.*, \d\d/\d\d/\d{4}$', tit)), f'título "Operação, data" ({tit})')
        pg.screenshot(path=str(PRINTS / 'aplicacao_mapa.png'))
        pg.click('#cr-voltar')
        confere(pg.locator('.cr-top').is_visible(), 'cabeçalho do app volta na lista')
        pg.click('[data-abrir]')
        pg.wait_for_function('CR_ST.geo && CR_ST.det', timeout=30000)
        pg.wait_for_selector('#cr-mapa canvas', timeout=30000)

        # fim das conferências
        confere(not erros, f'sem erros de JavaScript ({erros[:2]})')
        nav.close()
finally:
    srv.shutdown()

print(f'\n{len(falhas)} falha(s)')
sys.exit(1 if falhas else 0)