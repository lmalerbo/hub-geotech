"""Tela do Paralelismo (aba Processar) no Edge, em modo demonstração, só com dados sintéticos e sem tocar no banco
(Playwright). O servidor só escuta em 127.0.0.1; da internet vêm só as fontes, o supabase-js e o fflate.
Roda à mão, da raiz do repositório:
    python tests/app/teste_paralelismo_tela.py
Não cobre o Pyodide nem o envio real (Worker do Cloudflare e GitHub): o Worker de análise é o de demonstração.
O Pyodide de verdade está em tests/app/teste_paralelismo_worker.py."""
import functools
import http.server
import socketserver
import sys
import tempfile
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
BASE = f'http://127.0.0.1:{srv.server_address[1]}/paralelismo.html'
DEMO = BASE + '?demo'


def pen_sintetico(raiz: Path):
    """Pen-drive de mentira: dois .jdl de uma série cadastrada, um de série desconhecida e um mapa GS3 sem documentação.
    O Worker de demonstração não lê o conteúdo; a identificação só procura a série nos bytes."""
    log = raiz / 'pen' / 'JD-Data' / 'log' / '2026_U_10001Rev0'
    log.mkdir(parents=True)
    for i, serie in enumerate(['BM0000X000001', 'BM0000X000001', 'BM0000Y000009']):
        (log / f'2026_10_26_0{i}_00_00.jdl').write_bytes(b'\x00' + serie.encode() + b'\x00' + bytes([i]) * 64)
    gs3 = raiz / 'pen' / '90003' / 'GS3_2630' / '90003' / 'RCD' / 'EIC'
    gs3.mkdir(parents=True)
    (gs3 / 'mapa.pth').write_bytes(b'x')
    return raiz / 'pen'


def abrir(ctx, url, init=''):
    pg = ctx.new_page()
    erros = []
    pg.on('pageerror', lambda e: erros.append(str(e)))
    pg.on('dialog', lambda d: d.accept())
    if init:
        pg.add_init_script(init)
    pg.goto(url)
    pg.erros = erros
    return pg


def esperar_pronto(pg, timeout=15000):
    pg.wait_for_function("PAR.itens.length && PAR.itens.every(i => i.estado === 'pronto' || i.estado === 'erro')", timeout=timeout)


