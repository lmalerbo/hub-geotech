"""Prova no Edge: do File do pen-drive até o resultado, pelo OPFS, pela fila e pelo Web Worker (Playwright, sem banco e sem
tela). Compara com o Python nativo. O servidor só escuta em 127.0.0.1; da internet vêm só o Pyodide e o pyshp.
Roda à mão, da raiz do repositório:
    python tests/app/teste_paralelismo_worker.py
Com tests/dados/paralelismo/amostra.* presentes (fora do git, ver o LEIAME.md de lá), compara também as amostras reais.
"""
import base64
import functools
import http.server
import io
import json
import re
import statistics
import struct
import sys
import tempfile
import threading
import time
import urllib.parse
import zipfile
from pathlib import Path

import shapefile
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from mapas.publicar import publicar  # noqa: E402
from paralelismo.analise import analisar_fazenda, linhas_do_grupo, para_utm, talhoes_de_geojson  # noqa: E402
from paralelismo.gs3 import ler_gs3, ler_sessao  # noqa: E402
from paralelismo.jdl import ler_jdl  # noqa: E402
from tests.paralelismo.test_leitores_sinteticos import (FDL, campo_int, coluna_estado, coluna_numerica,  # noqa: E402
                                                        item_estado, item_rico, registro_gs3, registro_jdl)

AMOSTRAS = RAIZ / 'tests' / 'dados' / 'paralelismo'
falhas = []
pedidos_py = []


def confere(cond, msg):
    print(('✓ ' if cond else '✗ ') + msg, flush=True)
    if not cond:
        falhas.append(msg)


class Servidor(http.server.SimpleHTTPRequestHandler):
    """/ = app/; /py/ = publicado numa pasta temporária; /amostras/ = tests/dados/paralelismo."""

    def __init__(self, *args, py_dir=None, **kwargs):
        self.py_dir = py_dir
        super().__init__(*args, directory=str(RAIZ / 'app'), **kwargs)

    def translate_path(self, path):
        caminho = urllib.parse.unquote(urllib.parse.urlsplit(path).path)
        if caminho.startswith('/py/'):
            pedidos_py.append(caminho[4:])
            return str(Path(self.py_dir) / caminho[4:])
        if caminho.startswith('/amostras/'):
            return str(AMOSTRAS / Path(caminho).name)
        return super().translate_path(path)

    def do_GET(self):
        if self.path == '/bancada.html':
            corpo = b'<!doctype html><meta charset="utf-8"><input id="pasta" type="file" webkitdirectory>'
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return
        super().do_GET()

    def log_message(self, *a):
        pass


# Roda na página: mesmo caminho que a tela da S3 vai usar, com as escolhas do usuário já feitas.
AJUDANTES = r"""
window.parTeste = {
  // Vira File com o caminho que teria no pen-drive; o conteúdo vem do servidor local.
  async arquivo(url, caminho) {
    const b = await (await fetch(url)).blob();
    const f = new File([b], caminho.split('/').pop());
    Object.defineProperty(f, 'webkitRelativePath', { value: caminho });
    return f;
  },
  async rodar(files, frotaDe, bases) {
    const id = crypto.randomUUID();
    const inicio = performance.now();
    const copia = await parOpfsCopiar(id, files);
    const copiaS = (performance.now() - inicio) / 1000;
    const conf = parConferencia([...copia.arquivos, ...copia.mapas], [], []).map((g) => {
      const [frota, operacao] = frotaDe(g);
      return { ...g, frota, operacao };
    });
    const plano = parPlanoDoItem(conf, copia.arquivos);
    const progresso = [];
    const fim = await new Promise((pronto) => {
      const fila = parCriarFila({
        criarWorker: () => new Worker('paralelismo-worker.js'),
        buscarBase: async (operacao, cod_faz) => bases[`${operacao}|${cod_faz}`] || bases['*'],
        aoMudar: (itens) => {
          const i = itens[0];
          if (i.estado === 'processando') progresso.push([i.fase, i.fazenda, i.pct, i.pct_item]);
          if (i.estado === 'pronto' || i.estado === 'erro') pronto(i);
        },
      });
      fila.adicionar({ id, plano });
    });
    const t = (performance.now() - inicio) / 1000;
    const fazendas = (fim.resultado ? fim.resultado.fazendas : []).map((f) => ({ ...f, shapefile: btoa(String.fromCharCode(...f.shapefile)) }));
    return { id, copia, plano, progresso, estado: fim.estado, erro: fim.erro, segundos: t, copiaS, pulados: fim.resultado && fim.resultado.pulados, parciais: fim.resultado && fim.resultado.parciais, fazendas };
  },
};
"""
FC_VAZIA = {'type': 'FeatureCollection', 'features': []}
BASE_VAZIA = {'analise_id': None, 'linhas': [], 'talhoes': FC_VAZIA}


