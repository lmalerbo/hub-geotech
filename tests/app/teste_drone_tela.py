"""Teste da tela do Drone (Playwright + Edge). Roda à mão:
    set HUB_CONTA_TESTE=C:/caminho/conta-teste.json
    python tests/app/teste_drone_tela.py
Dá à conta de teste o papel de editor do Drone só durante o teste e devolve o papel original no fim.
Gera uma prévia da fazenda 10974 e DESCARTA (não publica nada); cancela a solicitação criada.
Também confere a tela só leitura (admin desligado e nível 'leitura' no Drone) e devolve admin e nível originais."""
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
u = b.selecionar('usuarios', 'id,papel,admin', {'id': f"eq.{conta['id']}"})[0]
papel_orig = u['papel']
admin_orig = u['admin']
linhas_drone = b.selecionar('usuario_modulos', 'modulo_id,nivel', {'usuario_id': f"eq.{u['id']}", 'modulo_id': 'eq.drone'})
tinha_drone = bool(linhas_drone)
nivel_orig = linhas_drone[0]['nivel'] if linhas_drone else None
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


def definir_acesso(admin, nivel):
    b.atualizar('usuarios', {'id': f"eq.{u['id']}"}, {'admin': admin})
    b.atualizar('usuario_modulos', {'usuario_id': f"eq.{u['id']}", 'modulo_id': 'eq.drone'}, {'nivel': nivel})


def devolver_acesso():
    # Conta sem linha de Drone antes do teste: a linha criada aqui é apagada no finally; o nível não importa.
    definir_acesso(admin_orig, nivel_orig if tinha_drone else 'editor')


def entrar_e_abrir(pg):
    # Depois de um reload: a sessão pode já estar de pé ou a tela de login aparece. Entra e abre a 10974 pela busca.
    pg.wait_for_function('(typeof EU!=="undefined"&&!!EU&&!!EU.perms)'
                         '||document.getElementById("f-email").getClientRects().length>0', timeout=60000)
    if not pg.evaluate('typeof EU!=="undefined"&&!!EU&&!!EU.perms'):
        pg.fill('#f-email', conta['email']); pg.fill('#f-pass', conta['senha']); pg.click('#btn-entrar')
    pg.wait_for_function('typeof EU!=="undefined" && EU && EU.perms && EU.perms.drone', timeout=60000)
    pg.evaluate("trocar('drone',document.querySelector('.ni[onclick*=\"drone\"]'))")
    pg.wait_for_selector('#dri .dri-col', timeout=20000)
    pg.fill('#dr-busca', str(FAZ)); pg.wait_for_selector('#dr-busca-res .dr-it'); pg.click('#dr-busca-res .dr-it')
    pg.wait_for_selector('#dr-map canvas', timeout=20000)
    pg.wait_for_timeout(1500)


