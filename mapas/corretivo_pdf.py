"""PDF do mapa de aplicação de corretivos. A4 na orientação da fazenda (todas as folhas iguais).

Fazenda em pé (retrato), página 1 de cima para baixo: MAPA em largura total (legenda das cores dentro dele),
CARIMBO numa faixa horizontal (identificação | totais por produto | escala/área/safra e norte) e TABELA
"APLICAÇÕES POR TALHÃO" com letra grande. Linhas que não cabem vão para as páginas seguintes.
Fazenda larga (paisagem): folha 1 só com MAPA e CARIMBO; a TABELA, com a mesma letra grande, da folha 2 em diante.

Coordenadas da página em mm (origem no topo). Usa só as peças genéricas de mapas/layout.py (Pagina, eixo_mapa,
escala, moldura, norte, nova_pagina); a tabela, o carimbo e a legenda são locais, para não mexer no Drone."""
import datetime
import io
import json
import math
from dataclasses import dataclass
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
    moldura_logo, nova_pagina, orientacao, safra_de,
)

LOGO = Path(__file__).resolve().parent.parent / 'drone' / 'assets' / 'logo-pedra.png'
EPSG_UTM = 31983
M = 10                           # margem
TOPO = 10                        # topo do conteúdo
GAP = 4                          # espaço entre mapa, carimbo e tabela
LETRA_LINHA = 14                 # letra das linhas da tabela
LINHA_TAB = 7.5                  # altura de cada linha da tabela
CAB_TAB = 11.2                   # do topo da tabela até a primeira linha (título + cabeçalho)
TOTAL_NOTA = 12.5                # linha de total + nota, no fim da tabela
TOPO_CONT = 18                   # topo da tabela nas páginas só de tabela (depois do nome da fazenda)
LETRA_LEGENDA = 13
WA, WC = 60, 40                  # blocos do carimbo: identificação | totais (o resto) | escala/área/safra
LARG_RETRATO = 190               # as colunas abaixo são para 190 mm; em paisagem se espalham na proporção
COLUNAS = [('TALHÃO', 2, 'left'), ('ÁREA (ha)', 42, 'right'), ('APLICAÇÃO', 52, 'left'),
           ('DOSE (t/ha)', 124, 'right'), ('TOTAL (t)', 148, 'right'), ('O.S.', 153, 'left')]
NOTA = '* área editada · ÁREA ha · DOSE t/ha · TOTAL t'


