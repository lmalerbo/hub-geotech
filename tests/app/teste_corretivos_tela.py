"""Teste de ponta a ponta dos Corretivos (Playwright + Edge, banco real). Roda Ã  mÃ£o, da raiz do repositÃ³rio:
    set HUB_CONTA_TESTE=C:/caminho/conta-teste.json
    python tests/app/teste_corretivos_tela.py
DÃ¡ Ã  conta de teste o mÃ³dulo 'corretivos' sÃ³ durante o teste e devolve o acesso original no fim.
Cria um mapa de corretivo na fazenda 10974, lanÃ§a aplicaÃ§Ãµes, baixa o PDF e EXCLUI o mapa que ele mesmo criou."""
import functools
import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
from pathlib import Path

import pymupdf
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
# As credenciais (hub-geotech-supabase.env) só existem no clone principal; numa worktree, usa o banco de lá.
_BANCO = RAIZ if (RAIZ / 'hub-geotech-supabase.env').exists() else RAIZ.parent / 'hub-geotech'
sys.path.insert(0, str(_BANCO))
from drone.banco import DroneBanco  # noqa: E402

conta = json.loads(Path(os.environ['HUB_CONTA_TESTE']).read_text(encoding='utf-8'))
b = DroneBanco()
uid = conta['id']
tinha_modulo = bool(b.selecionar('usuario_modulos', 'modulo_id', {'usuario_id': f'eq.{uid}', 'modulo_id': 'eq.corretivos'}))
FAZ = 10974
falhas = []


def remover(tabela, filtro):
    """DELETE com service_role (o mÃ³dulo comum nÃ£o tem; uso sÃ³ para limpar o que este teste criou)."""
    import requests
    r = requests.delete(f'{b.url}/{tabela}', params=filtro, headers=b.headers, timeout=60)
    r.raise_for_status()


def confere(cond, msg):
    print(('âœ“ ' if cond else 'âœ— ') + msg)
    if not cond:
        falhas.append(msg)


