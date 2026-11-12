"""Painel (Resumo e Talhões) do Paralelismo no Edge, em modo demonstração (dados fictícios, sem banco).
O servidor só escuta em 127.0.0.1; da internet vêm só as fontes, o supabase-js, o fflate e o MapLibre.
Roda à mão, da raiz do repositório:
    python tests/app/teste_paralelismo_painel_tela.py"""
import functools
import http.server
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding='utf-8')
falhas = []


def confere(cond, msg):
    print(('✓ ' if cond else '✗ ') + msg, flush=True)
    if not cond:
        falhas.append(msg)


class Quieto(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Quieto, directory=str(RAIZ / 'app')))
threading.Thread(target=srv.serve_forever, daemon=True).start()
DEMO = f'http://127.0.0.1:{srv.server_address[1]}/paralelismo.html?demo'


def abrir(ctx, nivel='leitura', extra=''):
    pg = ctx.new_page()
    pg.erros = []
    pg.on('pageerror', lambda e: pg.erros.append(str(e)))
    pg.add_init_script(f"window.PAR_DEMO_NIVEL = '{nivel}'; {extra}")
    pg.goto(DEMO)
    pg.wait_for_selector('#par-app:visible', timeout=20000)
    return pg


with sync_playwright() as p:
    nav = p.chromium.launch(channel='msedge')
    ctx = nav.new_context(viewport={'width': 1400, 'height': 900})

    print('\n— Resumo (nível leitura abre no Painel)')
    pg = abrir(ctx)
    pg.wait_for_selector('.par-kpis', timeout=5000)
    confere(pg.locator('.par-aba[aria-selected="true"]').get_attribute('data-aba') == 'painel', 'abre no Painel')
    confere(pg.locator('.par-kpi').count() == 4, '4 KPIs')
    confere(pg.locator('.par-kpi .v').first.inner_text().endswith('%'), 'aderência total em %')
    confere(pg.locator('.par-barra-h').count() == 4, 'quatro faixas de declividade')
    confere(pg.locator('.par-col-v').count() == 2, 'duas colunas de mês (set e out)')
    confere(pg.locator('#par-col tbody tr').count() == 4, 'tabela com as 4 fazendas')
    confere('<b>' not in pg.inner_html('#par-col') and '&lt;b&gt;x&lt;/b&gt;' in pg.inner_html('#par-col'), 'nome com HTML escapado')
    confere(pg.locator('#par-col .par-sit.insuf').count() >= 1, 'fazenda só com amostra insuficiente aparece como tal')
    confere(pg.locator('#par-maplibre').is_hidden(), 'mapa do Painel fica escondido no Resumo')
    confere(not pg.erros, f'sem erro de script {pg.erros}')

    print('\n— Talhões')
    pg.click('[data-sub="talhoes"]')
    pg.wait_for_selector('#par-tab-tal tr', timeout=5000)
    total = pg.locator('#par-tab-tal tr').count()
    confere(total == 24, f'24 talhões na tabela ({total})')
    confere(pg.locator('.par-disp circle').count() > 0 and pg.locator('.par-disp circle').count() < 24, 'dispersão sem os de amostra insuficiente')
    confere(pg.locator('#par-tab-tal .par-sit.insuf').count() >= 7, 'insuficientes marcados na tabela')
    pg.fill('#par-busca', '10002')
    confere(pg.locator('#par-tab-tal tr').count() == 6, 'busca por código filtra')
    confere(pg.evaluate("document.activeElement.id") == 'par-busca', 'busca mantém o foco')
    pg.fill('#par-busca', 'sao jose')
    confere(pg.locator('#par-tab-tal tr').count() == 6, 'busca sem acento acha "São José"')
    pg.fill('#par-busca', 'zzz')
    confere('Nenhum talhão' in pg.inner_text('#par-tab-tal'), 'busca sem resultado avisa')
    pg.fill('#par-busca', '')
    pg.click('#par-tab-tal tr[data-chave="cana|10001"]')
    confere(pg.locator('#par-tab-tal tr.sel').first.get_attribute('data-chave') == 'cana|10001', 'clicar na linha escolhe a fazenda')
    confere(pg.locator('#par-maplibre').is_visible() and pg.locator('#par-canvas').is_hidden(), 'mapa MapLibre no palco')
    try:
        pg.wait_for_function('window.PAR_PAINEL_DESENHADO === 6', timeout=15000)
        confere(True, 'MapLibre desenhou os 6 talhões da fazenda')
        cores = pg.evaluate("PAR.painel.ml.m.querySourceFeatures('talhoes').map(f => f.properties.cor)")
        confere(len(set(cores)) >= 2, f'talhões pintados por situação ({sorted(set(cores))})')
    except Exception as e:
        confere(False, f'MapLibre não desenhou (CDN fora do ar?): {str(e)[:80]}')
    confere(not pg.erros, f'sem erro de script {pg.erros}')
    pg.focus('#par-tab-tal tr[data-chave="cana|10002"] button')
    pg.keyboard.press('Enter')
    confere(pg.evaluate("document.activeElement.tagName") == 'BUTTON', 'Enter na linha mantém o foco no botão (teclado)')
    confere(pg.locator('#par-tab-tal button[aria-pressed="true"]').count() >= 1, 'linha escolhida marcada com aria-pressed')
    chamadas = pg.evaluate('window.PAR_DEMO_PAINEL_CHAMADAS')
    pg.click('.par-aba[data-aba="rodadas"]')
    pg.click('.par-aba[data-aba="painel"]')
    pg.wait_for_function(f'window.PAR_DEMO_PAINEL_CHAMADAS > {chamadas}', timeout=5000)
    confere(True, 'voltar ao Painel lê os dados de novo')
    pg.click('.par-aba[data-aba="processar"]')
    confere(pg.locator('#par-maplibre').is_hidden() and pg.locator('#par-canvas').is_visible(), 'em Processar volta o mapa de Processar')
    pg.close()

    print('\n— Sem rodada publicada')
    pg = abrir(ctx, 'editor', 'window.PAR_DEMO_PAINEL_VAZIO = true;')
    pg.wait_for_selector('#par-col .par-aviso', timeout=5000)
    confere('Nenhuma rodada publicada' in pg.inner_text('#par-col'), 'estado vazio')
    confere('NaN' not in pg.inner_text('#par-col'), 'sem NaN')
    pg.click('[data-sub="talhoes"]')
    confere('Nenhuma rodada publicada' in pg.inner_text('#par-col') and pg.locator('#par-maplibre').is_hidden(), 'Talhões vazio, sem mapa')
    pg.close()

    print('\n— 390 px')
    c2 = nav.new_context(viewport={'width': 390, 'height': 800})
    pg = abrir(c2, 'leitura')
    pg.wait_for_selector('.par-kpis')
    confere(pg.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Resumo sem rolagem horizontal da página')
    pg.click('[data-sub="talhoes"]')
    pg.wait_for_selector('#par-tab-tal tr')
    confere(pg.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Talhões sem rolagem horizontal da página')
    nav.close()

print(f'\n{"OK" if not falhas else "FALHOU"}: {len(falhas)} falha(s)')
sys.exit(1 if falhas else 0)