@dataclass(frozen=True)
class Folha:
    """Medidas (mm) de uma folha A4 em pé (210 × 297) ou deitada (297 × 210)."""
    W: float
    H: float

    @property
    def paisagem(self) -> bool: return self.W > self.H
    @property
    def larg(self) -> float: return self.W - 2 * M              # largura útil
    @property
    def base(self) -> float: return self.H - 23                  # fim do conteúdo (o rodapé fica em H − 19)
    @property
    def u(self) -> float: return self.base - TOPO                # altura útil
    @property
    def wb(self) -> float: return self.larg - WA - WC - 6        # bloco dos totais no carimbo
    @property
    def por_linha(self) -> int: return 5 if self.paisagem else 3  # quadros de totais por linha do carimbo
    @property
    def cap_tabela(self) -> int:                                 # linhas numa página só de tabela
        return int((self.base - TOPO_CONT - CAB_TAB) // LINHA_TAB)

    def col(self, fx: float) -> float:
        return M + fx * self.larg / LARG_RETRATO


RETRATO, PAISAGEM = Folha(210, 297), Folha(297, 210)


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

def _altura_carimbo(f: Folha, totais) -> float:
    rows = max(1, math.ceil(len(totais) / f.por_linha))
    return max(24.0, 19 + 18 * (rows - 1))


def _tamanho_titulos(pg: Pagina, titulos, max_mm: float) -> float:
    """Um tamanho só para todos os títulos dos quadros: 4,8 pt, reduzido (até 4,0) se algum não couber."""
    tam = 4.8
    for t in titulos:
        while tam > 4.0 and _largura(pg, t, tam, 'semibold') > max_mm:
            tam -= 0.1
    return round(tam, 1)


def _quadros(pg: Pagina, totais, x, y, w, por_linha):
    gap = 2
    cw = (w - 4 - (por_linha - 1) * gap) / por_linha
    tam_titulo = _tamanho_titulos(pg, [q['titulo'] for q in totais], cw - 5)
    for idx, q in enumerate(totais):
        r, c = divmod(idx, por_linha)
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


def _carimbo(pg: Pagina, f: Folha, dados, yb, hb, escala):
    totais = totais_por_produto(dados)
    pg.caixa(M, yb, f.larg, hb, LINHA, 'white')
    xb, xc = M + WA + 3, M + WA + 3 + f.wb + 3
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
    _quadros(pg, totais, xb, yb, f.wb, f.por_linha)
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

def _linha_tabela(pg: Pagina, f: Folha, yy: float, valores, bold=False, cor=GRAFITE):
    ultima = len(COLUNAS) - 1
    for i, (valor, (_, fx, ha)) in enumerate(zip(valores, COLUNAS)):
        if not valor:
            continue
        x = f.col(fx)
        tam = LETRA_LINHA
        if i == ultima:                               # O.S.: reduz/corta para caber na coluna
            valor, tam = _caber(pg, valor, M + f.larg - x - 1, LETRA_LINHA, 9)
        pg.texto(x, yy + LINHA_TAB / 2, valor, tam, cor, 'bold' if bold else 'normal', ha=ha, va='center')


def _tabela(pg: Pagina, f: Folha, y, titulo, linhas, total):
    """Título, cabeçalho, linhas (zebradas) e, se total não for None, a linha de total e a nota.
    Devolve o y logo abaixo do que foi desenhado."""
    pg.texto(M, y, titulo, 12, GRAFITE, 'bold')
    for nome, fx, ha in COLUNAS:
        pg.texto(f.col(fx), y + 8.0, nome, 10, MARCA, 'bold', ha=ha, va='center')
    pg.ret(M, y + 10.4, f.larg, 0.35, GRAFITE)
    yy = y + CAB_TAB
    grupo = -1
    for valores in linhas:
        if valores[0]:                     # linha que abre um talhão (as seguintes do mesmo talhão vêm com '')
            grupo += 1
        if grupo % 2:                      # zebrado por TALHÃO: as linhas do mesmo talhão têm o mesmo fundo
            pg.ret(M, yy, f.larg, LINHA_TAB, '#f4f6f5')
        _linha_tabela(pg, f, yy, valores)
        yy += LINHA_TAB
    if total is not None:
        pg.ret(M, yy + 0.3, f.larg, 0.35, GRAFITE)
        _linha_tabela(pg, f, yy + 0.3, total, bold=True)
        yy += LINHA_TAB + 0.3
        pg.texto(M, yy + 1.5, NOTA, 6, CINZA)
        yy += 4
    return yy


def _paginar(f: Folha, linhas: list, hb: float) -> list:
    """Intervalos (ini, fim) de linhas por página de tabela. Quebra só entre talhões (a linha de um talhão nunca
    se separa); só um talhão maior que a página é partido, e a página seguinte repete o número dele.
    Retrato: a 1ª página tem o mapa (>= 45% da altura útil) e o começo da tabela. Paisagem: a tabela começa
    numa página só de tabela (a folha do mapa não entra aqui). O total e a nota ficam na última página."""
    n = len(linhas)
    if n == 0:
        return [(0, 0)]
    tab_max = f.u - 2 * GAP - hb - 0.45 * f.u
    cap1 = int((tab_max - CAB_TAB) // LINHA_TAB)
    last1 = int((tab_max - CAB_TAB - TOTAL_NOTA) // LINHA_TAB)
    capx = f.cap_tabela
    lastx = int((f.base - TOPO_CONT - CAB_TAB - TOTAL_NOTA) // LINHA_TAB)
    inicios = {i for i, linha in enumerate(linhas) if linha[0] != ''}
    paginas, pos, primeira = [], 0, not f.paisagem
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


def _rodape(pg: Pagina, f: Folha, dados, k: int, n: int):
    y = f.H - 19
    pg.ret(M, y, f.larg, 0.2, LINHA)
    pg.texto(M, y + 1.2, 'Pedra Agroindustrial S/A · Geotecnologia', 4.8, CINZA)
    pg.texto(f.W - M, y + 1.2, f"Gerado em {_gerado_em(dados):%d/%m/%Y} por {dados.get('gerado_por', '')}",
             4.8, CINZA, ha='right')
    if n > 1:
        pg.texto(f.W / 2, y + 1.2, f'Página {k} de {n}', 4.8, CINZA, ha='center')


def _cabecalho_extra(pg: Pagina, dados):
    pg.texto(M, TOPO, f"{dados['cod_faz']} · {dados['nome']}", 12, GRAFITE, 'bold')


# ---------- PDF ----------

def gerar_pdf(dados: dict, destino) -> str:
    gdf = _gdf(dados)
    f = PAISAGEM if orientacao(gdf) == 'paisagem' else RETRATO
    totais = totais_por_produto(dados)
    linhas = linhas_tabela(dados)
    total = ['Total', br(area_total(dados)), '', '', '', '']
    hb = _altura_carimbo(f, totais)
    intervalos = _paginar(f, linhas, hb)
    # Retrato: a 1ª fatia da tabela vai na folha do mapa. Paisagem: a folha do mapa não tem tabela.
    na_folha_do_mapa = None if f.paisagem else intervalos[0]
    so_tabela = intervalos if f.paisagem else intervalos[1:]
    n_paginas = 1 + len(so_tabela)
    if na_folha_do_mapa:
        ini, fim = na_folha_do_mapa
        h_tab1 = CAB_TAB + (fim - ini) * LINHA_TAB + (TOTAL_NOTA if n_paginas == 1 else 0)
        h_mapa = f.u - 2 * GAP - hb - h_tab1
    else:
        h_mapa = f.u - GAP - hb

    pg = nova_pagina(f.W, f.H)
    escala = _mapa(pg, dados, gdf, M, TOPO, f.larg, h_mapa)
    yb = TOPO + h_mapa + GAP
    _carimbo(pg, f, dados, yb, hb, escala)
    if na_folha_do_mapa:
        _tabela(pg, f, yb + hb + GAP, 'APLICAÇÕES POR TALHÃO', _recortar(linhas, *na_folha_do_mapa),
                total if n_paginas == 1 else None)
    _rodape(pg, f, dados, 1, n_paginas)

    with PdfPages(destino) as pdf:
        pdf.savefig(pg.fig)
        plt.close(pg.fig)
        for k, (ini, fim) in enumerate(so_tabela, start=2):
            pg = nova_pagina(f.W, f.H)
            _cabecalho_extra(pg, dados)
            titulo = 'APLICAÇÕES POR TALHÃO' if (f.paisagem and k == 2) else 'APLICAÇÕES POR TALHÃO (continuação)'
            _tabela(pg, f, TOPO_CONT, titulo, _recortar(linhas, ini, fim), total if k == n_paginas else None)
            _rodape(pg, f, dados, k, n_paginas)
            pdf.savefig(pg.fig)
            plt.close(pg.fig)
    return 'paisagem' if f.paisagem else 'retrato'


def gerar_bytes(json_texto: str) -> bytes:
    buffer = io.BytesIO()
    gerar_pdf(json.loads(json_texto), buffer)
    return buffer.getvalue()