subprocess.run([sys.executable, str(RAIZ / 'mapas' / 'publicar.py'), str(RAIZ / 'app' / 'py')], check=True)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(RAIZ / 'app'))
H.log_message = lambda *a: None
srv = socketserver.TCPServer(('127.0.0.1', 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f'http://127.0.0.1:{srv.server_address[1]}/corretivos.html'
mapa_id = None
try:
    if not tinha_modulo:
        b.inserir('usuario_modulos', {'usuario_id': uid, 'modulo_id': 'corretivos'})
    with sync_playwright() as p:
        nav = p.chromium.launch(channel='msedge')
        pg = nav.new_page(viewport={'width': 1400, 'height': 900}, accept_downloads=True)
        erros = []
        pg.on('pageerror', lambda e: erros.append(str(e)))
        pg.goto(url)
        pg.wait_for_selector('#cr-email:visible, #cr-busca:visible', timeout=30000)
        if pg.locator('#cr-email').is_visible():
            pg.fill('#cr-email', conta['email']); pg.fill('#cr-senha', conta['senha']); pg.click('#cr-entrar')
        pg.wait_for_selector('#cr-busca:visible', timeout=30000)
        confere(True, 'login e acesso ao mÃ³dulo')

        pg.fill('#cr-busca', str(FAZ)); pg.wait_for_selector('#cr-res .cr-it'); pg.click('#cr-res .cr-it')
        pg.wait_for_selector('[data-novo]:visible', timeout=20000)
        antes = {m['id'] for m in b.selecionar('corretivo_mapas', 'id', {'cod_faz': f'eq.{FAZ}'})}
        pg.click('[data-novo]'); pg.click('#cr-modal-fundo button:has-text("Arado")')
        pg.wait_for_selector('#cr-mapa canvas', timeout=30000)
        pg.wait_for_function('CR_ST.geo && CR_ST.det', timeout=30000)
        novos = [m['id'] for m in b.selecionar('corretivo_mapas', 'id', {'cod_faz': f'eq.{FAZ}'}) if m['id'] not in antes]
        confere(len(novos) == 1, 'mapa Arado criado no banco')
        mapa_id = novos[0] if novos else None
        t = pg.evaluate('CR_ST.geo.features.map(f => f.properties.talhao).sort((a, b) => a - b)')
        A, B = t[0], t[1]

        def aplicar(form, talhoes):
            pg.evaluate("([f, ts]) => { CR_ST.sel = new Set(ts); Object.assign(CR_ST.form, f); crAtualizarEstados(); crRenderPainel(); }",
                        [form, talhoes])
            pg.click('[data-aplicar]')
            pg.wait_for_timeout(2500)

        aplicar({'tipo': 'calcario', 'calcario': 'dolomitico', 'dose': '2', 'gesso': '', 'os': 'E2E-1'}, [A, B])
        aplicar({'tipo': 'blend', 'calcario': 'ph7', 'dose': '1.5', 'gesso': '1', 'os': 'E2E-2'}, [B])
        apls = b.selecionar('corretivo_aplicacoes', 'id,tipo,os', {'mapa_id': f'eq.{mapa_id}'})
        confere(sorted(a['os'] for a in apls) == ['E2E-1', 'E2E-2'], 'duas aplicaÃ§Ãµes gravadas (calcÃ¡rio e blend)')

        aplicar({'tipo': 'calcario', 'calcario': 'dolomitico', 'dose': '2', 'gesso': '', 'os': 'E2E-1'}, [A])
        confere(len(b.selecionar('corretivo_aplicacoes', 'id', {'mapa_id': f'eq.{mapa_id}'})) == 2,
                'a tela recusa a mesma aplicaÃ§Ã£o no mesmo talhÃ£o')
        dup = b.inserir('corretivo_aplicacoes', {'mapa_id': mapa_id, 'tipo': 'calcario', 'calcario': 'dolomitico',
                                                 'dose': 2, 'os': 'E2E-1', 'ordem': 9})
        dup_id = (dup[0] if isinstance(dup, list) else dup)['id']
        try:
            b.inserir('corretivo_aplicacao_talhoes', {'aplicacao_id': dup_id, 'mapa_id': mapa_id, 'talhao_num': A})
            confere(False, 'o banco recusa a mesma aplicaÃ§Ã£o no mesmo talhÃ£o')
        except Exception as e:  # noqa: BLE001
            confere('jÃ¡ tem esta aplicaÃ§Ã£o' in str(e), 'o banco recusa a mesma aplicaÃ§Ã£o no mesmo talhÃ£o')
        remover('corretivo_aplicacoes', {'id': f'eq.{dup_id}'})

        pg.evaluate("async ([id, t]) => { await crApi().salvarArea(id, t, 7.77); await crRecarregar(); }", [mapa_id, A])
        ta = b.selecionar('corretivo_talhoes', 'area_ha,area_editada', {'mapa_id': f'eq.{mapa_id}', 'talhao_num': f'eq.{A}'})[0]
        confere(float(ta['area_ha']) == 7.77 and ta['area_editada'], 'Ã¡rea editada gravada e marcada')

        pg.wait_for_selector('[data-pdf]:not([disabled])', timeout=240000)
        with pg.expect_download(timeout=240000) as dl:
            pg.click('[data-pdf]')
        destino = RAIZ / '.prints' / 'e2e_corretivo.pdf'
        destino.parent.mkdir(exist_ok=True)
        dl.value.save_as(destino)
        texto = '\n'.join(pagina.get_text() for pagina in pymupdf.open(destino))
        confere(dl.value.suggested_filename.startswith(f'corretivo_{FAZ}_arado_'), 'nome do arquivo do PDF')
        for esperado in ['CORRETIVO Â· ARADO', 'E2E-1', 'Blend PH7', '7,77*']:
            confere(esperado in texto, f'PDF contÃ©m "{esperado}"')

        pg.click('#cr-voltar'); pg.wait_for_selector(f'[data-excluir="{mapa_id}"]', timeout=20000)
        pg.click(f'[data-excluir="{mapa_id}"]'); pg.click('#cr-modal-fundo button:has-text("Excluir")')
        pg.wait_for_timeout(2500)
        confere(not b.selecionar('corretivo_mapas', 'id', {'id': f'eq.{mapa_id}'}), 'mapa excluÃ­do pela tela')
        log = b.selecionar('log_auditoria', 'id', {'modulo_id': 'eq.corretivos', 'campo': 'eq.mapa_corretivo',
                                                   'valor_anterior': f'like.mapa {mapa_id} *'})
        confere(bool(log), 'exclusÃ£o registrada no log de auditoria')
        if not b.selecionar('corretivo_mapas', 'id', {'id': f'eq.{mapa_id}'}):
            mapa_id = None
        confere(not erros, f'sem erros de JavaScript ({erros[:2]})')
        nav.close()
finally:
    if mapa_id:                              # sÃ³ apaga o que o prÃ³prio teste criou
        remover('corretivo_mapas', {'id': f'eq.{mapa_id}'})
    if not tinha_modulo:
        remover('usuario_modulos', {'usuario_id': f'eq.{uid}', 'modulo_id': 'eq.corretivos'})
    srv.shutdown()
print('FALHAS:', falhas or 'nenhuma')
sys.exit(1 if falhas else 0)