def _pagina(ctx, url):
    pag = ctx.new_page()
    pag.goto(f'{url}/bancada.html')
    for s in ('paralelismo-puro.js', 'paralelismo-fila.js'):
        pag.add_script_tag(url=f'/{s}')
    pag.add_script_tag(content=AJUDANTES)
    return pag


def perto(a, b, tol):
    return abs(a - b) <= tol


def compara_analise(nome, web, nat):
    for k in ('pll_total', 'pll_aderentes', 'amostras', 'aderentes', 'acima', 'abaixo', 'fora_talhao', 'mes', 'linhas_usadas', 'frotas'):
        confere(web[k] == nat[k], f'{nome}: {k} = {nat[k] if k != "frotas" else "igual"}' + ('' if web[k] == nat[k] else f' (navegador deu {web[k]})'))
    sem_media = lambda ts: [{k: v for k, v in t.items() if k != 'media_m'} for t in ts]
    confere(sem_media(web['talhoes']) == sem_media(nat['talhoes']), f'{nome}: {len(nat["talhoes"])} talhões com as mesmas contagens')
    confere(all(perto(a['media_m'], b['media_m'], 0.0011) for a, b in zip(web['talhoes'], nat['talhoes'])), f'{nome}: média por talhão')
    pts_ok = len(web['pontos']) == len(nat['pontos']) and all(
        all(perto(p[i], q[i], 1e-6) for i in range(4)) and perto(p[4], q[4], 0.0011) and p[5:] == q[5:]
        for p, q in zip(web['pontos'], nat['pontos']))
    confere(pts_ok, f'{nome}: {len(nat["pontos"])} amostras no mesmo lugar (menos de 1 µm) e na mesma classe')


def compara_linhas(nome, web, nat):
    ok = len(web) == len(nat) and all(
        a['frota'] == b['frota'] and a['data'] == b['data'] and len(a['coords']) == len(b['coords'])
        and all(perto(p[0], q[0], 1e-6) and perto(p[1], q[1], 1e-6) for p, q in zip(a['coords'], b['coords']))
        for a, b in zip(web, nat))
    confere(ok, f'{nome}: {len(nat)} linhas iguais às do Python')


def nativo(lotes, frota, data):
    """Sem navegador.py: o mesmo caminho de test_regressao.py."""
    pontos = [p for lote in lotes for p in para_utm(lote)]
    return [{'frota': frota, 'data': data, 'coords': [list(c) for c in g.coords]} for g in linhas_do_grupo(pontos)]


def talhoes_de_bbox(pontos):
    """Dois talhões inventados sobre os pontos, deixando parte de fora: exercita talhão, fora_talhao e a conversão."""
    lats, lons = [p[0] for p in pontos], [p[1] for p in pontos]
    meio = statistics.median(lons)
    s, n, o, l = min(lats) - 0.001, max(lats) + 0.001, min(lons) - 0.001, max(lons) + 0.001
    quadro = lambda oe, le, sul, norte: [[[round(oe, 6), round(sul, 6)], [round(le, 6), round(sul, 6)], [round(le, 6), round(norte, 6)], [round(oe, 6), round(norte, 6)], [round(oe, 6), round(sul, 6)]]]
    feature = lambda num, coords: {'type': 'Feature', 'properties': {'talhao': num, 'area_ha': 1, 'declividade': None}, 'geometry': {'type': 'Polygon', 'coordinates': coords}}
    return {'type': 'FeatureCollection', 'features': [feature(1, quadro(o, meio, s, n)), feature(2, quadro(meio, l, (s + n) / 2, n))]}


