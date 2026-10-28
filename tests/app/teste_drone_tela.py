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
u = b.selecionar('usuarios', 'id,papel', {'id': f"eq.{conta['id']}"})[0]
papel_orig = u['papel']
tinha_drone = bool(b.selecionar('usuario_modulos', 'modulo_id', {'usuario_id': f"eq.{u['id']}", 'modulo_id': 'eq.drone'}))
falhas = []

# Nunca mexe em trabalho real: só roda com a 10974 sem solicitação aberta e a fila do agente vazia.
FAZ = 10974
abertas = b.selecionar('drone_solicitacoes', 'id', {'cod_faz': f'eq.{FAZ}', 'origem': 'neq.legado',
                                                     'status': 'not.in.(ok,cancelado)'})
fila = (b.selecionar('drone_geracoes', 'id', {'status': 'in.(fila,processando)'})
        + b.selecionar('drone_geracoes', 'id', {'status': 'eq.pronta', 'publicar_pedido_em': 'not.is.null',
                                                'publicacao_erro': 'is.null'})
        + b.selecionar('drone_envios', 'id', {'status': 'in.(fila,processando)'}))
if abertas or fila:
    sys.exit(f'Teste NÃO rodou (nada foi alterado): solicitações abertas da {FAZ}: {abertas}; itens na fila: {fila}')


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
        pg.wait_for_function('typeof EU!=="undefined" && EU && EU.perms && EU.perms.drone', timeout=60000)
        pg.evaluate("trocar('drone',document.querySelector('.ni[onclick*=\"drone\"]'))")
        pg.wait_for_selector('#dri .dri-col', timeout=20000)
        confere(pg.locator('#dri .dri-col').count() == 3, 'Início com três colunas')
        pg.fill('#dr-busca', '10974'); pg.wait_for_selector('#dr-busca-res .dr-it'); pg.click('#dr-busca-res .dr-it')
        pg.wait_for_selector('#dr-map canvas', timeout=20000)
        pg.wait_for_timeout(1500)
        confere(pg.locator('.dr-doc').count() == 2, 'cartões Normal e Catação')
        confere(pg.locator('#dri').is_hidden() and pg.locator('#dr-trab').is_visible(), 'Início escondido e fazenda aberta')
        # S2.2: o mapa não é recriado pelo polling nem pela troca Normal/Catação
        pg.evaluate("window.__mapa=DR.mapa")
        pg.evaluate("async()=>{await drCarregarFazenda();await drCarregarFazenda();}")
        pg.click('.dr-doc >> nth=1'); pg.click('.dr-doc >> nth=0')
        confere(pg.evaluate("DR.mapa===window.__mapa"), 'mapa reaproveitado no polling e na troca de documento')
        pg.evaluate("drSelecionarSemProjeto()")
        sem = pg.evaluate("DR.sel.size")
        if sem == 0:
            pg.evaluate("const f=DR.geo.features.find(f=>f.properties.camada==='talhao');drClicarTalhao(f.properties)")
        confere(pg.evaluate("DR.sel.size") > 0, 'seleção de talhões')
        pg.click('text=Gerar prévia')
        pg.wait_for_selector('text=Gerando prévia', timeout=15000)
        confere(True, 'pedido de geração aceito')
        sol_criada = pg.evaluate("drAtual().sol.id")
        dup = pg.evaluate("""async s=>{const {error}=await sb.rpc('drone_pedir_geracao',
            {p_solicitacao_id:s,p_escopo:{incluir:[{talhao:DR.geo.features[0].properties.talhao,fonte:'sistema'}],remover:[]}});
            return error?error.message:''}""", sol_criada)
        confere('prévia aberta' in dup, f'segunda geração da mesma fazenda é recusada ({dup[:60]})')
        # processa só a geração deste teste (a fila estava vazia antes), sem envios nem publicações
        os.system(f'"{sys.executable}" -c "from drone.agente import gerar_uma; from drone.banco import DroneBanco; '
                  f'from drone.config import cfg; gerar_uma(DroneBanco(), cfg())"')
        pg.evaluate("drCarregarFazenda()")
        pg.wait_for_selector('text=Prévia pronta', timeout=60000)
        # a janela abre sozinha quando a geração termina com a tela aberta
        pg.wait_for_selector('#drp-fundo', timeout=10000)
        pg.wait_for_selector('.drp-pg.ok canvas, #drp-carga .dr-err', timeout=30000)
        confere(pg.locator('.drp-pg.ok canvas').count() >= 1, f"PDF da prévia desenhado na janela {pg.inner_text('#drp-pags')[:120]}")
        confere(pg.locator('#dr-pdf canvas').count() == 1, 'capa da prévia no painel')
        # Foco 1: o motivo digitado na prévia sobrevive a um ciclo de atualização
        # (a janela já abre sozinha, então fecha antes para o botão 'Abrir prévia' do painel ficar clicável)
        pg.evaluate("drPrevFechar()"); pg.click('text=Abrir prévia'); pg.fill('#dr-mot', 'teste S2')
        pg.evaluate("drCarregarFazenda()"); pg.wait_for_timeout(1500)
        confere(pg.input_value('#dr-mot') == 'teste S2', 'motivo continua depois do polling')
        pg.click('#drp-fundo button:has-text("Descartar")')
        pg.click('#confirma-sim')
        pg.wait_for_selector('text=Nova revisão', timeout=15000)
        confere(True, 'prévia descartada, seleção liberada')
        # ← Início volta às três colunas, sem a 10974 em "A analisar"
        pg.click('.dri-voltar'); pg.wait_for_selector('#dri', state='visible', timeout=10000)
        confere(pg.locator('#dri .dri-col').count() == 3 and pg.locator('#dri .dri-col[data-col="analisar"] .dri-card[data-cod="10974"]').count() == 0,
                'Início volta com três colunas e sem a 10974 em A analisar')
        canc = pg.evaluate("""async s=>{const {error}=await sb.rpc('drone_cancelar',
            {p_solicitacao_id:s,p_motivo:'teste automatizado'});return error?error.message:''}""", sol_criada)
        st = b.selecionar('drone_solicitacoes', 'status,cancelado_motivo', {'id': f'eq.{sol_criada}'})[0]
        confere(canc == '' and st['status'] == 'cancelado', f'cancelar solicitação pela tela ({canc or st})')
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
