"""Confere a tela da Apresentação semanal em modo demonstração (sem banco). Roda à mão, da raiz do repositório:
    python tests/app/teste_apresentacao_tela.py
Sobe um servidor local para app/, abre apresentacao.html?demo no Edge e salva prints em .prints/."""
import functools
import http.server
import re
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright
from pptx import Presentation

RAIZ = Path(__file__).resolve().parents[2]
PRINTS = RAIZ / '.prints'
falhas = []
erros = []
sys.stdout.reconfigure(encoding='utf-8')  # o console do Windows (cp1252) não imprime "⋯"


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


def abre(nav, query):
    pg = nav.new_page(viewport={'width': 1440, 'height': 900})
    pg.on('pageerror', lambda e: erros.append(str(e)))
    pg.goto(f'http://127.0.0.1:{porta}/apresentacao.html{query}', timeout=30000)
    return pg


try:
    with sync_playwright() as p:
        nav = p.chromium.launch(channel='msedge')

        # ── 1. Demonstração: busca e lista de slides ──
        pg = abre(nav, '?demo')
        confere(pg.locator('#apt-demo').is_visible(), 'faixa de demonstração visível')
        pg.wait_for_selector('#apt-buscar', state='visible', timeout=30000)
        pg.wait_for_function("document.getElementById('apt-semana').value && document.getElementById('apt-corte').value"
                             " && document.getElementById('apt-meta-meta_ervas_ha').value", timeout=30000)
        pg.click('#apt-buscar', timeout=30000)
        pg.wait_for_selector('#apt-fontes [data-fonte=voos][data-status=ok]', timeout=30000)
        confere(pg.locator('#apt-lista [data-slide]').count() == 6, 'seis slides na lista')

        # ── 2. Prévia com destaque em texto (escapado, sem HTML) ──
        pg.click('[data-slide=colheita]', timeout=10000)
        pg.fill('#apt-f-destaque', '<b>chuva</b>', timeout=10000)
        confere(pg.locator('#apt-previa .ap-destaque').inner_text(timeout=10000) == '<b>chuva</b>',
                'destaque aparece como texto na prévia')
        confere(pg.locator('#apt-previa .ap-destaque b').count() == 0, 'destaque não vira HTML')

        # ── 3. Rascunho salvo com atraso ──
        pg.fill('#apt-f-notas', 'Nota & "aspas"', timeout=10000)
        pg.wait_for_timeout(2500)
        confere('Rascunho salvo às' in pg.locator('#apt-salvo').inner_text(), 'rascunho salvo após 2 s')
        pg.screenshot(path=str(PRINTS / 'apresentacao_edicao.png'))

        # ── 4. PPTX: download e conferência do arquivo ──
        pg.wait_for_selector('#apt-baixar:not([disabled])', timeout=60000)
        with pg.expect_download(timeout=120000) as dl:
            pg.click('#apt-baixar', timeout=10000)
        baixado = dl.value
        nome = baixado.suggested_filename
        confere(bool(re.match(r'^s[1-5]m\d{1,2} - Apresentacao Geotecnologia - Indicadores e Entregas\.pptx$', nome)),
                f'nome do PPTX ({nome})')
        destino = PRINTS / nome
        baixado.save_as(str(destino))
        prs = Presentation(str(destino))
        confere(len(prs.slides) == 6, f'PPTX com 6 slides ({len(prs.slides)})')
        notas = prs.slides[1].notes_slide.notes_text_frame.text
        confere(notas == 'Nota & "aspas"', f'notas do slide 2 preservadas ({notas!r})')
        pg.close()

        # ── 5. Falha da API de voos: aviso, botão travado e nova tentativa ──
        pg = abre(nav, '?demo=voos-falha')
        pg.wait_for_selector('#apt-buscar', state='visible', timeout=30000)
        pg.wait_for_function("document.getElementById('apt-semana').value && document.getElementById('apt-corte').value"
                             " && document.getElementById('apt-meta-meta_ervas_ha').value", timeout=30000)
        pg.click('#apt-buscar', timeout=10000)
        pg.wait_for_selector('#apt-fontes [data-fonte=voos][data-status=falhou]', timeout=15000)
        pg.click('[data-slide=voos]', timeout=10000)
        confere('Dados indisponíveis' in pg.locator('#apt-previa').inner_text(timeout=10000),
                'prévia de voos mostra "Dados indisponíveis"')
        confere(pg.locator('#apt-baixar').is_disabled(), 'botão PPTX desabilitado com voos falhos')
        confere(pg.evaluate('AP_ST.tentativasVoos') == 1, 'uma tentativa de voos até aqui')
        pg.click('#apt-tentar', timeout=10000)
        pg.wait_for_selector('#apt-fontes [data-fonte=voos][data-status=carregando]', timeout=5000)
        confere(True, 'nova tentativa põe voos em carregando')
        pg.wait_for_function('AP_ST.tentativasVoos == 2', timeout=5000)
        confere(pg.evaluate('AP_ST.tentativasVoos') == 2, 'segunda tentativa registrada')
        pg.wait_for_selector('#apt-fontes [data-fonte=voos][data-status=falhou]', timeout=15000)
        pg.screenshot(path=str(PRINTS / 'apresentacao_voos_falha.png'))
        pg.close()

        nav.close()

        # ── 6. Sem erros de JavaScript ──
        confere(not erros, f'sem erros de JavaScript ({erros[:2]})')
finally:
    srv.shutdown()
    srv.server_close()

if falhas:
    print(f'\n{len(falhas)} falha(s).')
    sys.exit(1)
print('ok')