def confere_shapefile(nome, b64, n_amostras, n_linhas, prefixo):
    z = zipfile.ZipFile(io.BytesIO(base64.b64decode(b64)))
    ler = lambda sufixo: shapefile.Reader(shp=io.BytesIO(z.read(f'{prefixo}_{sufixo}.shp')), shx=io.BytesIO(z.read(f'{prefixo}_{sufixo}.shx')), dbf=io.BytesIO(z.read(f'{prefixo}_{sufixo}.dbf')))
    confere(len(ler('Amostras')) == n_amostras and len(ler('Linhas')) == n_linhas, f'{nome}: shapefile com {n_amostras} amostras e {n_linhas} linhas')


def confere_progresso(nome, r):
    pcts = [p[3] for p in r['progresso']]
    confere(pcts == sorted(pcts) and {p[0] for p in r['progresso']} >= {'lendo', 'analise'}, f'{nome}: progresso só sobe e passa pelas fases')


# ── Pasta sintética, pelo <input webkitdirectory> ─────────────────────────
def passada_jdl(deslocamento, ticks=400):
    """Passada diagonal de ~1,4 m por tick, com o trabalho ligado desde o início."""
    delta = 10_000  # 1e-5 grau por tick
    lat, lon = -22.0 + deslocamento * 2e-5, -48.0 - deslocamento * 2e-5
    return registro_jdl(1000, campo_int(5, ticks * 200), [item_estado(1000, 1), item_rico(lat, lon, [delta] * ticks)])


def sessao_gs3(deslocamento, registros=400):
    """(.fdl, .fdd) com uma passada na antena 5140, ~1,4 m por registro, gravação ligada."""
    lat, lon = -22.0 + deslocamento * 2e-5, -48.0 - deslocamento * 2e-5
    catalogo = (struct.pack('<H', 5) + coluna_numerica('GPSLatitude_5140', lat)
                + coluna_numerica('GPSLongitude_5140', lon) + coluna_numerica('GPSLatitude_5141', -23.0)
                + coluna_numerica('GPSLongitude_5141', -49.0) + coluna_estado('Section1_State'))
    # O comentário faz cada .fdl ter SHA-256 próprio, como numa sessão real; iguais contariam como repetidos.
    return f'{FDL}<!-- sessao {deslocamento} -->', b'\xff\xff' + catalogo + registro_gs3(0) * registros