with sync_playwright() as p:
    nav = p.chromium.launch(channel='msedge')
    ctx = nav.new_context(viewport={'width': 1400, 'height': 900})

    # ── Login (fora da demonstração): sem sessão, mostra o formulário e valida o vazio ──
    print('\n— Login')
    pg = abrir(ctx, BASE)
    pg.wait_for_selector('#par-email:visible', timeout=20000)
    pg.click('#par-entrar')
    confere('Informe e-mail e senha' in pg.inner_text('#par-login-erro'), 'login: pede e-mail e senha')
    confere(not pg.locator('#par-app').is_visible(), 'login: o app não aparece sem sessão')
    pg.close()

    # ── Demonstração: exemplo pronto, abas, prévia, comparação com a vigente ──
    print('\n— Demonstração: prévia')
    pg = abrir(ctx, DEMO, 'window.PAR_DEMO_PASSO = 20')
    pg.wait_for_selector('#par-app:visible', timeout=20000)
    pg.click('.par-aba[data-aba=\"processar\"]')   # a abertura agora é o Painel
    confere(pg.locator('#par-demo').is_visible(), 'demo: selo "dados fictícios" visível')
    confere(pg.locator('.par-aba').count() == 4, 'demo: quatro abas')
    esperar_pronto(pg)
    col = pg.inner_text('#par-col')
    confere('Enviar para validação' in col, 'prévia: botão de enviar')
    confere('vigente 65,00%' in col, 'prévia: compara com a análise vigente da fazenda')
    confere('fazenda nova' in col or 'vigente' in col, 'prévia: mostra a situação da fazenda')
    confere(pg.locator('#par-col .par-grande .v').inner_text().endswith('%'), 'prévia: aderência total em %')
    confere(pg.locator('#par-canvas').is_visible() and not pg.locator('#par-mapa-vazio').is_visible(), 'mapa: talhões desenhados no palco')
    pintado = pg.evaluate("""() => { const c = document.getElementById('par-canvas'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
        let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i]) n++; return n; }""")
    confere(pintado > 1000, f'mapa: canvas tem pixels pintados ({pintado})')
    pg.click('[data-acao="faz"]')
    confere('Talhões da 10001' in pg.inner_text('#par-col'), 'prévia: toque na fazenda lista os talhões')
    confere('insuficiente' in pg.inner_text('#par-col'), 'prévia: talhão com menos de 25 amostras marcado como insuficiente')
    pg.click('.par-aba[data-aba="pendentes"]')
    pg.wait_for_selector('#par-col [data-tela="pendentes"]', timeout=5000)
    confere('Rodadas esperando validação' in pg.inner_text('#par-col'), 'abas: Pendentes abre a lista de rodadas (P4)')
    pg.click('.par-aba[data-aba="processar"]')

    # ── Envio com falha no meio: nada gravado, tenta de novo com o mesmo id ──
    print('\n— Envio')
    pg.evaluate('window.PAR_DEMO_FALHA_ENVIO = 1')
    pg.click('[data-acao="enviar"]')
    pg.wait_for_selector('#par-col .par-aviso.erro', timeout=10000)
    confere('Nada foi gravado' in pg.inner_text('#par-col .par-aviso.erro'), 'envio: falha mostra "Nada foi gravado"')
    confere('Sem conexão' in pg.inner_text('#par-col .par-aviso.erro'), 'envio: falha de rede tem texto claro')
    confere(pg.evaluate('(window.PAR_DEMO_ENVIADOS || []).length') == 0, 'envio: nada foi enviado ao banco')
    confere('Tentar de novo' in pg.inner_text('[data-acao="enviar"]'), 'envio: botão vira "Tentar de novo"')
    pg.click('[data-acao="enviar"]')
    pg.wait_for_function('(window.PAR_DEMO_ENVIADOS || []).length === 1', timeout=10000)
    carga = pg.evaluate('window.PAR_DEMO_ENVIADOS[0]')
    confere(carga['rodada_id'] == 9001, 'envio: o mesmo id da rodada foi reaproveitado')
    confere(len(carga['arquivos']) == 2 and len(carga['analises']) == 1 and carga['linhas'], 'envio: arquivos, análise e linhas na carga')
    confere(all('pontos' not in a and 'shapefile' not in a for a in carga['analises']), 'envio: sem pontos nem shapefile no banco')
    confere(carga['partes'][0]['nome'] == 'p9001-01.zip', 'envio: parte zipada com o nome da rodada')
    confere('Rodada 9001' in pg.inner_text('#par-fila'), 'envio: item enviado fica na fila como "aguardando validação"')
    confere(pg.evaluate('PAR.itens.length') == 0, 'envio: a cópia saiu da fila')
    pg.close()

    # ── Pen-drive de mentira: cópia no OPFS, conferência, cadastro de frota, fila ──
    print('\n— Conferência e cadastro de frota')
    with tempfile.TemporaryDirectory() as tmp:
        pen = pen_sintetico(Path(tmp))
        pg = abrir(ctx, DEMO, 'window.PAR_DEMO_PASSO = 20')
        pg.wait_for_selector('#par-app:visible', timeout=20000)
        pg.click('.par-aba[data-aba=\"processar\"]')   # a abertura agora é o Painel
        esperar_pronto(pg)
        pg.click('[data-acao="remover"]')
        pg.click('.par-modal .par-btn')
        pg.wait_for_function('PAR.itens.length === 0')
        pg.set_input_files('#par-pasta', str(pen)) if pg.locator('#par-pasta').count() else None
        if not pg.locator('#par-pasta').count():
            pg.evaluate('parPasta()')
            pg.set_input_files('#par-pasta', str(pen))
        pg.wait_for_selector('.par-trator', timeout=15000)
        col = pg.inner_text('#par-col')
        confere('pode retirar o pen-drive' in col, 'cópia: avisa que pode retirar o pen-drive')
        confere('BM0000X000001' in col and 'Frota 90001' in col and '2 arquivos novos' in col, 'conferência: série cadastrada resolve frota e conta arquivos')
        confere('10001' in col, 'conferência: fazenda vem do nome gravado no monitor')
        confere('BM0000Y000009' in col and 'sem frota cadastrada' in col, 'conferência: série desconhecida avisa')
        confere('Sem executado' in col and 'Documentation' in col, 'conferência: pasta GS3 sem documentação avisa')
        pg.click('[data-acao="cadastrar"]')
        pg.fill('[name="frota"]', '90009')
        pg.select_option('[name="operacao"]', 'torta')
        pg.click('[data-form-frota] button[type="submit"]')
        pg.wait_for_function("document.querySelectorAll('.par-pil.torta').length === 1")
        confere('Frota 90009' in pg.inner_text('#par-col'), 'cadastro: o editor cadastra a frota ali mesmo e a conferência atualiza')
        pg.click('[data-acao="adicionar"]')
        esperar_pronto(pg)
        confere(pg.evaluate("PAR.itens[0].estado") == 'pronto', 'fila: o pen-drive processou e ficou pronto')
        confere(pg.evaluate("PAR.itens[0].resultado.fazendas.map(f => f.operacao + f.cod_faz).sort().join()") == 'cana10001,torta10001',
                'fila: a mesma fazenda em duas operações sai em duas análises')
        pg.close()

        # ── Solicitante não cadastra frota ──
        pg = abrir(ctx, DEMO, "window.PAR_DEMO_NIVEL = 'solicitante'; window.PAR_DEMO_PASSO = 20")
        pg.wait_for_selector('#par-app:visible', timeout=20000)
        pg.click('.par-aba[data-aba=\"processar\"]')   # a abertura agora é o Painel
        pg.evaluate('parPasta()')
        pg.set_input_files('#par-pasta', str(pen))
        pg.wait_for_selector('.par-trator', timeout=15000)
        confere(pg.locator('[data-acao="cadastrar"]').count() == 0 and 'Peça a um editor' in pg.inner_text('#par-col'),
                'solicitante: não vê o cadastro de frota')
        pg.close()

    # ── Erros da spec §10 e avisos ──
    print('\n— Erros e avisos')
    pg = abrir(ctx, DEMO, 'window.PAR_DEMO_FALHA_PREPARO = true; window.PAR_DEMO_PASSO = 5')
    pg.wait_for_selector('#par-app:visible', timeout=20000)
    pg.click('.par-aba[data-aba=\"processar\"]')   # a abertura agora é o Painel
    pg.wait_for_selector('#par-col .par-aviso.erro', timeout=10000)
    confere('Não foi possível preparar a análise; recarregue a página' in pg.inner_text('#par-col'), 'erro: Pyodide não carrega, com o texto da spec')
    confere('Nada foi gravado' in pg.inner_text('#par-col'), 'erro: diz que nada foi gravado')
    confere(pg.locator('[data-acao="recarregar"]').count() == 1, 'erro: oferece recarregar a página')
    pg.close()

    pg = abrir(ctx, DEMO, 'window.PAR_DEMO_SEM_TRABALHO = true; window.PAR_DEMO_PASSO = 5')
    pg.wait_for_selector('#par-app:visible', timeout=20000)
    pg.click('.par-aba[data-aba=\"processar\"]')   # a abertura agora é o Painel
    esperar_pronto(pg)
    confere('implemento quase sempre desligado' in pg.inner_text('#par-col'), 'aviso: frota sem trabalho registrado')
    pg.close()

    pg = abrir(ctx, DEMO, "window.PAR_DEMO_NIVEL = 'leitura'")
    pg.wait_for_selector('#par-app:visible', timeout=20000)
    pg.click('.par-aba[data-aba=\"processar\"]')   # a abertura agora é o Painel
    confere('nível é de leitura' in pg.inner_text('#par-col') and pg.locator('[data-acao="escolher"]').count() == 0,
            'leitura: não processa pen-drive')
    pg.close()

    # ── Sobras no OPFS ──
    print('\n— Sobras')
    pg = abrir(ctx, DEMO, 'window.PAR_DEMO_PASSO = 5')
    pg.wait_for_selector('#par-app:visible', timeout=20000)
    pg.click('.par-aba[data-aba=\"processar\"]')   # a abertura agora é o Painel
    pg.evaluate("async () => { const r = await (await navigator.storage.getDirectory()).getDirectoryHandle(PAR_OPFS_PASTA, { create: true }); const d = await r.getDirectoryHandle('csobra', { create: true });"
                " const f = await d.getFileHandle('f000001.jdl', { create: true }); const w = await f.createWritable(); await w.write(new Uint8Array(10)); await w.close(); }")
    pg.reload()
    pg.wait_for_selector('#par-app:visible', timeout=20000)
    pg.click('.par-aba[data-aba=\"processar\"]')   # a abertura agora é o Painel
    pg.wait_for_function("PAR.sobras.some(s => s.id === 'csobra')", timeout=10000)
    pg.wait_for_selector('[data-acao="descartar-sobras"]', timeout=10000)
    confere('sessão anterior' in pg.inner_text('#par-col'), 'sobras: avisa da cópia da sessão anterior')
    pg.click('[data-acao="descartar-sobras"]')
    pg.click('.par-modal .par-btn')
    pg.wait_for_function("document.querySelectorAll('[data-acao=\"descartar-sobras\"]').length === 0", timeout=10000)
    confere(pg.evaluate("async () => { const r = await (await navigator.storage.getDirectory()).getDirectoryHandle(PAR_OPFS_PASTA, { create: true }); const n = []; for await (const [k] of r.entries()) n.push(k); return n.includes('csobra'); }") is False,
            'sobras: descartar apaga a cópia do OPFS')
    pg.close()

    # ── Achados da revisão: formulário em edição, conferência que falha, resposta perdida, mesmo pen-drive duas vezes ──
    print('\n— Robustez')
    with tempfile.TemporaryDirectory() as tmp:
        pen = pen_sintetico(Path(tmp))
        pg = abrir(ctx, DEMO, 'window.PAR_DEMO_PASSO = 300; window.PAR_DEMO_FALHA_JA = 1')
        pg.wait_for_selector('#par-app:visible', timeout=20000)
        pg.click('.par-aba[data-aba=\"processar\"]')   # a abertura agora é o Painel
        pg.evaluate('parPasta()')
        pg.set_input_files('#par-pasta', str(pen))
        pg.wait_for_selector('[data-acao="reconferir"]', timeout=15000)
        confere(pg.evaluate("PAR.rascunho.arquivos.length") == 3 and pg.locator('[data-acao="adicionar"]').is_disabled(),
                'conferência que falha: a cópia fica guardada e o botão de adicionar espera')
        pg.click('[data-acao="reconferir"]')
        pg.wait_for_selector('.par-trator', timeout=10000)
        pg.wait_for_function("PAR.rascunho.ja !== null")
        # o item de demonstração ainda processa (passos de 300 ms): o texto digitado não pode sumir
        pg.click('[data-acao="cadastrar"]')
        pg.fill('[name="frota"]', 'digitando')
        pg.wait_for_timeout(1500)
        confere(pg.input_value('[name="frota"]') == 'digitando', 'formulário: o texto digitado sobrevive ao progresso da fila')
        pg.click('[data-acao="cancelar-cadastro"]')
        pg.click('[data-acao="adicionar"]')
        esperar_pronto(pg, 20000)
        # a mesma pasta de novo: o que já está na fila conta como repetido
        pg.evaluate('parPasta()')
        pg.set_input_files('#par-pasta', str(pen))
        pg.wait_for_selector('.par-trator', timeout=15000)
        pg.wait_for_function("PAR.rascunho && PAR.rascunho.ja !== null")
        confere('já foram analisados' in pg.inner_text('#par-col') or 'já foi analisado' in pg.inner_text('#par-col'),
                'mesmo pen-drive de novo: arquivos da fila aparecem como já analisados')
        pg.close()

    pg = abrir(ctx, DEMO, 'window.PAR_DEMO_PASSO = 5; window.PAR_DEMO_JA_ENVIADO = true')
    pg.wait_for_selector('#par-app:visible', timeout=20000)
    pg.click('.par-aba[data-aba=\"processar\"]')   # a abertura agora é o Painel
    esperar_pronto(pg)
    pg.click('[data-acao="enviar"]')
    pg.wait_for_function('PAR.itens.length === 0 && PAR.enviados.length === 1', timeout=10000)
    confere('já tinha sido gravada' in pg.inner_text('#par-toast') or 'aguardando validação' in pg.inner_text('#par-fila'),
            'resposta perdida: rodada já gravada vira "enviado", sem prender o item')
    pg.close()

    # ── 390 px: sem rolagem horizontal ──
    print('\n— Celular')
    mov = nav.new_context(viewport={'width': 390, 'height': 800})
    pg = abrir(mov, DEMO, 'window.PAR_DEMO_PASSO = 5')
    pg.wait_for_selector('#par-app:visible', timeout=20000)
    pg.click('.par-aba[data-aba=\"processar\"]')   # a abertura agora é o Painel
    esperar_pronto(pg)
    larg = pg.evaluate('document.documentElement.scrollWidth')
    confere(larg <= 390, f'celular: sem rolagem horizontal ({larg}px)')
    confere(pg.locator('[data-acao="enviar"]').is_visible(), 'celular: botão de enviar acessível')
    pg.close()
    mov.close()

    # ── file:// ──
    print('\n— file://')
    pg = abrir(ctx, (RAIZ / 'app' / 'paralelismo.html').as_uri())
    pg.wait_for_selector('#par-app:visible', timeout=20000)
    pg.click('.par-aba[data-aba=\"processar\"]')   # a abertura agora é o Painel
    confere(pg.locator('#par-demo').is_visible(), 'file://: abre em demonstração, sem login')
    pg.wait_for_function('PAR.itens.length === 1', timeout=10000)
    confere(not pg.erros, f'file://: sem erro de script ({pg.erros})')
    pg.close()
    nav.close()

srv.shutdown()
print(f'\n{"FALHOU" if falhas else "OK"}: {len(falhas)} falha(s)')
sys.exit(1 if falhas else 0)
