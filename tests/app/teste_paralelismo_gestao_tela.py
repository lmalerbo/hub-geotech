"""Pendentes, Rodadas e Frotas do Paralelismo no Edge, por nível, em modo demonstração (dados fictícios, sem banco).
O servidor só escuta em 127.0.0.1; da internet vêm só as fontes, o supabase-js e o fflate.
Roda à mão, da raiz do repositório:
    python tests/app/teste_paralelismo_gestao_tela.py
Não cobre o Pyodide nem o banco: o Worker de análise e o envio são os simulados da demonstração."""
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


H = functools.partial(Quieto, directory=str(RAIZ / 'app'))
srv = socketserver.TCPServer(('127.0.0.1', 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
DEMO = f'http://127.0.0.1:{srv.server_address[1]}/paralelismo.html?demo'


def abrir(ctx, nivel, extra=''):
    pg = ctx.new_page()
    pg.erros = []
    pg.on('pageerror', lambda e: pg.erros.append(str(e)))
    pg.add_init_script(f"window.PAR_DEMO_NIVEL = '{nivel}'; window.PAR_DEMO_PASSO = 10; {extra}")
    pg.goto(DEMO)
    pg.wait_for_selector('#par-app:visible', timeout=20000)
    return pg


def aba(pg, nome):
    pg.click(f'.par-aba[data-aba="{nome}"]')
    pg.wait_for_selector('#par-col [data-tela]', timeout=5000)


def n(pg, seletor):
    return pg.locator(seletor).count()


def dialogo(pg, texto):
    pg.click(f'#par-fundo button:has-text("{texto}")')


def log(pg):
    return pg.evaluate('window.PAR_DEMO_LOG || []')


with sync_playwright() as p:
    nav = p.chromium.launch(channel='msedge')
    ctx = nav.new_context(viewport={'width': 1400, 'height': 900})

    # ── Leitura ──
    print('\n— Nível leitura')
    pg = abrir(ctx, 'leitura')
    confere(not pg.locator('.par-aba[data-aba="pendentes"]').is_visible(), 'leitura: aba Pendentes escondida')
    aba(pg, 'rodadas')
    confere(n(pg, '.par-rod') == 2, 'leitura: vê só as 2 rodadas publicadas')
    confere(n(pg, '[data-acao="excluir"], [data-acao="publicar"], [data-acao="recusar"]') == 0, 'leitura: nenhum botão de ação')
    pg.click('[data-acao="sub"][data-sub="frotas"]')
    confere(n(pg, '.par-frota') >= 3, 'leitura: tabela de frotas aparece')
    confere(n(pg, '[data-acao="editar-frota"], [data-acao="nova-frota"]') == 0, 'leitura: frotas só para leitura')
    confere(not pg.erros, f'leitura: sem erro de script {pg.erros}')
    pg.close()

    # ── Solicitante ──
    print('\n— Nível solicitante')
    pg = abrir(ctx, 'solicitante')
    aba(pg, 'pendentes')
    confere(n(pg, '.par-pend') == 1 and pg.locator('.par-pend').first.get_attribute('data-rodada') == '7', 'solicitante: vê só a própria pendente')
    confere(n(pg, '[data-acao="publicar"], [data-acao="recusar"]') == 0, 'solicitante: sem Publicar nem Recusar')
    confere('Aguardando validação' in pg.inner_text('#par-col'), 'solicitante: texto de espera')
    aba(pg, 'rodadas')
    confere(n(pg, '[data-acao="excluir"]') == 0, 'solicitante: sem Excluir')
    pg.click('[data-acao="sub"][data-sub="frotas"]')
    confere(n(pg, '[data-acao="editar-frota"], [data-acao="nova-frota"]') == 0, 'solicitante: frotas só para leitura')
    confere(not pg.erros, f'solicitante: sem erro de script {pg.erros}')
    pg.close()

    # ── Editor: publicar, recusar, links ──
    print('\n— Nível editor')
    pg = abrir(ctx, 'editor')
    aba(pg, 'pendentes')
    confere(n(pg, '.par-pend') == 3, 'editor: vê as 3 pendentes')
    confere(pg.inner_text('#par-cont').strip() == '3', 'editor: contador da aba = 3')
    confere('%' in pg.inner_text('.par-pend[data-rodada="7"]') and 'p.p.' in pg.inner_text('.par-pend[data-rodada="7"]'), 'editor: prévia lida do banco com comparação à vigente')
    confere(n(pg, '[data-acao="excluir"]') == 0, 'editor: sem Excluir')
    hrefs = pg.eval_on_selector_all('#par-col a', 'els => els.map(e => e.getAttribute("href"))')
    confere(len(hrefs) >= 2 and all(h.startswith('https://github.com/') for h in hrefs), f'links: todos https do GitHub ({len(hrefs)})')
    confere(n(pg, 'a[href^="javascript"], a[href^="data"], a[href^="http:"]') == 0, 'links: nenhum esquema perigoso virou href')
    confere('link inválido' in pg.inner_text('.par-pend[data-rodada="9"]'), 'links: o inválido aparece como texto, sem link')
    confere(n(pg, '.par-pend[data-rodada="9"] script, .par-pend[data-rodada="9"] img') == 0, 'links: nada injetado no HTML')
    pg.click('.par-pend[data-rodada="7"] [data-acao="publicar"]')
    pg.wait_for_function("document.querySelectorAll('.par-pend').length === 2", timeout=8000)
    confere(any(x['tipo'] == 'publicar' and x['id'] == 7 and x['rec'] is None for x in log(pg)), 'editor: publicar 7 sem recálculo')
    confere(pg.inner_text('#par-cont').strip() == '2', 'editor: contador cai para 2')
    pg.click('.par-pend[data-rodada="9"] [data-acao="recusar"]')
    pg.click('#par-fundo button:has-text("Recusar rodada")')
    confere(pg.locator('#par-fundo').is_visible() and 'motivo' in pg.inner_text('#par-fundo').lower(), 'recusar: motivo obrigatório (diálogo continua aberto)')
    pg.fill('#par-motivo', 'Linhas fora do talhão')
    dialogo(pg, 'Recusar rodada')
    pg.wait_for_function("document.querySelectorAll('.par-pend').length === 1", timeout=8000)
    confere(any(x['tipo'] == 'recusar' and x['id'] == 9 and x['motivo'] == 'Linhas fora do talhão' for x in log(pg)), 'recusar: motivo enviado')
    aba(pg, 'rodadas')
    confere('Linhas fora do talhão' in pg.inner_text('.par-rod[data-rodada="9"]'), 'rodadas: recusada mostra o motivo')
    confere(not pg.erros, f'editor: sem erro de script {pg.erros}')
    pg.close()

    # ── Editor: recálculo ──
    print('\n— Recálculo na publicação')
    pg = abrir(ctx, 'editor', 'window.PAR_DEMO_RECALC = 1;')
    aba(pg, 'pendentes')
    pg.click('.par-pend[data-rodada="8"] [data-acao="publicar"]')
    pg.wait_for_selector('#par-fundo:visible', timeout=15000)
    confere('10001' in pg.inner_text('#par-fundo') and 'recalcul' in pg.inner_text('#par-fundo').lower(), 'recálculo: mostra o resultado novo da fazenda 10001')
    dialogo(pg, 'Cancelar')
    pg.wait_for_function("!document.querySelector('#par-fundo').innerHTML", timeout=5000)
    confere(n(pg, '.par-pend[data-rodada="8"]') == 1 and not any(x['tipo'] == 'publicar' and x['id'] == 8 and x['rec'] for x in log(pg)), 'recálculo: cancelar não publica')
    pg.click('.par-pend[data-rodada="8"] [data-acao="publicar"]')
    pg.wait_for_selector('#par-fundo:visible', timeout=15000)
    dialogo(pg, 'Publicar com o recálculo')
    pg.wait_for_function("document.querySelectorAll('.par-pend[data-rodada=\"8\"]').length === 0", timeout=8000)
    pub = [x for x in log(pg) if x['tipo'] == 'publicar' and x['id'] == 8 and x['rec']]
    confere(len(pub) == 1 and pub[0]['rec'][0]['cod_faz'] == 10001 and pub[0]['rec'][0]['amostras_url'] is None, 'recálculo: publicou com p_recalculo da fazenda 10001')
    confere(not pg.erros, f'recálculo: sem erro de script {pg.erros}')
    pg.close()

    # ── Editor: frotas ──
    print('\n— Frotas (editor)')
    pg = abrir(ctx, 'editor')
    aba(pg, 'rodadas')
    pg.click('[data-acao="sub"][data-sub="frotas"]')
    antes = n(pg, '.par-frota')
    pg.click('[data-acao="nova-frota"]')
    pg.fill('form[data-form-frota-ed] [name="serie"]', 'BM0000X000077')
    pg.click('form[data-form-frota-ed] button[type="submit"]')
    confere('frota' in pg.inner_text('form[data-form-frota-ed]').lower() and n(pg, 'form[data-form-frota-ed]') == 1, 'frotas: formulário incompleto não salva')
    pg.fill('form[data-form-frota-ed] [name="frota"]', '90077')
    pg.select_option('form[data-form-frota-ed] [name="operacao"]', 'torta')
    pg.select_option('form[data-form-frota-ed] [name="tipo"]', 'prestador')
    pg.click('form[data-form-frota-ed] button[type="submit"]')
    pg.wait_for_function(f"document.querySelectorAll('.par-frota').length === {antes + 1}", timeout=5000)
    confere('90077' in pg.inner_text('.par-frota[data-serie="BM0000X000077"]'), 'frotas: nova frota aparece na tabela')
    pg.click('.par-frota[data-serie="BM0000X000001"] [data-acao="editar-frota"]')
    confere(pg.locator('form[data-form-frota-ed] [name="serie"]').is_disabled(), 'frotas: a série não muda ao editar')
    pg.fill('form[data-form-frota-ed] [name="observacao"]', 'revisada')
    pg.click('form[data-form-frota-ed] button[type="submit"]')
    pg.wait_for_function("document.querySelector('.par-frota[data-serie=\"BM0000X000001\"]').innerText.includes('revisada')", timeout=5000)
    confere(True, 'frotas: edição salva')
    confere(not pg.erros, f'frotas: sem erro de script {pg.erros}')
    pg.close()

    # ── Admin: excluir ──
    print('\n— Nível admin')
    pg = abrir(ctx, 'admin', 'window.PAR_DEMO_EXCLUIR_ERRO = 1;')
    aba(pg, 'rodadas')
    confere(n(pg, '[data-acao="excluir"]') == 2, 'admin: Excluir só nas 2 publicadas')
    pg.click('.par-rod[data-rodada="2"] [data-acao="excluir"]')
    dialogo(pg, 'Excluir rodada')
    pg.wait_for_selector('.par-toast.show.erro, #par-toast.show.erro', timeout=5000)
    confere('Exclua antes' in pg.inner_text('#par-toast'), 'admin: rodada com outra mais nova na fazenda é recusada com o texto certo')
    pg.evaluate('window.PAR_DEMO_EXCLUIR_ERRO = 0')
    pg.click('.par-rod[data-rodada="2"] [data-acao="excluir"]')
    dialogo(pg, 'Cancelar')
    confere(n(pg, '.par-rod[data-rodada="2"]') == 1, 'admin: cancelar não exclui')
    pg.click('.par-rod[data-rodada="2"] [data-acao="excluir"]')
    dialogo(pg, 'Excluir rodada')
    pg.wait_for_function("!document.querySelector('.par-rod[data-rodada=\"2\"]')", timeout=5000)
    ex = [x for x in log(pg) if x['tipo'] == 'excluir']
    mk = [x for x in log(pg) if x['tipo'] == 'marcar_excluida']
    confere(len(ex) == 1 and ex[0]['id'] == 2 and len(mk) == 1 and mk[0]['tag'] == 'paralelismo-r2', 'admin: excluiu e marcou a release como excluída')
    pg.click('[data-acao="sub"][data-sub="frotas"]')
    confere(n(pg, '[data-acao="nova-frota"]') == 1, 'admin: também edita frotas')
    confere(not pg.erros, f'admin: sem erro de script {pg.erros}')
    pg.close()

    # ── 390 px ──
    print('\n— 390 px')
    pg = abrir(ctx, 'admin')
    pg.set_viewport_size({'width': 390, 'height': 800})
    for nome in ('pendentes', 'rodadas'):
        pg.click(f'.par-aba[data-aba="{nome}"]')
        pg.wait_for_selector('#par-col [data-tela]', timeout=5000)
        confere(pg.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth'), f'390 px: {nome} sem rolagem horizontal')
    pg.click('[data-acao="sub"][data-sub="frotas"]')
    confere(pg.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth'), '390 px: frotas sem rolagem horizontal')
    nav.close()

print()
if falhas:
    print(f'FALHARAM {len(falhas)} conferência(s):')
    for f in falhas:
        print(' -', f)
    sys.exit(1)
print('Todas as conferências passaram.')