def cenario_sintetico(ctx, url):
    print('\n— Pasta sintética (.jdl e GS3), com um arquivo corrompido e um mapa de cobertura')
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / 'pen' / 'JD-Data' / 'log' / '2026_U_99999Rev0'
        log.mkdir(parents=True)
        for i in range(3):
            (log / f'2026_10_10_{i}.jdl').write_bytes(passada_jdl(i))
        (log / '2026_10_10_z_ruim.jdl').write_bytes(b'isto nao e um jdl')
        (log / 'mapa.pth').write_bytes(b'x')
        (log / 'leiame.txt').write_bytes(b'x')
        doc = Path(tmp) / 'pen' / '90002' / 'GS3_2630' / '90002' / 'RCD' / 'EIC' / 'Documentation' / 'F8'
        doc.mkdir(parents=True)
        for i in range(3):
            fdl, fdd = sessao_gs3(i)
            (doc / f's{i}.fdl').write_text(fdl, encoding='latin-1')
            (doc / f's{i}.fdd').write_bytes(fdd)

        lotes_jdl = [ler_jdl(str(log / f'2026_10_10_{i}.jdl'))[0] for i in range(3)]
        linhas_jdl = nativo(lotes_jdl, '90001', '2026-10-10')
        nat_jdl = analisar_fazenda(linhas_jdl, {})
        lotes_gs3 = [ler_gs3(str(doc / f's{i}.fdl'))[0] for i in range(3)]
        linhas_gs3 = nativo(lotes_gs3, '90002', '2026-10-10')
        nat_gs3 = analisar_fazenda(linhas_gs3, {})

        pag = _pagina(ctx, url)
        pag.set_input_files('#pasta', str(Path(tmp) / 'pen'))
        r = pag.evaluate("""async (base) => {
            const files = document.getElementById('pasta').files;
            return parTeste.rodar(files, (g) => (g.tipo === 'jdl' ? ['90001', 'torta'] : ['90002', 'cana']), { '*': base });
        }""", BASE_VAZIA)
    confere(r['estado'] == 'pronto', f'sintético: processou ({r["segundos"]:.1f} s, com preparo do Pyodide); erro: {r["erro"]}')
    confere(all(a['caminho'].startswith('pen/') for a in r['copia']['arquivos']), 'sintético: caminho real do webkitRelativePath')
    confere(len(r['copia']['arquivos']) == 10 and [m['caminho'].split('/')[-1] for m in r['copia']['mapas']] == ['mapa.pth'], 'sintético: copiou .jdl, .fdl e .fdd; o .pth entra pelo nome; o .txt fica de fora')
    confere(r['pulados'] == [{'caminho': 'pen/JD-Data/log/2026_U_99999Rev0/2026_10_10_z_ruim.jdl', 'motivo': 'ilegivel'}], f'sintético: o corrompido foi pulado e listado ({r["pulados"]})')
    confere(nat_jdl['pll_total'] > 0 and nat_gs3['pll_total'] > 0, f'sintético: o Python nativo gera amostras (.jdl {nat_jdl["pll_total"]}, GS3 {nat_gs3["pll_total"]})')
    por_op = {f['operacao']: f for f in r['fazendas']}
    confere(set(por_op) == {'torta', 'cana'} and {f['cod_faz'] for f in r['fazendas']} == {99999}, 'sintético: a mesma fazenda em duas operações sai em duas análises')
    if len(por_op) == 2:
        f = por_op['torta']
        confere(f['base_analise_id'] is None, 'sintético: fazenda nova sem análise de base')
        compara_linhas('sintético .jdl', f['linhas_novas'], linhas_jdl)
        compara_analise('sintético .jdl', f['analise'], json.loads(json.dumps(nat_jdl)))
        confere_shapefile('sintético .jdl', f['shapefile'], nat_jdl['pll_total'], len(linhas_jdl), 'torta_99999')
        confere(f['frotas_leitura'] == [{'frota': '90001', 'duracao_total_s': 240.0, 'duracao_trabalho_s': 240.0, 'sem_trabalho': False}], f'sintético .jdl: durações ({f["frotas_leitura"]})')
        f = por_op['cana']
        compara_linhas('sintético GS3', f['linhas_novas'], linhas_gs3)
        compara_analise('sintético GS3', f['analise'], json.loads(json.dumps(nat_gs3)))
    confere_progresso('sintético', r)
    pag.evaluate('id => parOpfsDescartar(id)', r['id'])
    pag.close()


