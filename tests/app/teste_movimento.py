"""Teste de app/motion.js (Playwright + Edge) na vitrine app/motion-demo.html. Sem banco, sem conta.
    python tests/app/teste_movimento.py [pasta_para_capturas]
Confere cada função do contrato (Mo.*) com e sem prefers-reduced-motion."""
import functools
import http.server
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
CAPT = Path(sys.argv[1]) if len(sys.argv) > 1 else None
sys.stdout.reconfigure(encoding='utf-8')


class Quieto(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


H = functools.partial(Quieto, directory=str(RAIZ / 'app'))
srv = socketserver.TCPServer(('127.0.0.1', 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f'http://127.0.0.1:{srv.server_address[1]}/motion-demo.html'
falhas = []


def confere(nome, cond):
    print(('ok   ' if cond else 'FALHA ') + nome)
    if not cond:
        falhas.append(nome)


def foto(pg, nome):
    if CAPT:
        CAPT.mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(CAPT / f'{nome}.png'))


def rodar(pg, calmo):
    sufixo = ' (menos movimento)' if calmo else ''
    erros = []
    pg.on('pageerror', lambda e: erros.append(str(e)))
    pg.goto(url)

    # ocupado → ✓ e volta ao normal com o rótulo intacto
    b = pg.locator('#b-ok')
    rotulo = b.inner_text()
    b.click()
    pg.wait_for_timeout(150)
    confere('ocupado: desabilita e mostra o campo' + sufixo,
            b.evaluate("b=>b.disabled&&b.classList.contains('mo-ocupado')&&!!b.querySelector('.mo-campo')"))
    if not calmo:
        foto(pg, '1-ocupado')
    pg.wait_for_timeout(1250)
    confere('ocupado: ✓ no fim' + sufixo, b.evaluate("b=>b.classList.contains('mo-ok')"))
    pg.wait_for_timeout(1000)
    confere('ocupado: volta ao normal' + sufixo,
            b.evaluate("b=>!b.disabled&&!b.className.match(/mo-(ok|ocupado|fim)/)") and b.inner_text() == rotulo)
    pg.locator('#b-erro').click()
    pg.wait_for_timeout(1300)
    confere('ocupado: ✕ no erro' + sufixo, pg.locator('#b-erro').evaluate("b=>b.classList.contains('mo-erro')"))

    # progresso → % e MB reais, termina em ✓
    pg.locator('#b-prog').click()
    pg.wait_for_timeout(600)
    meio = pg.locator('#prog .mo-prog-pct').inner_text()
    mb = pg.locator('#prog .mo-prog-mb').inner_text()
    confere(f'progresso: % parcial ({meio}) e MB ({mb})' + sufixo, meio.endswith('%') and meio != '0%' and 'MB' in mb)
    if not calmo:
        foto(pg, '2-progresso')
    pg.wait_for_timeout(4500)
    confere('progresso: termina em ✓' + sufixo, pg.locator('#prog .mo-prog').evaluate("p=>p.classList.contains('mo-ok')"))

    # carregando/pronto → esboço aparece e some, conteúdo novo entra
    pg.locator('#b-lista').click()
    pg.wait_for_timeout(200)
    confere('carregando: esboço visível' + sufixo, pg.locator('#lista .mo-esboco').count() == 1)
    if not calmo:
        foto(pg, '3-carregando')
    pg.wait_for_timeout(1500)
    confere('pronto: esboço removido e 6 itens' + sufixo,
            pg.locator('#lista .mo-esboco').count() == 0 and pg.locator('#lista > div').count() == 6)

    # carregando discreto → conteúdo continua visível, sem linhas de esboço
    disc = pg.evaluate("""()=>{const l=document.getElementById('lista');Mo.carregando(l,{discreto:true});
      const r={barras:l.querySelectorAll('.mo-esboco>i').length,campo:!!l.querySelector('.mo-esboco .mo-campo'),
        opac:getComputedStyle(l.firstElementChild).opacity};Mo.pronto(l,{cascata:false});return r;}""")
    confere(f'carregando discreto: {disc}' + sufixo, disc['barras'] == 0 and disc['campo'] and disc['opac'] == '1')

    # etapa → marca aparece (sem ela com menos movimento) e a Promise resolve
    pg.locator('#b-etapa').click()
    pg.wait_for_timeout(250)
    tem_marca = pg.locator('#barra .mo-etapa-marca').count() == 1
    confere('etapa: marca deslizando' + sufixo, tem_marca != calmo)
    if not calmo:
        foto(pg, '4-etapa')
    pg.wait_for_timeout(1300)
    confere('etapa: termina e redesenha' + sufixo,
            pg.locator('#barra .mo-etapa-marca').count() == 0
            and pg.locator('#barra [data-etapa=andamento]').evaluate("d=>d.classList.contains('on')"))

    # concluido → selo + confete (sem confete com menos movimento), some sozinho
    pg.locator('#b-conc').click()
    pg.wait_for_timeout(450)
    confere('concluido: selo e texto' + sufixo,
            pg.locator('#faz .mo-conc-selo').count() == 1 and pg.locator('#faz .mo-conc-txt').inner_text() == 'Fazenda em Ok')
    confere('concluido: confete só com movimento' + sufixo, (pg.locator('#faz .mo-conc-p').count() > 0) != calmo)
    if not calmo:
        foto(pg, '5-concluido')
    pg.wait_for_timeout(1700)
    confere('concluido: some sozinho' + sufixo, pg.locator('#faz .mo-conc').count() == 0)

    # voo → drone sobrevoando (andando, sem movimento fica parado), pousa em ✓ ou mostra o erro
    pg.locator('#b-voo-ok').click()
    mapa = pg.locator('#mapa-voo')
    pg.wait_for_timeout(700)
    p1 = mapa.locator('.mo-voo-rota').evaluate("r=>getComputedStyle(r).transform")
    pg.wait_for_timeout(600)
    p2 = mapa.locator('.mo-voo-rota').evaluate("r=>getComputedStyle(r).transform")
    confere('voo: drone e texto visíveis' + sufixo,
            mapa.locator('.mo-voo-drone svg').count() == 1 and 'Publicando' in mapa.locator('.mo-voo-txt').inner_text())
    confere('voo: drone anda só com movimento' + sufixo, (p1 != p2) != calmo)
    if not calmo:
        foto(pg, '6-voo')
    pg.wait_for_timeout(3400)
    confere('voo: pousa e vira ✓' + sufixo,
            mapa.locator('.mo-voo').count() == 0 and mapa.locator('.mo-conc-txt').inner_text() == 'Publicado no portal')
    pg.wait_for_timeout(2000)
    pg.locator('#b-voo-erro').click()
    pg.wait_for_timeout(4400)
    confere('voo: falha mostra o erro' + sufixo, 'Falha ao publicar' in mapa.locator('.mo-voo-txt.mo-erro').inner_text())
    pg.wait_for_timeout(2300)
    confere('voo: some depois da falha' + sufixo, mapa.locator('.mo-voo').count() == 0)

    pg.click('#b-trilho')
    confere('trilho e varredura aparecem' + sufixo,
            pg.locator('#gerando .mo-trilho').count() == 1 and pg.locator('#mapa-varr .mo-varr').count() == 1)
    confere('varredura não pega clique' + sufixo,
            pg.locator('#mapa-varr .mo-varr').evaluate("v=>getComputedStyle(v).pointerEvents") == 'none')
    anim = pg.locator('#mapa-varr .mo-varr i').evaluate("i=>getComputedStyle(i).animationName")
    confere(f'varredura anda só com movimento ({anim})' + sufixo, (anim != 'none') != calmo)
    pg.click('#b-trilho'); pg.wait_for_timeout(400)
    confere('trilho e varredura somem' + sufixo,
            pg.locator('#gerando .mo-trilho').count() == 0 and pg.locator('#mapa-varr .mo-varr').count() == 0)
    pg.click('#b-mover')
    if not calmo:
        confere('mover: anima transform no meio' + sufixo,
                pg.locator('[data-id=c1]').evaluate("e=>e.getAnimations().length") > 0)
    pg.evaluate("window.__mov")
    confere('mover: termina no lugar novo e sem animação' + sufixo,
            pg.locator('#col-b [data-id=c1]').count() == 1
            and pg.locator('[data-id=c1]').evaluate("e=>e.getAnimations().length") == 0)

    confere('sem erro de JS' + sufixo, not erros)


with sync_playwright() as p:
    nav = p.chromium.launch(channel='msedge')
    for calmo in (False, True):
        ctx = nav.new_context(viewport={'width': 1200, 'height': 800}, reduced_motion='reduce' if calmo else 'no-preference')
        rodar(ctx.new_page(), calmo)
        ctx.close()
    nav.close()
srv.shutdown()
print(f'\n{len(falhas)} falha(s)')
sys.exit(1 if falhas else 0)
