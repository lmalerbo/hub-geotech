"""PDF do mapa de aplicação de corretivos. Sempre A4 em pé.

Página 1, de cima para baixo: faixa da marca, MAPA em largura total (legenda das cores dentro dele), CARIMBO
numa faixa horizontal (identificação | totais por produto | escala/área/safra e norte) e TABELA
"APLICAÇÕES POR TALHÃO" com letra grande. Linhas que não cabem vão para as páginas seguintes.

Coordenadas da página em mm (origem no topo). Usa só as peças genéricas de mapas/layout.py (Pagina, eixo_mapa,
escala, moldura, norte, nova_pagina); a tabela, o carimbo e a legenda são locais, para não mexer no Drone."""
import datetime
import io
import json
import math
from pathlib import Path

import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch

from mapas.corretivo_dados import (
    CORES, OPERACOES, SEM_APLICACAO, area_total, chave_cor, faixas, linhas_tabela, lista_os, rotulo,
    totais_por_produto, _ordenadas,
)
from mapas.layout import (
    CINZA, GRAFITE, LINHA, MARCA, Pagina, br, caixa_norte, eixo_mapa, escala_grafica, escala_numerica,
    moldura_logo, nova_pagina, safra_de,
)

LOGO = Path(__file__).resolve().parent.parent / 'drone' / 'assets' / 'logo-pedra.png'
EPSG_UTM = 31983
W, H = 210, 297                  # A4 em pé, mm
M = 10                           # margem
LARG = W - 2 * M                 # largura útil: 190 mm
TOPO, BASE = 10, 274             # área do conteúdo (o rodapé fica em 278)
U = BASE - TOPO                  # altura útil: 264 mm
GAP = 4                          # espaço entre mapa, carimbo e tabela
MAPA_MIN = 0.45 * U              # o mapa nunca fica com menos de ~45% da altura útil
LETRA_LINHA = 14                 # letra das linhas da tabela
LINHA_TAB = 7.5                  # altura de cada linha da tabela
CAB_TAB = 11.2                   # do topo da tabela até a primeira linha (título + cabeçalho)
TOTAL_NOTA = 12.5                # linha de total + nota, no fim da tabela
TOPO_CONT = 18                   # topo da tabela nas páginas extras (depois do nome da fazenda)
CAP_EXTRA = int((BASE - TOPO_CONT - CAB_TAB) // LINHA_TAB)
LETRA_LEGENDA = 13
WA, WB, WC = 60, 84, 40          # blocos do carimbo (identificação | totais | escala/área/safra)
COLUNAS = [('TALHÃO', 2, 'left'), ('ÁREA (ha)', 42, 'right'), ('APLICAÇÃO', 52, 'left'),
           ('DOSE (t/ha)', 124, 'right'), ('TOTAL (t)', 148, 'right'), ('O.S.', 153, 'left')]
NOTA = '* área editada · ÁREA ha · DOSE t/ha · TOTAL t'


# ---------- dados ----------

def _gdf(dados) -> gpd.GeoDataFrame:
    gdf = gpd.GeoDataFrame.from_features(dados['talhoes_geo']['features'], crs='EPSG:4326')
    return gdf.to_crs(EPSG_UTM)


def _data(dados) -> datetime.date:
    return datetime.date.fromisoformat(str(dados['data'])[:10])


def _gerado_em(dados) -> datetime.date:
    """Data em que o PDF foi gerado (rodapé), como no Drone; sem ela, a data do mapa."""
    return datetime.date.fromisoformat(str(dados.get('gerado_em') or dados['data'])[:10])


def _aplicacoes_por_talhao(dados) -> dict:
    por_talhao: dict[int, list[dict]] = {}
    for a in _ordenadas(dados):
        for t in a['talhoes']:
            por_talhao.setdefault(int(t), []).append(a)
    return por_talhao


# ---------- medidas de texto (mm) ----------

def _largura(pg: Pagina, texto: str, tam: float, peso='normal') -> float:
    t = pg.fig.text(0, 0, texto, fontsize=tam, fontweight=peso)
    bb = t.get_window_extent(renderer=pg.fig.canvas.get_renderer())
    t.remove()
    return bb.width / pg.fig.dpi * 25.4


def _cortar(pg: Pagina, texto: str, max_mm: float, tam: float, peso='normal') -> str:
    """Corta o fim do texto com '…' até caber em max_mm."""
    if _largura(pg, texto, tam, peso) <= max_mm:
        return texto
    while len(texto) > 1 and _largura(pg, texto + '…', tam, peso) > max_mm:
        texto = texto[:-1]
    return texto.rstrip() + '…'


def _caber(pg: Pagina, texto: str, max_mm: float, tam: float, minimo: float, peso='normal'):
    """(texto, tamanho): reduz a letra até o mínimo; abaixo disso corta com '…'."""
    t = tam
    while t >= minimo - 1e-9:
        if _largura(pg, texto, t, peso) <= max_mm:
            return texto, t
        t -= 0.5
    return _cortar(pg, texto, max_mm, minimo, peso), minimo


def _linhas_titulo(pg: Pagina, texto: str, max_mm: float):
    """Título do carimbo: uma linha (12 a 9 pt) ou, se nem a 9 pt couber, duas linhas (9 pt, a 2ª cortada)."""
    for tam in (12, 11, 10, 9):
        if _largura(pg, texto, tam, 'bold') <= max_mm:
            return [(texto, tam)]
    palavras = texto.split(' ')
    l1 = ''
    i = 0
    while i < len(palavras):
        cand = (l1 + ' ' + palavras[i]).strip()
        if l1 and _largura(pg, cand, 9, 'bold') > max_mm:
            break
        l1 = cand
        i += 1
    resto = ' '.join(palavras[i:])
    if not resto:
        return [(l1, 9)]
    return [(l1, 9), (_cortar(pg, resto, max_mm, 9, 'bold'), 9)]


def _subtitulo(pg: Pagina, lista, max_mm: float):
    """'MAPA DE APLICAÇÃO · CORRETIVOS · O.S. …': reduz a letra até 4,8 pt; depois mostra menos O.S. ('… (+N)')."""
    base = 'MAPA DE APLICAÇÃO · CORRETIVOS · O.S. '
    n = len(lista)
    for tam in (5.5, 5.2, 4.8):
        for k in range(n, 0, -1):
            s = base + ', '.join(lista[:k]) + ('' if k == n else f', … (+{n - k})')
            if _largura(pg, s, tam) <= max_mm:
                return s, tam
    return _cortar(pg, base + (lista[0] if lista else ''), max_mm, 4.8), 4.8


# ---------- mapa ----------

def _mapa(pg: Pagina, dados, gdf, x, y, w, h) -> int:
    ax, s, x0, y0 = eixo_mapa(pg, gdf, x, y, w, h)
    por_talhao = _aplicacoes_por_talhao(dados)
    no_mapa = {int(k) for k in dados['areas']}
    pintados = []                                   # (geometria, número) de cada talhão com geometria
    for _, linha in gdf.iterrows():
        t = int(linha['talhao'])
        geom = linha.geometry
        if t not in no_mapa:                        # talhão da fazenda fora do mapa: branco com contorno
            gpd.GeoSeries([geom], crs=gdf.crs).plot(ax=ax, facecolor='white', edgecolor='none')
            continue
        aps = por_talhao.get(t, [])
        if not aps:
            gpd.GeoSeries([geom], crs=gdf.crs).plot(ax=ax, facecolor=SEM_APLICACAO, edgecolor='none')
        else:
            for parte, ap in zip(faixas(geom, len(aps)), aps):
                if parte.is_empty or parte.area == 0:
                    continue
                gpd.GeoSeries([parte], crs=gdf.crs).plot(ax=ax, facecolor=CORES[chave_cor(ap)],
                                                         edgecolor='none', alpha=0.92)
        pintados.append((geom, t))
    for _, linha in gdf.iterrows():                 # contornos por cima das pinturas
        gpd.GeoSeries([linha.geometry], crs=gdf.crs).plot(ax=ax, facecolor='none', edgecolor=GRAFITE,
                                                          linewidth=0.5)
    for geom, t in pintados:
        p = geom.representative_point()
        ax.text(p.x, p.y, str(t), fontsize=6.5, fontweight='semibold', color=GRAFITE, ha='center',
                va='center', path_effects=[pe.withStroke(linewidth=2, foreground='white')])
    escala_grafica(ax, s, x0, y0)
    moldura_logo(pg, x, y, w, h, LOGO)
    _legenda_mapa(pg, dados, x, y, w, h)
    return escala_numerica(s)


def _legenda_mapa(pg: Pagina, dados, x, y, w, h):
    """Caixa branca (alpha 0,9) no canto inferior direito do mapa: só os tipos usados; Blend é um item só."""
    rotulos: dict[str, str] = {}
    for a in _ordenadas(dados):                  # Blend Dolomítico e PH7 têm a mesma cor: um item só
        rotulos.setdefault(chave_cor(a), 'Blend' if a['tipo'] == 'blend' else rotulo(a))
    if not rotulos:
        return
    duas = any(len(aps) >= 2 for aps in _aplicacoes_por_talhao(dados).values())
    itens = [(CORES[c], t) for c, t in rotulos.items()] + ([(None, '◩ duas aplicações')] if duas else [])
    passo, pad, sw = 6.2, 2.5, 5.0
    larg = max(_largura(pg, t, LETRA_LEGENDA) for _, t in itens) + sw + 2.5
    bw = larg + 2 * pad
    bh = passo * len(itens) + 2 * pad - 1.2
    bx, by = x + w - bw - 2.5, y + h - bh - 2.5
    pg.fig.patches.append(FancyBboxPatch(
        (bx / pg.W, 1 - (by + bh) / pg.H), bw / pg.W, bh / pg.H, boxstyle='round,pad=0,rounding_size=0.0',
        transform=pg.fig.transFigure, facecolor='white', edgecolor=LINHA, linewidth=0.5, alpha=0.9))
    for i, (cor, texto) in enumerate(itens):
        yy = by + pad + i * passo + passo / 2
        if cor is None:
            pg.texto(bx + pad, yy, texto, LETRA_LEGENDA, CINZA, va='center')
        else:
            pg.ret(bx + pad, yy - 1.5, sw, 3, cor)
            pg.texto(bx + pad + sw + 2.5, yy, texto, LETRA_LEGENDA, GRAFITE, va='center')


# ---------- carimbo ----------

def _altura_carimbo(totais) -> float:
    rows = max(1, math.ceil(len(totais) / 3))
    return max(24.0, 19 + 18 * (rows - 1))


def _tamanho_titulos(pg: Pagina, titulos, max_mm: float) -> float:
    """Um tamanho só para todos os títulos dos quadros: 4,8 pt, reduzido (até 4,0) se algum não couber."""
    tam = 4.8
    for t in titulos:
        while tam > 4.0 and _largura(pg, t, tam, 'semibold') > max_mm:
            tam -= 0.1
    return round(tam, 1)


def _quadros(pg: Pagina, totais, x, y, w):
    gap = 2
    cw = (w - 4 - 2 * gap) / 3
    tam_titulo = _tamanho_titulos(pg, [q['titulo'] for q in totais], cw - 5)
    for idx, q in enumerate(totais):
        r, c = divmod(idx, 3)
        cx, cy = x + 2 + c * (cw + gap), y + 2 + r * 18
        destaque = idx == 0
        pg.caixa(cx, cy, cw, 15, '#b9dcc4' if destaque else LINHA, '#f1f8f3' if destaque else 'white')
        pg.texto(cx + 2.5, cy + 1.8, _cortar(pg, q['titulo'], cw - 5, tam_titulo, 'semibold'), tam_titulo,
                 CINZA, 'semibold')
        valor, t2 = _caber(pg, br(q['toneladas']), cw - 5 - 4, 12, 9, 'bold')
        pg.texto(cx + 2.5, cy + 5, valor, t2, MARCA if destaque else GRAFITE, 'bold')
        pg.texto(cx + cw - 2.5, cy + 6.8, 't', 5.5, CINZA, 'semibold', ha='right')
        if q['detalhe']:
            det, t3 = _caber(pg, q['detalhe'], cw - 5, 5, 4.0)
            pg.texto(cx + 2.5, cy + 11.2, det, t3, CINZA)


def _carimbo(pg: Pagina, dados, yb, hb, escala):
    totais = totais_por_produto(dados)
    pg.caixa(M, yb, LARG, hb, LINHA, 'white')
    xb, xc = M + WA + 3, M + WA + 3 + WB + 3
    for xs in (xb - 1.5, xc - 1.5):
        pg.ret(xs, yb + 2, 0.25, hb - 4, LINHA)
    # (a) identificação
    x = M + 3
    tag = f"CORRETIVO · {OPERACOES[dados['operacao']].upper()}"
    tag_txt, tt = _caber(pg, tag, WA - 10, 4.5, 4.0, 'bold')
    tag_w = _largura(pg, tag_txt, tt, 'bold') + 4
    pg.caixa(x, yb + 2.5, tag_w, 3.6, MARCA, MARCA, 0.5, 0.1)
    pg.texto(x + tag_w / 2, yb + 3.0, tag_txt, tt, 'white', 'bold', ha='center')
    y = yb + 7.5
    for texto, tam in _linhas_titulo(pg, f"{dados['cod_faz']} · {dados['nome']}", WA - 6):
        pg.texto(x, y, texto, tam, peso='bold')
        y += tam * 0.3528 * 1.2
    sub, ts = _subtitulo(pg, lista_os(dados), WA - 6)
    pg.texto(x, y + 0.8, sub, ts, CINZA)
    # (b) totais por produto
    _quadros(pg, totais, xb, yb, WB)
    # (c) escala / área / safra e norte
    celulas = [('ESCALA', f'1:{escala:,}'.replace(',', '.')),
               (f'ÁREA · {len(dados["areas"])} TALHÕES', f'{br(area_total(dados))} ha'),
               ('SAFRA', safra_de(_data(dados)))]
    largura_txt = WC - 3 - 10            # a seta do norte fica à direita, sem encostar no texto
    for i, (titulo, valor) in enumerate(celulas):
        cy = yb + 2 + i * 7.2
        pg.texto(xc + 2.5, cy + 0.3, _cortar(pg, titulo, largura_txt, 4.8, 'semibold'), 4.8, CINZA, 'semibold')
        pg.texto(xc + 2.5, cy + 3.2, _cortar(pg, valor, largura_txt, 7, 'semibold'), 7, GRAFITE, 'semibold')
    caixa_norte(pg, xc + WC - 5.5, yb + 3)


# ---------- tabela ----------

def _linha_tabela(pg: Pagina, yy: float, valores, bold=False, cor=GRAFITE):
    ultima = len(COLUNAS) - 1
    for i, (valor, (_, fx, ha)) in enumerate(zip(valores, COLUNAS)):
        if not valor:
            continue
        x = M + fx
        tam = LETRA_LINHA
        if i == ultima:                               # O.S.: reduz/corta para caber na coluna
            valor, tam = _caber(pg, valor, LARG - fx - 1, LETRA_LINHA, 9)
        pg.texto(x, yy + LINHA_TAB / 2, valor, tam, cor, 'bold' if bold else 'normal', ha=ha, va='center')


def _tabela(pg: Pagina, y, titulo, linhas, total):
    """Título, cabeçalho, linhas (zebradas) e, se total não for None, a linha de total e a nota.
    Devolve o y logo abaixo do que foi desenhado."""
    pg.texto(M, y, titulo, 12, GRAFITE, 'bold')
    for nome, fx, ha in COLUNAS:
        pg.texto(M + fx, y + 8.0, nome, 10, MARCA, 'bold', ha=ha, va='center')
    pg.ret(M, y + 10.4, LARG, 0.35, GRAFITE)
    yy = y + CAB_TAB
    for i, valores in enumerate(linhas):
        if i % 2:
            pg.ret(M, yy, LARG, LINHA_TAB, '#f4f6f5')
        _linha_tabela(pg, yy, valores)
        yy += LINHA_TAB
    if total is not None:
        pg.ret(M, yy + 0.3, LARG, 0.35, GRAFITE)
        _linha_tabela(pg, yy + 0.3, total, bold=True)
        yy += LINHA_TAB + 0.3
        pg.texto(M, yy + 1.5, NOTA, 6, CINZA)
        yy += 4
    return yy


def _paginar(linhas: list, hb: float) -> list:
    """Intervalos (ini, fim) de linhas por página. Quebra só entre talhões (a linha de um talhão nunca se
    separa); só um talhão maior que a página é partido, e a página seguinte repete o número dele.
    Página 1 tem o mapa (>= 45% da altura útil); o total e a nota ficam na última página."""
    n = len(linhas)
    if n == 0:
        return [(0, 0)]
    tab_max = U - 2 * GAP - hb - MAPA_MIN
    cap1 = int((tab_max - CAB_TAB) // LINHA_TAB)
    last1 = int((tab_max - CAB_TAB - TOTAL_NOTA) // LINHA_TAB)
    capx = CAP_EXTRA
    lastx = int((BASE - TOPO_CONT - CAB_TAB - TOTAL_NOTA) // LINHA_TAB)
    inicios = {i for i, linha in enumerate(linhas) if linha[0] != ''}
    paginas, pos, primeira = [], 0, True
    while True:
        cap, last = (cap1, last1) if primeira else (capx, lastx)
        if n - pos <= last:
            paginas.append((pos, n))
            return paginas
        fim = None
        for e in range(min(pos + cap, n - 1), pos, -1):
            if e in inicios:
                fim = e
                break
        if fim is None:                            # talhão maior que a página: parte
            fim = max(pos + 1, min(pos + cap, n - 1))
        paginas.append((pos, fim))
        pos, primeira = fim, False


def _recortar(linhas: list, ini: int, fim: int) -> list:
    """Linhas de uma página; se a página começa no meio de um talhão, repete o número e a área dele."""
    rows = [list(r) for r in linhas[ini:fim]]
    if rows and ini > 0 and rows[0][0] == '':
        k = max(j for j in range(ini) if linhas[j][0] != '')
        rows[0] = [linhas[k][0], linhas[k][1]] + rows[0][2:]
    return rows


def _rodape(pg: Pagina, dados, k: int, n: int):
    pg.ret(M, 278, LARG, 0.2, LINHA)
    pg.texto(M, 279.2, 'Pedra Agroindustrial S/A · Geotecnologia', 4.8, CINZA)
    pg.texto(W - M, 279.2, f"Gerado em {_gerado_em(dados):%d/%m/%Y} por {dados.get('gerado_por', '')}",
             4.8, CINZA, ha='right')
    if n > 1:
        pg.texto(W / 2, 279.2, f'Página {k} de {n}', 4.8, CINZA, ha='center')


def _cabecalho_extra(pg: Pagina, dados):
    pg.texto(M, TOPO, f"{dados['cod_faz']} · {dados['nome']}", 12, GRAFITE, 'bold')


# ---------- PDF ----------

def gerar_pdf(dados: dict, destino) -> str:
    gdf = _gdf(dados)
    totais = totais_por_produto(dados)
    linhas = linhas_tabela(dados)
    total = ['Total', br(area_total(dados)), '', '', '', '']
    hb = _altura_carimbo(totais)
    intervalos = _paginar(linhas, hb)
    n_paginas = len(intervalos)
    so_p1 = n_paginas == 1
    h_tab1 = CAB_TAB + (intervalos[0][1] - intervalos[0][0]) * LINHA_TAB + (TOTAL_NOTA if so_p1 else 0)
    h_mapa = U - 2 * GAP - hb - h_tab1

    pg = nova_pagina(W, H)
    escala = _mapa(pg, dados, gdf, M, TOPO, LARG, h_mapa)
    yb = TOPO + h_mapa + GAP
    _carimbo(pg, dados, yb, hb, escala)
    y_tab = yb + hb + GAP
    _tabela(pg, y_tab, 'APLICAÇÕES POR TALHÃO', _recortar(linhas, *intervalos[0]), total if so_p1 else None)
    _rodape(pg, dados, 1, n_paginas)

    with PdfPages(destino) as pdf:
        pdf.savefig(pg.fig)
        plt.close(pg.fig)
        for k, (ini, fim) in enumerate(intervalos[1:], start=2):
            pg = nova_pagina(W, H)
            _cabecalho_extra(pg, dados)
            ultima = k == n_paginas
            _tabela(pg, TOPO_CONT, 'APLICAÇÕES POR TALHÃO (continuação)', _recortar(linhas, ini, fim),
                    total if ultima else None)
            _rodape(pg, dados, k, n_paginas)
            pdf.savefig(pg.fig)
            plt.close(pg.fig)
    return 'retrato'


def gerar_bytes(json_texto: str) -> bytes:
    buffer = io.BytesIO()
    gerar_pdf(json.loads(json_texto), buffer)
    return buffer.getvalue()