# ── Amostras reais: ficam fora do git; nada aqui as grava no repositório ──
def cenario_amostras(ctx, url):
    print('\n— Amostras reais (tests/dados/paralelismo), comparadas com o Python nativo')
    jdl, fdl = AMOSTRAS / 'amostra.jdl', AMOSTRAS / 'amostra.fdl'
    pontos_jdl, ticks_jdl = ler_jdl(str(jdl))
    pontos_gs3, registros_gs3 = ler_gs3(str(fdl))
    sessao = ler_sessao(str(fdl))
    data_gs3 = sessao['inicio'][:10]
    linhas_jdl = nativo([pontos_jdl], '90001', '2026-08-23')
    linhas_gs3 = nativo([pontos_gs3], '90002', data_gs3)
    fc_jdl, fc_gs3 = talhoes_de_bbox(pontos_jdl), talhoes_de_bbox(pontos_gs3)
    nat_jdl = json.loads(json.dumps(analisar_fazenda(linhas_jdl, talhoes_de_geojson(fc_jdl))))
    nat_gs3 = json.loads(json.dumps(analisar_fazenda(linhas_gs3, talhoes_de_geojson(fc_gs3))))
    cod_gs3 = int(re.search(r'\d{5}', sessao['fazenda']).group())

    pag = _pagina(ctx, url)
    pedidos_py.clear()
    r = pag.evaluate("""async ({ bases }) => {
        const files = await Promise.all([
          parTeste.arquivo('/amostras/amostra.jdl', 'pen/90001/JD-Data/log/2026_U_99991Rev0/2026_08_23_[16_29]_{x}.jdl'),
          parTeste.arquivo('/amostras/amostra.fdl', 'pen/90002/GS3_2630/90002/RCD/EIC/Documentation/F8/s.fdl'),
          parTeste.arquivo('/amostras/amostra.fdd', 'pen/90002/GS3_2630/90002/RCD/EIC/Documentation/F8/s.fdd'),
        ]);
        return parTeste.rodar(files, (g) => (g.tipo === 'jdl' ? ['90001', 'torta'] : ['90002', 'cana']), bases);
    }""", {'bases': {'torta|99991': {'analise_id': 7, 'linhas': [], 'talhoes': fc_jdl}, f'cana|{cod_gs3}': {'analise_id': None, 'linhas': [], 'talhoes': fc_gs3}}})
    confere(r['estado'] == 'pronto', f'amostras: processou em {r["segundos"]:.1f} s; cópia {r["copiaS"]:.2f} s; erro: {r["erro"]}')
    confere(r['pulados'] == [], 'amostras: nada pulado')
    por_op = {f['operacao']: f for f in r['fazendas']}
    if 'torta' in por_op:
        f = por_op['torta']
        confere((f['cod_faz'], f['base_analise_id']) == (99991, 7), 'amostras .jdl: fazenda e base_analise_id')
        compara_linhas('amostras .jdl', f['linhas_novas'], linhas_jdl)
        compara_analise('amostras .jdl', f['analise'], nat_jdl)
        confere_shapefile('amostras .jdl', f['shapefile'], nat_jdl['pll_total'], len(linhas_jdl), 'torta_99991')
        leitura = f['frotas_leitura'][0]
        confere(perto(leitura['duracao_total_s'], ticks_jdl * 0.2, 1e-6) and perto(leitura['duracao_trabalho_s'], len(pontos_jdl) * 0.2, 1e-6), f'amostras .jdl: {ticks_jdl} ticks e {len(pontos_jdl)} pontos lidos no navegador')
        print(f'  .jdl: {nat_jdl["pll_total"]} amostras, {nat_jdl["pll_aderentes"]} aderentes, {nat_jdl["fora_talhao"]} fora de talhão, {len(linhas_jdl)} linhas')
    if 'cana' in por_op:
        f = por_op['cana']
        confere(f['cod_faz'] == cod_gs3, 'amostras GS3: fazenda do .fdl')
        compara_linhas('amostras GS3', f['linhas_novas'], linhas_gs3)
        compara_analise('amostras GS3', f['analise'], nat_gs3)
        leitura = f['frotas_leitura'][0]
        confere((leitura['duracao_total_s'], leitura['duracao_trabalho_s']) == (float(registros_gs3), float(len(pontos_gs3))), f'amostras GS3: {registros_gs3} registros e {len(pontos_gs3)} pontos lidos no navegador')
        print(f'  GS3: {nat_gs3["pll_total"]} amostras, {len(linhas_gs3)} linhas (uma sessão só; as amostras não saem daqui, e sim do cenário sintético)')
    confere(pedidos_py and all(p == 'manifest.json' or p.startswith('paralelismo/') for p in pedidos_py), 'manifesto: o Worker baixou só os arquivos do paralelismo')
    confere_progresso('amostras', r)
    pag.evaluate('id => parOpfsDescartar(id)', r['id'])

    print('\n— Linhas vigentes iguais às novas: a mescla não duplica')
    arredondadas = [{**l, 'coords': [[round(c, 9) for c in p] for p in l['coords']]} for l in linhas_jdl]
    r = pag.evaluate("""async ({ base }) => {
        const f = await parTeste.arquivo('/amostras/amostra.jdl', 'pen/90001/JD-Data/log/2026_U_99991Rev0/2026_08_23_a.jdl');
        return parTeste.rodar([f], () => ['90001', 'torta'], { '*': base });
    }""", {'base': {'analise_id': 7, 'linhas': arredondadas, 'talhoes': fc_jdl}})
    a = r['fazendas'][0]['analise'] if r['fazendas'] else {}
    confere(a.get('pll_total') == nat_jdl['pll_total'] and a.get('linhas_usadas') == nat_jdl['linhas_usadas'], f'mescla: mesmo total ({a.get("pll_total")}) com vigentes = novas')
    pag.evaluate('id => parOpfsDescartar(id)', r['id'])
    pag.close()