H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(RAIZ / 'app'))
srv = socketserver.TCPServer(('127.0.0.1', 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f'http://127.0.0.1:{srv.server_address[1]}/index.html'
sol_criada = None
try:
    b.atualizar('usuarios', {'id': f"eq.{u['id']}"}, {'papel': 'editor'})
    if not tinha_drone:
        b.inserir('usuario_modulos', {'usuario_id': u['id'], 'modulo_id': 'drone', 'nivel': 'editor'})
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
        confere(pg.locator('nav.dr-abas .dr-aba').count() == 2, 'abas Normal e Catação')
        confere(pg.locator('#dri').is_hidden() and pg.locator('#dr-trab').is_visible(), 'Início escondido e fazenda aberta')
        # S2.2: o mapa não é recriado pelo polling nem pela troca Normal/Catação
        pg.evaluate("window.__mapa=DR.mapa")
        pg.evaluate("async()=>{await drCarregarFazenda();await drCarregarFazenda();}")
        pg.click('nav.dr-abas .dr-aba >> nth=1'); pg.click('nav.dr-abas .dr-aba >> nth=0')
        confere(pg.evaluate("DR.mapa===window.__mapa"), 'mapa reaproveitado no polling e na troca de documento')

        # S4.7 caso 1: barra de etapas, barra de ferramentas e chip de obstáculos (editor)
        confere(pg.locator('#dr-etapas').is_visible()
                and pg.get_attribute('#dr-etapas [data-etapa="0"]', 'aria-current') == 'step',
                'barra de etapas visível com a primeira etapa atual')
        confere(pg.locator('#dr-ferr').is_visible(), 'barra de ferramentas do mapa visível')
        confere((pg.text_content('.dr-obst-chip') or '').strip() != '', 'chip de obstáculos com texto')

        # S4.7 caso 2: fonte por talhão (Sistema | Shape) sobrevive a um ciclo de atualização
        pg.evaluate("drFerramenta('limpar')")
        pg.evaluate("""()=>{DR.geo.features.filter(f=>f.properties.camada==='talhao'&&f.properties.status!=='fora_da_base')
            .slice(0,2).forEach(f=>drClicarTalhao(f.properties));}""")
        ns = pg.evaluate("[...DR.sel.keys()]")
        n1 = ns[0] if ns else -1
        confere(len(ns) == 2, f'dois talhões marcados ({ns})')
        pg.evaluate(f"drFonteTalhao({n1},'shape')")
        confere(pg.locator('.dr-solta').count() == 1, 'botão de soltar o shape de ajuste aparece')
        pg.evaluate("async()=>{await drCarregarFazenda();}")
        confere(pg.evaluate(f"DR.sel.size===2&&DR.sel.get({n1})==='shape'")
                and pg.get_attribute(f'[data-foco="f{n1}h"]', 'aria-pressed') == 'true',
                'depois do ciclo a seleção tem os 2 talhões e o primeiro segue em Shape')
        pg.evaluate(f"drFonteTalhao({n1},'sistema')")

        # S4.7 caso 3: estado 'gerando' (antes do gerar_uma, que roda na hora)
        pg.click('#dr-side-rodape button:has-text("Gerar prévia")')
        pg.wait_for_selector('#dr-side-cab h2:has-text("Gerando a prévia")', timeout=15000)
        confere(pg.locator('#dr-ferr').is_hidden(), 'ferramentas escondidas enquanto gera')
        confere('travado' in (pg.text_content('#dr-dica') or ''), 'dica diz que o mapa está travado')
        t1 = pg.text_content('#dr-decorrido'); pg.wait_for_timeout(2100); t2 = pg.text_content('#dr-decorrido')
        confere(t1 != t2, f'tempo decorrido anda ({t1} → {t2})')
        sol_criada = pg.evaluate("drAtual().sol.id")
        dup = pg.evaluate("""async s=>{const {error}=await sb.rpc('drone_pedir_geracao',
            {p_solicitacao_id:s,p_escopo:{incluir:[{talhao:DR.geo.features[0].properties.talhao,fonte:'sistema'}],remover:[]}});
            return error?error.message:''}""", sol_criada)
        confere('prévia aberta' in dup, f'segunda geração da mesma fazenda é recusada ({dup[:60]})')
        # processa só a geração deste teste (a fila estava vazia antes), sem envios nem publicações
        os.system(f'"{sys.executable}" -c "from drone.agente import gerar_uma; from drone.banco import DroneBanco; '
                  f'from drone.config import cfg; gerar_uma(DroneBanco(), cfg())"')
        pg.evaluate("drCarregarFazenda()")

        # S4.7 caso 4: prévia pronta (painel "Confira antes de publicar")
        pg.wait_for_selector('#dr-side-cab h2:has-text("Confira antes de publicar")', timeout=60000)
        confere(' ha' in (pg.text_content('.drp-indic') or ''), 'painel mostra o indicador de área em ha')
        confere(pg.locator('.dr-mot-painel').count() == 1, 'campo de motivo no painel')
        # a janela abre sozinha quando a geração termina com a tela aberta
        pg.wait_for_selector('#drp-fundo', timeout=10000)
        pg.wait_for_selector('.drp-pg.ok canvas, #drp-carga .dr-err', timeout=30000)
        confere(pg.locator('.drp-pg.ok canvas').count() >= 1, f"PDF da prévia desenhado na janela {pg.inner_text('#drp-pags')[:120]}")
        confere(pg.locator('#dr-pdf canvas').count() == 1, 'capa da prévia no painel')
        # Foco 1: o motivo digitado na janela da prévia sobrevive a um ciclo de atualização
        pg.evaluate("drPrevFechar()"); pg.click('#dr-pdf'); pg.fill('#dr-mot', 'teste S2')
        pg.evaluate("drCarregarFazenda()"); pg.wait_for_timeout(1500)
        confere(pg.input_value('#dr-mot') == 'teste S2', 'motivo na janela continua depois do polling')
        # e o motivo digitado no painel sobrevive a um ciclo (com a janela fechada, o campo do painel fica acessível)
        pg.evaluate("drPrevFechar()")
        pg.fill('.dr-mot-painel', 'teste S4')
        pg.evaluate("drCarregarFazenda()"); pg.wait_for_timeout(1500)
        confere(pg.input_value('.dr-mot-painel') == 'teste S4', 'motivo no painel continua depois do polling')
        pg.click('#dr-pdf')
        pg.click('#drp-fundo button:has-text("Descartar")')
        pg.click('#confirma-sim')
        pg.wait_for_selector('#dr-side-cab .dr-side-sobre:has-text("Nova revisão")', timeout=15000)
        confere(True, 'prévia descartada, seleção liberada')

        # S4.7 caso 5: conta só leitura (Foco 4), depois do descarte e antes do ← Início
        definir_acesso(False, 'leitura')
        pg.reload(); entrar_e_abrir(pg)
        confere(pg.evaluate('podeEditar("drone")') is False, 'conta só leitura: podeEditar("drone") é falso')
        confere('Somente consulta' in (pg.text_content('#dr-side') or ''), 'painel diz "Somente consulta"')
        confere(pg.locator('#dr-side button').count() == 0, 'nenhum botão dentro do painel')
        confere(pg.evaluate("(()=>{const f=document.getElementById('dr-ferr');return !f||f.hidden||!f.innerHTML})()"),
                'barra de ferramentas escondida ou vazia')
        confere(pg.evaluate("(()=>{const o=document.querySelector('.dr-obst');return !!o&&o.tagName!=='BUTTON'})()"),
                '.dr-obst não é botão')
        pg.evaluate("drMenuAbrir()")
        itens = pg.evaluate("[...document.querySelectorAll('#dr-menu [role=menuitem]')].map(x=>x.textContent.trim())")
        # o menu traz "Cancelar solicitação" quando a conta é a solicitante (regra de drPodeCancelar); fora isso, só Revisões
        confere(itens and 'Revisões' in itens[0] and all(i.endswith('Cancelar solicitação') for i in itens[1:]),
                f'menu ⋯ sem ações de edição ({itens})')
        pg.evaluate("drMenuFechar()")
        antes = pg.evaluate("DR.sel.size")
        pg.evaluate("""()=>{const f=DR.geo.features.find(f=>f.properties.camada==='talhao'&&f.properties.status!=='fora_da_base');
            drClicarTalhao(f.properties);}""")
        confere(pg.evaluate("DR.sel.size") == antes, 'clicar em talhão não muda a seleção')
        devolver_acesso()
        pg.reload(); entrar_e_abrir(pg)

        # ← Início volta às três colunas, sem a 10974 em "A analisar"
        pg.click('.dr-ini'); pg.wait_for_selector('#dri', state='visible', timeout=10000); pg.evaluate('async () => { await drCarregarPainel(); }')  # conta depois do redesenho
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
    b.atualizar('usuarios', {'id': f"eq.{u['id']}"}, {'papel': papel_orig, 'admin': admin_orig})
    if tinha_drone:
        b.atualizar('usuario_modulos', {'usuario_id': f"eq.{u['id']}", 'modulo_id': 'eq.drone'}, {'nivel': nivel_orig})
    else:
        import requests
        requests.delete(f'{b.url}/usuario_modulos', params={'usuario_id': f"eq.{u['id']}", 'modulo_id': 'eq.drone'},
                        headers=b.headers, timeout=60)
    srv.shutdown()
print('FALHAS:', falhas if falhas else 'nenhuma')
sys.exit(1 if falhas else 0)
