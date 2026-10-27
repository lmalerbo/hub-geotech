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

        # ── Tarefa 3: coluna da direita e barra de seleção ──
        confere(pg.locator('.cr-nova').count() == 0, 'sem talhão marcado, a Nova aplicação fica fechada')
        confere('Clique nos talhões' in pg.locator('#cr-selbar').inner_text(), 'barra diz como marcar')
        ts = pg.evaluate("() => { const ts = CR_ST.geo.features.map(f => f.properties.talhao).sort((a, b) => a - b).slice(0, 2);"
                         " ts.forEach(t => crToggleSel(t)); return ts; }")
        confere(pg.locator('.cr-nova h2').inner_text() == 'Nova aplicação nos 2 talhões', 'título da Nova aplicação')
        confere('2 talhões marcados' in pg.locator('#cr-selbar').inner_text(), 'barra conta os marcados')
        if pg.evaluate("CR_ST.trab.operacao === 'aerea'"):
            pg.select_option('#cr-f-insumo', index=1)
        pg.fill('#cr-f-dose', '2')
        if pg.locator('#cr-f-gesso').count():
            pg.fill('#cr-f-gesso', '1')
        rot = pg.locator('[data-aplicar]').inner_text()
        confere(bool(re.match(r'^Aplicar nos 2 talhões \([\d.,]+\s\S+\)$', rot)), f'botão com total previsto ({rot})')
        pg.fill('#cr-f-dose', '')
        confere('NaN' not in pg.locator('[data-aplicar]').inner_text(), 'dose vazia não mostra NaN')
        confere(pg.locator('[data-area]').count() == 0, 'áreas por talhão começam recolhidas')
        pg.click('[data-areas]')
        confere(pg.locator('[data-area]').count() == 2, 'Ajustar a área abre um campo por talhão')
        confere(pg.locator('.cr-painel-tot').is_visible(), 'total do mapa no pé da coluna')
        n_apl = pg.locator('[data-menu-apl]').count()
        confere(n_apl > 0, 'demonstração tem aplicações para conferir o menu')
        if n_apl:
            pg.locator('[data-menu-apl]').first.click()
            confere(pg.locator('.cr-menu button:has-text("Editar")').is_visible(), 'menu de ações com Editar')
            pg.keyboard.press('Escape')
            confere(pg.locator('.cr-menu').count() == 0, 'Esc fecha o menu')
            pg.locator('[data-menu-apl]').first.click()
            pg.click('#cr-trab-tit')
            confere(pg.locator('.cr-menu').count() == 0, 'clicar fora fecha o menu')
        pg.screenshot(path=str(PRINTS / 'aplicacao_selecao.png'))
        pg.evaluate('crSelecionarTodos()')
        largura = pg.locator('#cr-selbar').bounding_box()['width']
        confere(largura < pg.locator('#cr-mapa').bounding_box()['width'], 'barra com todos marcados não estoura o mapa')
        pg.click('#cr-selbar [data-limpar]')
        confere(pg.locator('.cr-nova').count() == 0, 'Limpar fecha a Nova aplicação')

        # ── Tarefa 4: dica ao passar o mouse ──
        ponto = pg.evaluate("""() => {
            const f = CR_ST.geo.features[0];
            const anel = (f.geometry.type === 'Polygon' ? f.geometry.coordinates : f.geometry.coordinates[0])[0];
            const lng = anel.reduce((s, c) => s + c[0], 0) / anel.length, lat = anel.reduce((s, c) => s + c[1], 0) / anel.length;
            const p = CR_ST.map.project([lng, lat]);
            return { x: p.x, y: p.y, t: f.properties.talhao };
        }""")
        caixa = pg.locator('#cr-mapa').bounding_box()
        pg.mouse.move(caixa['x'] + ponto['x'], caixa['y'] + ponto['y'])
        pg.wait_for_selector('#cr-dica:not(.off)', timeout=5000)
        confere(f"Talhão {ponto['t']}," in pg.locator('#cr-dica').inner_text(), 'dica mostra o talhão sob o mouse')
        pg.screenshot(path=str(PRINTS / 'aplicacao_dica.png'))
        pg.mouse.move(caixa['x'] + 5, caixa['y'] + caixa['height'] - 5)
        pg.mouse.move(0, 0)
        confere(pg.locator('#cr-dica.off').count() == 1, 'dica some ao sair do mapa')

        # ── Tarefa 5: lista em linhas e abertos por último ──
        pg.click('#cr-voltar')
        pg.wait_for_selector('button.cr-lin-abrir', timeout=10000)
        n_mapas = pg.evaluate('CR_ST.mapas.length')
        confere(pg.locator('button.cr-lin-abrir').count() == n_mapas and n_mapas > 0, 'uma linha por mapa')
        confere(pg.locator('.cr-mapa').count() == 0, 'sem os cartões antigos')
        confere(pg.locator('#cr-recentes [data-recente]').count() >= 1, 'mapa aberto aparece em Abertos por último')
        pg.locator('[data-menu-mapa]').first.click()
        confere(pg.locator('.cr-menu button:has-text("Excluir mapa")').is_visible(), 'menu ⋯ da linha com Excluir mapa')
        pg.keyboard.press('Escape')
        pg.screenshot(path=str(PRINTS / 'aplicacao_lista.png'))
        pg.evaluate("localStorage.setItem('cr-recentes-demo', JSON.stringify([{ id: 999999, cod_faz: CR_ST.faz.cod_faz,"
                    " operacao: 'arado', data: '2026-01-01' }])); crRenderRecentes();")
        pg.click('[data-recente="999999"]')
        pg.wait_for_selector('#cr-toast.show', timeout=5000)
        confere('não existe mais' in pg.locator('#cr-toast').inner_text(), 'recente de mapa excluído avisa')
        confere(pg.locator('#cr-recentes.off').count() == 1, 'recente de mapa excluído sai da lista')
        pg.locator('button.cr-lin-abrir').first.click()
        pg.wait_for_function('CR_ST.geo && CR_ST.det', timeout=30000)
        confere(pg.locator('#cr-trabalho').is_visible(), 'clicar na linha abre o mapa')
        pg.click('#cr-voltar')

        # ── Tarefa 6: novo mapa em dois passos ──
        pg.click('#cr-novo')
        confere(pg.locator('.cr-nm-g').count() == 2, 'novo mapa: Corretivo e Aplicação aérea')
        confere(pg.locator('[data-criar]').inner_text() == 'Criar mapa de SubSolagem', 'começa em Corretivo, SubSolagem')
        pg.click('.cr-seg-o:has([data-op="arado"])')
        confere(pg.locator('[data-criar]').inner_text() == 'Criar mapa de Arado', 'botão acompanha a operação')
        pg.click('[data-grupo="aerea"]')
        confere(pg.locator('[data-op]').count() == 0, 'aérea não pede operação')
        confere(pg.locator('[data-criar]').inner_text() == 'Criar mapa de aplicação aérea', 'botão da aérea')
        pg.screenshot(path=str(PRINTS / 'aplicacao_novo.png'))
        pg.click('[data-cancel]')
        confere(pg.locator('#cr-modal-fundo.off').count() == 1, 'Cancelar fecha a janela')
        pg.click('#cr-novo')
        pg.click('[data-criar]')
        pg.wait_for_function("CR_ST.trab && CR_ST.trab.operacao === 'subsolagem' && CR_ST.det", timeout=30000)
        confere(pg.locator('#cr-trabalho').is_visible(), 'Criar abre o mapa novo')

        # fim das conferências
        confere(not erros, f'sem erros de JavaScript ({erros[:2]})')
        nav.close()
finally:
    srv.shutdown()

print(f'\n{len(falhas)} falha(s)')
sys.exit(1 if falhas else 0)