# ── Página fechada no meio ────────────────────────────────────────────────
def cenario_sobras(ctx, url):
    print('\n— Sobras no OPFS: página fechada no meio')
    a, b = _pagina(ctx, url), _pagina(ctx, url)
    id_ = a.evaluate("""async () => {
        const f = new File([new Uint8Array(1000)], 'x.jdl');
        const id = crypto.randomUUID();
        await parOpfsCopiar(id, [f]);
        return id;
    }""")
    confere(b.evaluate('parOpfsSobras()') == [], 'sobras: outra aba não vê como sobra a cópia em uso')
    a.close()
    fim = time.time() + 10
    sobras = []
    while time.time() < fim and not sobras:
        sobras = b.evaluate('parOpfsSobras()')
        time.sleep(0.2)
    confere([(s['id'], s['arquivos'], s['bytes']) for s in sobras] == [(id_, 1, 1000)], 'sobras: fechada a aba, a cópia aparece para descartar')
    b.evaluate('id => parOpfsDescartar(id)', id_)
    confere(b.evaluate('parOpfsSobras()') == [], 'sobras: descartada, some')
    b.close()


# ── Corretivos com o manifesto novo ───────────────────────────────────────
def cenario_corretivos(ctx, url):
    print('\n— Corretivos com o manifesto por módulo')
    pag = ctx.new_page()
    pag.goto(f'{url}/bancada.html')
    pag.add_script_tag(url='/corretivos-pdf.js')
    pedidos_py.clear()
    erro = pag.evaluate("""async () => { try { await crGerador.preparar(); return null; } catch (e) { return String(e); } }""")
    confere(erro is None, f'Corretivos: gerador de PDF prepara ({erro})')
    confere(pedidos_py and not any(p.startswith('paralelismo/') for p in pedidos_py) and 'mapas/corretivo_pdf.py' in pedidos_py, 'manifesto: o Corretivos baixou só os arquivos dele')
    pag.close()


# ── Pyodide inacessível: spec §10 ─────────────────────────────────────────
def cenario_sem_pyodide(navegador, url):
    print('\n— Pyodide inacessível')
    ctx = navegador.new_context()
    ctx.route('**/cdn.jsdelivr.net/**', lambda rota: rota.abort())
    pag = _pagina(ctx, url)
    r = pag.evaluate("""async (base) => {
        const f = new File([new Uint8Array(10)], '2026_10_10_a.jdl');
        Object.defineProperty(f, 'webkitRelativePath', { value: 'pen/log/2026_U_99999Rev0/2026_10_10_a.jdl' });
        return parTeste.rodar([f], () => ['90001', 'torta'], { '*': base });
    }""", BASE_VAZIA)
    confere(r['estado'] == 'erro' and r['erro'] == 'Não foi possível preparar a análise; recarregue a página', f'sem Pyodide: texto da spec ({r["erro"]})')
    pag.evaluate('id => parOpfsDescartar(id)', r['id'])
    ctx.close()


# ── Dois itens na mesma fila, com o Worker de verdade ─────────────────────
def cenario_dois_itens(ctx, url):
    print('\n— Dois pen-drives na mesma fila: um por vez, o Pyodide é preparado uma vez só')
    linhas = nativo([ler_jdl_bytes(passada_jdl(i)) for i in range(3)], '90001', '2026-10-10')
    nat = analisar_fazenda(linhas, {})
    arquivos = [base64.b64encode(passada_jdl(i)).decode() for i in range(3)]
    pag = _pagina(ctx, url)
    pedidos_py.clear()
    r = pag.evaluate("""async ({ arquivos, base }) => {
        const copiar = async (id, cod) => {
          const files = arquivos.map((b64, i) => {
            const f = new File([Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))], `2026_10_10_${i}.jdl`);
            Object.defineProperty(f, 'webkitRelativePath', { value: `pen/log/2026_U_${cod}Rev0/2026_10_10_${i}.jdl` });
            return f;
          });
          const { arquivos: copiados } = await parOpfsCopiar(id, files);
          const conf = parConferencia(copiados, [], []).map((g) => ({ ...g, frota: '90001', operacao: 'torta' }));
          return parPlanoDoItem(conf, copiados);
        };
        const ordem = [];
        const planos = { a: await copiar('a', 99998), b: await copiar('b', 99999) };
        const itens = await new Promise((pronto) => {
          const fila = parCriarFila({
            criarWorker: () => new Worker('paralelismo-worker.js'),
            buscarBase: async () => base,
            aoMudar: (lista) => {
              ordem.push(lista.map((i) => i.estado).join(','));
              if (lista.length === 2 && lista.every((i) => i.estado === 'pronto' || i.estado === 'erro')) pronto(lista);
            },
          });
          fila.adicionar({ id: 'a', plano: planos.a });
          fila.adicionar({ id: 'b', plano: planos.b });
        });
        await parOpfsDescartar('a');
        await parOpfsDescartar('b');
        return { ordem, totais: itens.map((i) => i.estado === 'pronto' ? i.resultado.fazendas[0].analise.pll_total : i.erro) };
    }""", {'arquivos': arquivos, 'base': BASE_VAZIA})
    confere(r['totais'] == [nat['pll_total']] * 2, f'dois itens: os dois dão {nat["pll_total"]} amostras ({r["totais"]})')
    confere(not any(e.count('processando') > 1 for e in r['ordem']), 'dois itens: nunca dois processando ao mesmo tempo')
    confere(pedidos_py.count('manifest.json') == 1, f'dois itens: manifesto baixado {pedidos_py.count("manifest.json")} vez (um Worker só)')
    pag.close()


# ── O que não pode mudar número sem avisar ────────────────────────────────
def cenario_falhas(ctx, url):
    print('\n— Arquivo cortado, sem data, cópia que sumiu do OPFS e mensagem inválida')
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / 'pen' / 'log' / '2026_U_99997Rev0'
        log.mkdir(parents=True)
        # Nome sem o prefixo AAAA_MM_DD: a data vem nula, e o null do JS passa pela ponte do Pyodide.
        for i in range(3):
            (log / f'p{i}.jdl').write_bytes(passada_jdl(i))
        # Dois registros, com o corte no segundo: o primeiro continua valendo. Num registro só, nada sobra (e é ilegível).
        (log / 'p3_cortado.jdl').write_bytes(passada_jdl(3) + passada_jdl(3, ticks=50)[:-1])
        lotes = [ler_jdl(str(log / nome))[0] for nome in ('p0.jdl', 'p1.jdl', 'p2.jdl', 'p3_cortado.jdl')]
        linhas = nativo(lotes, '90001', None)
        nat = json.loads(json.dumps(analisar_fazenda(linhas, {})))
        pag = _pagina(ctx, url)
        pag.set_input_files('#pasta', str(Path(tmp) / 'pen'))
        r = pag.evaluate("""async (base) => parTeste.rodar(document.getElementById('pasta').files, () => ['90001', 'torta'], { '*': base })""", BASE_VAZIA)
    confere(r['estado'] == 'pronto', f'cortado e sem data: processou; erro: {r["erro"]}')
    confere(r['parciais'] == [{'caminho': 'pen/log/2026_U_99997Rev0/p3_cortado.jdl'}] and r['pulados'] == [], f'cortado: listado como parcial ({r["parciais"]}, {r["pulados"]})')
    if r['fazendas']:
        f = r['fazendas'][0]
        compara_linhas('sem data', f['linhas_novas'], linhas)
        compara_analise('sem data', f['analise'], nat)
        confere(all(l['data'] is None for l in f['linhas_novas']) and f['analise']['mes'] is None, 'sem data: linhas com data nula e sem mês')
    pag.evaluate('id => parOpfsDescartar(id)', r['id'])

    r = pag.evaluate("""async (base) => {
        const id = crypto.randomUUID();
        const f = new File([new Uint8Array(10)], 'a.jdl');
        const { arquivos } = await parOpfsCopiar(id, [f]);
        const plano = { pulados: [], fazendas: [{ operacao: 'torta', cod_faz: 99999, grupos: [{ frota: '90001', arquivos: [
          { tipo: 'jdl', caminho: 'a.jdl', opfs: arquivos[0].opfs, opfs_fdd: null, data: null, bytes: 10 }] }] }] };
        await parOpfsDescartar(id);  // o navegador pode evacuar o OPFS: não pode virar "pronto" com número menor
        return new Promise((pronto) => {
          parCriarFila({
            criarWorker: () => new Worker('paralelismo-worker.js'),
            buscarBase: async () => base,
            aoMudar: (itens) => { if (['pronto', 'erro'].includes(itens[0].estado)) pronto(itens[0]); },
          }).adicionar({ id, plano });
        }).then((i) => [i.estado, i.erro]);
    }""", BASE_VAZIA)
    confere(r == ['erro', 'Não foi possível analisar a fazenda 99999; tente de novo'], f'cópia sumiu do OPFS: erro do item, que pode ser refeito ({r})')

    r = pag.evaluate("""() => new Promise((pronto) => {
        const w = new Worker('paralelismo-worker.js');
        w.onmessage = (e) => { if (e.data.tipo === 'erro') { w.terminate(); pronto(e.data.id); } };
        w.postMessage({ tipo: 'processar', item: { id: 'x' } });
        setTimeout(() => pronto('travou'), 120000);
    })""")
    confere(r == 'x', f'mensagem inválida: o Worker responde erro em vez de travar a fila ({r})')
    pag.close()


def ler_jdl_bytes(dados):
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / 'a.jdl'
        f.write_bytes(dados)
        return ler_jdl(str(f))[0]


def main():
    with tempfile.TemporaryDirectory() as py_dir:
        publicar(py_dir)
        servidor = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Servidor, py_dir=py_dir))
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{servidor.server_address[1]}'
        with sync_playwright() as p:
            navegador = p.chromium.launch(channel='msedge', headless=True)
            ctx = navegador.new_context()
            cenario_sintetico(ctx, url)
            if all((AMOSTRAS / f'amostra.{e}').exists() for e in ('jdl', 'fdl', 'fdd')):
                cenario_amostras(ctx, url)
            else:
                print('\n— Amostras reais ausentes: comparação pulada (ver tests/dados/paralelismo/LEIAME.md)')
            cenario_dois_itens(ctx, url)
            cenario_falhas(ctx, url)
            cenario_sobras(ctx, url)
            cenario_corretivos(ctx, url)
            cenario_sem_pyodide(navegador, url)
            navegador.close()
        servidor.shutdown()
    print(f'\n{"FALHOU: " + str(len(falhas)) if falhas else "Tudo certo"}')
    sys.exit(1 if falhas else 0)


if __name__ == '__main__':
    main()
