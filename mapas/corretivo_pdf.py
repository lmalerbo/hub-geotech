"""PDF dos Mapas de aplicação (corretivo e aplicação aérea). A4 na orientação da fazenda (todas as folhas iguais).

Fazenda em pé (retrato), página 1 de cima para baixo: MAPA em largura total (legenda das cores dentro dele),
CARIMBO numa faixa horizontal (identificação | totais por produto | escala/área/safra e norte) e TABELA
"APLICAÇÕES POR TALHÃO" com letra grande. Linhas que não cabem vão para as páginas seguintes.
Fazenda larga (paisagem): folha 1 só com MAPA e CARIMBO; a TABELA, com a mesma letra grande, da folha 2 em diante.
Aplicação aérea: tabela só com TALHÃO, ÁREA e TOTAL (soma dos insumos por unidade), mapa de uma cor e a legenda com
os insumos; talhão 400 (margem de 5%) no fim da tabela.

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
import numpy as np
import shapely
from shapely import make_valid
from shapely.affinity import affine_transform
from shapely.geometry import box
from shapely.ops import unary_union

from mapas.corretivo_dados import (
    COR_AEREA, OPERACOES, SEM_APLICACAO, aerea, area_total, chave_cor, cores_do_mapa, faixas, linha_total,
    linhas_tabela, lista_os, rotulo, totais_por_produto, _ordenadas,
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
LETRA_LINHA = 12                 # letra das linhas da tabela (16/10: era 14, "pode diminuir um pouco")
LINHA_TAB = 6.5                  # altura de cada linha da tabela
CAB_TAB = 11.2                   # do topo da tabela até a primeira linha (título + cabeçalho)
TOTAL_NOTA = 12.5                # linha de total + nota, no fim da tabela
TOPO_CONT = 18                   # topo da tabela nas páginas só de tabela (depois do nome da fazenda)
LETRA_LEGENDA = 13
TIPO_TAM = 11                    # tipo do mapa, título do carimbo (28/10: era etiqueta de 4,5 pt)
LETRA_TALHAO = 9                 # número do talhão no mapa (16/10: era 6,5)
WA, WC = 60, 40                  # blocos do carimbo: identificação | totais (o resto) | escala/área/safra
LARG_RETRATO = 190               # as colunas abaixo são para 190 mm; em paisagem se espalham na proporção
COLUNAS = [('TALHÃO', 2, 'left'), ('ÁREA (ha)', 42, 'right'), ('APLICAÇÃO', 52, 'left'),
           ('DOSE (t/ha)', 124, 'right'), ('TOTAL (t)', 148, 'right'), ('O.S.', 153, 'left')]
NOTA = '* área editada · ÁREA ha · DOSE t/ha · TOTAL t'
# Aéreo (28/10): só TALHÃO | ÁREA | TOTAL (soma dos insumos, por unidade). O insumo fica na legenda e nos cards.
COLUNAS_AEREA = [('TALHÃO', 2, 'left'), ('ÁREA (ha)', 60, 'right'), ('TOTAL', 186, 'right')]
NOTA_AEREA = '* área editada · talhão 400 = margem de 5% da área · TOTAL = soma dos insumos do talhão'


def _colunas(dados):
    return COLUNAS_AEREA if aerea(dados) else COLUNAS


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

def _valida(geom):
    """Talhão com auto-interseção vira geometria válida (só a parte de área). Sem isso o GEOS do Pyodide quebra
    no union_all do enquadramento com TopologyException, que no navegador derruba o Python inteiro."""
    if geom is None or geom.is_valid:
        return geom
    v = make_valid(geom)
    if v.geom_type == 'GeometryCollection':
        v = unary_union([p for p in v.geoms if p.geom_type in ('Polygon', 'MultiPolygon')])
    return v


def _gdf(dados) -> gpd.GeoDataFrame:
    gdf = gpd.GeoDataFrame.from_features(dados['talhoes_geo']['features'], crs='EPSG:4326').to_crs(EPSG_UTM)
    gdf['geometry'] = gdf.geometry.apply(_valida)
    return gdf


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


def _subtitulo(pg: Pagina, lista, max_mm: float, dados):
    """'MAPA DE APLICAÇÃO · CORRETIVOS · O.S. …' (ou '· AÉREA ·'): reduz a letra até 4,8 pt; depois mostra menos
    O.S. ('… (+N)')."""
    base = f"MAPA DE APLICAÇÃO · {'AÉREA' if aerea(dados) else 'CORRETIVOS'} · O.S. "
    n = len(lista)
    for tam in (5.5, 5.2, 4.8):
        for k in range(n, 0, -1):
            s = base + ', '.join(lista[:k]) + ('' if k == n else f', … (+{n - k})')
            if _largura(pg, s, tam) <= max_mm:
                return s, tam
    return _cortar(pg, base + (lista[0] if lista else ''), max_mm, 4.8), 4.8


# ---------- mapa ----------

# Reservas (topo, base, lado) em mm, da mais justa à mais folgada: a fazenda chega o mais perto possível da moldura,
# desde que não fique embaixo do logo (canto sup. esquerdo), da escala (canto inf. esquerdo) nem da legenda.
# Da terceira em diante logo e escala estão sempre livres; as duas últimas só afastam a fazenda para abrir espaço
# para a legenda (09/11). Se nem a última tiver espaço, a legenda cobre o mínimo, sem tampar número de talhão.
RESERVAS = [(5, 5, 5), (12, 9, 6), (22, 14, 8), (30, 20, 16), (40, 26, 26)]
LOGO_MM, ESCALA_MM = (40, 19), (50, 12)            # cantos ocupados (largura, altura) a partir da moldura
# Onde a fazenda fica dentro da folga que sobra na direção que não limita o zoom: centrada (como sempre foi) e,
# se a legenda não couber, encostada em cima, embaixo, à direita ou à esquerda, antes de afastar mais o zoom.
ALINHAMENTOS = [(0, 0), (0, 1), (0, -1), (1, 0), (-1, 0)]


def _uniao(gdf):
    return gdf.geometry.union_all() if hasattr(gdf.geometry, 'union_all') else gdf.geometry.unary_union


def _caixa_dados(s, x0, y0, x, y, h, X0, Y0, X1, Y1):
    """Retângulo da página (mm) nas coordenadas do mapa (metros), para o enquadramento em teste."""
    return box(x0 + (X0 - x) / s, y0 + (y + h - Y1) / s, x0 + (X1 - x) / s, y0 + (y + h - Y0) / s)


def _para_mm(geom, s, x0, y0, x, y, h):
    """Geometria do mapa (metros) em mm da página (y cresce para baixo, como no resto do layout)."""
    return affine_transform(geom, [s, 0, 0, -s, x - x0 * s, y + h + y0 * s])


def _obstaculos_mm(gdf, s, x0, y0, x, y, w, h):
    """(fazenda, números dos talhões, caixas proibidas) em mm da página, para posicionar a legenda."""
    fazenda = _para_mm(_uniao(gdf), s, x0, y0, x, y, h)
    rotulos = [_para_mm(g.representative_point(), s, x0, y0, x, y, h) for g in gdf.geometry]
    proibidos = [box(x, y, x + LOGO_MM[0], y + LOGO_MM[1]), box(x, y + h - ESCALA_MM[1], x + ESCALA_MM[0], y + h)]
    return fazenda, rotulos, proibidos


def _enquadrar(pg: Pagina, gdf, x, y, w, h, leg):
    """(ax, s, x0, y0, reserva): o enquadramento mais justo em que nada cobre a fazenda. leg = (bw, bh) da legenda
    ou None; ela precisa caber em alguma posição encostada na moldura sem tocar a fazenda (_posicao_legenda)."""
    uniao = _uniao(gdf)
    minx, miny, maxx, maxy = gdf.total_bounds

    def cabe_tudo(s, x0, y0):
        livre = lambda X0, Y0, X1, Y1: _caixa_dados(s, x0, y0, x, y, h, X0, Y0, X1, Y1).intersection(uniao).area == 0
        if not (livre(x, y, x + LOGO_MM[0], y + LOGO_MM[1]) and livre(x, y + h - ESCALA_MM[1], x + ESCALA_MM[0], y + h)):
            return False
        if not leg:
            return True
        fazenda, rotulos, proibidos = _obstaculos_mm(gdf, s, x0, y0, x, y, w, h)
        _, _, cobre, tampa = _posicao_legenda(fazenda, rotulos, proibidos, x, y, w, h, *leg)
        return cobre == 0 and tampa == 0

    for reserva in RESERVAS:
        ax, s, x0, y0 = eixo_mapa(pg, gdf, x, y, w, h, reserva=reserva)
        topo, base, lado = reserva
        sobra_x = (w - 2 * lado) / s - (maxx - minx)          # folga (metros) na direção que não limita o zoom
        sobra_y = (h - topo - base) / s - (maxy - miny)
        for ax_, ay_ in ALINHAMENTOS:
            X0, Y0 = x0 - ax_ * sobra_x / 2, y0 - ay_ * sobra_y / 2
            if cabe_tudo(s, X0, Y0):
                ax.set_xlim(X0, X0 + w / s)
                ax.set_ylim(Y0, Y0 + h / s)
                return ax, s, X0, Y0, reserva
        if reserva == RESERVAS[-1]:
            return ax, s, x0, y0, reserva
        ax.remove()


def _mapa(pg: Pagina, dados, gdf, x, y, w, h) -> int:
    itens = _itens_legenda(dados)
    ax, s, x0, y0, _ = _enquadrar(pg, gdf, x, y, w, h, _tamanho_legenda(pg, itens) if itens else None)
    obstaculos = _obstaculos_mm(gdf, s, x0, y0, x, y, w, h)
    por_talhao = _aplicacoes_por_talhao(dados)
    cores = cores_do_mapa(dados)
    no_mapa = {int(k) for k in dados['areas']}
    pintados = []                                   # (geometria, número, cor) de cada talhão com geometria
    for _, linha in gdf.iterrows():
        t = int(linha['talhao'])
        geom = linha.geometry
        if t not in no_mapa:                        # talhão da fazenda fora do mapa: branco, número em cinza
            gpd.GeoSeries([geom], crs=gdf.crs).plot(ax=ax, facecolor='white', edgecolor='none')
            pintados.append((geom, t, CINZA))
            continue
        aps = por_talhao.get(t, [])
        if not aps:
            gpd.GeoSeries([geom], crs=gdf.crs).plot(ax=ax, facecolor=SEM_APLICACAO, edgecolor='none')
        elif aerea(dados):                          # aéreo: todos os insumos em todos os talhões, uma cor só
            gpd.GeoSeries([geom], crs=gdf.crs).plot(ax=ax, facecolor=COR_AEREA, edgecolor='none', alpha=0.92)
        else:
            for parte, ap in zip(faixas(geom, len(aps)), aps):
                if parte.is_empty or parte.area == 0:
                    continue
                gpd.GeoSeries([parte], crs=gdf.crs).plot(ax=ax, facecolor=cores[chave_cor(ap)],
                                                         edgecolor='none', alpha=0.92)
        pintados.append((geom, t, GRAFITE))
    for _, linha in gdf.iterrows():                 # contornos por cima das pinturas
        gpd.GeoSeries([linha.geometry], crs=gdf.crs).plot(ax=ax, facecolor='none', edgecolor=GRAFITE,
                                                          linewidth=0.5)
    for geom, t, cor in pintados:
        p = geom.representative_point()
        ax.text(p.x, p.y, str(t), fontsize=LETRA_TALHAO, fontweight='semibold', color=cor, ha='center',
                va='center', path_effects=[pe.withStroke(linewidth=2.5, foreground='white')])
    escala_grafica(ax, s, x0, y0)
    moldura_logo(pg, x, y, w, h, LOGO)
    _legenda_mapa(pg, itens, x, y, w, h, obstaculos)
    return escala_numerica(s)


# Posição da legenda, à moda dos rótulos do QGIS (motor PAL): gera muitas posições candidatas, descarta as que
# tocam obstáculos proibidos (logo, escala) e escolhe a de menor custo. Candidatas = a caixa encostada na moldura
# (MARGEM_LEG), deslizando de PASSO_CAND em PASSO_CAND mm pelas quatro bordas. Custo, nesta ordem: números de talhão
# tampados, área da fazenda coberta, distância até o canto mais próximo e, por fim, os cantos direitos (baixo, cima),
# que eram as duas únicas posições até 09/11.
MARGEM_LEG, PASSO_CAND, FOLGA_FAZENDA, RAIO_ROTULO = 2.5, 2.0, 1.5, 3.0


def _passos(a, b) -> list:
    if b < a:
        return []
    n = int((b - a) // PASSO_CAND)
    return [a + i * PASSO_CAND for i in range(n + 1)] + ([b] if a + n * PASSO_CAND < b else [])


def _posicao_legenda(fazenda, rotulos, proibidos, x, y, w, h, bw, bh) -> tuple:
    """(bx, by, área coberta, números tampados): canto sup. esquerdo da legenda (mm da página) na melhor posição.
    fazenda, rotulos (pontos) e proibidos (caixas) em mm da página."""
    esq, dir_, cima, baixo = x + MARGEM_LEG, x + w - bw - MARGEM_LEG, y + MARGEM_LEG, y + h - bh - MARGEM_LEG
    cand = list(dict.fromkeys([(bx, by) for bx in _passos(esq, dir_) for by in (baixo, cima)] +
                              [(bx, by) for by in _passos(cima, baixo) for bx in (dir_, esq)]))
    if cand:
        caixas = shapely.box(*np.array([[bx, by, bx + bw, by + bh] for bx, by in cand]).T)
        bloqueada = np.zeros(len(caixas), bool)
        for p in proibidos:
            bloqueada |= shapely.intersects(caixas, p)
        cand, caixas = [c for c, b in zip(cand, bloqueada) if not b], caixas[~bloqueada]
    if not cand:                                    # moldura pequena demais: fica no canto de sempre
        cand, caixas = [(dir_, baixo)], np.array([box(dir_, baixo, dir_ + bw, baixo + bh)])
    perto = fazenda.buffer(FOLGA_FAZENDA) if not fazenda.is_empty else fazenda
    shapely.prepare(perto)
    area = np.where(shapely.intersects(perto, caixas), shapely.area(shapely.intersection(caixas, perto)), 0.0)
    tampa = (np.array([shapely.intersects(caixas, r.buffer(RAIO_ROTULO)) for r in rotulos]).sum(axis=0)
             if rotulos else np.zeros(len(cand), int))

    def custo(i):
        bx, by = cand[i]
        canto = min(bx - esq, dir_ - bx) + min(by - cima, baixo - by)
        return tampa[i], round(area[i], 2), round(canto, 3), {(dir_, baixo): 0, (dir_, cima): 1}.get(cand[i], 2)

    i = min(range(len(cand)), key=custo)
    return cand[i][0], cand[i][1], float(area[i]), int(tampa[i])


PASSO_LEG, PAD_LEG, SW_LEG = 6.2, 2.5, 5.0


def _itens_legenda(dados) -> list:
    """[(cor, texto)]: só os tipos usados; Blend é um item só; '◩ duas aplicações' se algum talhão tiver duas.
    Aéreo: um quadrado só ('Área de aplicação') e, embaixo, o nome de cada insumo sem quadrado (cor '')."""
    if aerea(dados):
        nomes = list(dict.fromkeys(rotulo(a) for a in _ordenadas(dados)))
        return ([(COR_AEREA, 'Área de aplicação')] + [('', n) for n in nomes]) if nomes else []
    cores = cores_do_mapa(dados)
    rotulos: dict[str, str] = {}
    for a in _ordenadas(dados):                  # Blend Dolomítico e PH7 têm a mesma cor: um item só
        rotulos.setdefault(chave_cor(a), 'Blend' if a['tipo'] == 'blend' else rotulo(a))
    if not rotulos:
        return []
    duas = any(len(aps) >= 2 for aps in _aplicacoes_por_talhao(dados).values())
    return [(cores[c], t) for c, t in rotulos.items()] + ([(None, '◩ duas aplicações')] if duas else [])


def _tamanho_legenda(pg: Pagina, itens) -> tuple:
    larg = max(_largura(pg, t, LETRA_LEGENDA) for _, t in itens) + SW_LEG + 2.5
    return larg + 2 * PAD_LEG, PASSO_LEG * len(itens) + 2 * PAD_LEG - 1.2


def _legenda_mapa(pg: Pagina, itens, x, y, w, h, obstaculos):
    """Caixa branca (alpha 0,9) encostada na moldura, na posição escolhida por _posicao_legenda."""
    if not itens:
        return
    passo, pad, sw = PASSO_LEG, PAD_LEG, SW_LEG
    bw, bh = _tamanho_legenda(pg, itens)
    bx, by, _, _ = _posicao_legenda(*obstaculos, x, y, w, h, bw, bh)
    pg.fig.patches.append(FancyBboxPatch(
        (bx / pg.W, 1 - (by + bh) / pg.H), bw / pg.W, bh / pg.H, boxstyle='round,pad=0,rounding_size=0.0',
        transform=pg.fig.transFigure, facecolor='white', edgecolor=LINHA, linewidth=0.5, alpha=0.9))
    for i, (cor, texto) in enumerate(itens):
        yy = by + pad + i * passo + passo / 2
        if cor is None:
            pg.texto(bx + pad, yy, texto, LETRA_LEGENDA, CINZA, va='center')
        elif cor == '':                              # insumo do aéreo: nome sem quadrado, alinhado com os outros
            pg.texto(bx + pad + sw + 2.5, yy, texto, LETRA_LEGENDA, GRAFITE, va='center')
        else:
            pg.ret(bx + pad, yy - 1.5, sw, 3, cor)
            pg.texto(bx + pad + sw + 2.5, yy, texto, LETRA_LEGENDA, GRAFITE, va='center')


# ---------- carimbo ----------

# Cards dos totais: o aéreo usa cards maiores (o insumo e a unidade ficam legíveis no PDF).
# 'reserva' é a folga à direita do número para a unidade; 'linhas', quantas linhas o nome do produto pode ocupar.
# Aéreo: o nome tem até 25 letras e o card em retrato só 20 mm úteis, por isso duas linhas; o número desce até 8 pt
# para não ser cortado.
CARD = {False: dict(h=15, passo=18, tit=(4.8, 4.0), val=(12, 9), un=5.5, y_val=5, y_un=6.8, reserva=5, linhas=1),
        True: dict(h=20, passo=23, tit=(6.5, 5.0), val=(16, 8), un=8, y_val=8.2, y_un=10.8, reserva=4, linhas=2)}


def _altura_carimbo(f: Folha, totais, grande=False) -> float:
    rows = max(1, math.ceil(len(totais) / f.por_linha))
    c = CARD[grande]
    return max(24.0, c['h'] + 4 + c['passo'] * (rows - 1))


def _linhas_nome(pg: Pagina, nome: str, max_mm: float, tam: float, linhas=1) -> list[str]:
    """Nome do produto em até `linhas` linhas, quebrado por palavra; o que sobrar fica todo na última."""
    if linhas == 1 or _largura(pg, nome, tam, 'semibold') <= max_mm:
        return [nome]
    palavras = nome.split(' ')
    i = 1
    while i < len(palavras) and _largura(pg, ' '.join(palavras[:i + 1]), tam, 'semibold') <= max_mm:
        i += 1
    resto = ' '.join(palavras[i:])
    return [' '.join(palavras[:i])] + ([resto] if resto else [])


def _tamanho_titulos(pg: Pagina, titulos, max_mm: float, inicio=4.8, minimo=4.0, linhas=1) -> float:
    """Um tamanho só para todos os títulos dos quadros, reduzido (até o mínimo) se algum não couber."""
    tam = inicio
    for t in titulos:
        while tam > minimo and any(_largura(pg, l, tam, 'semibold') > max_mm for l in _linhas_nome(pg, t, max_mm, tam, linhas)):
            tam = round(tam - 0.1, 1)
    return tam


def _quadros(pg: Pagina, totais, x, y, w, por_linha, grande=False):
    c = CARD[grande]
    gap = 2
    cw = (w - 4 - (por_linha - 1) * gap) / por_linha
    tam_titulo = _tamanho_titulos(pg, [q['titulo'] for q in totais], cw - 5, *c['tit'], c['linhas'])
    for idx, q in enumerate(totais):
        r, col = divmod(idx, por_linha)
        cx, cy = x + 2 + col * (cw + gap), y + 2 + r * c['passo']
        destaque = idx == 0
        pg.caixa(cx, cy, cw, c['h'], '#b9dcc4' if destaque else LINHA, '#f1f8f3' if destaque else 'white')
        for n, linha in enumerate(_linhas_nome(pg, q['titulo'], cw - 5, tam_titulo, c['linhas'])):
            pg.texto(cx + 2.5, cy + 1.8 + n * tam_titulo * 0.3528 * 1.2, _cortar(pg, linha, cw - 5, tam_titulo, 'semibold'),
                     tam_titulo, CINZA, 'semibold')
        valor, t2 = _caber(pg, br(q['total']), cw - 5 - c['reserva'], *c['val'], 'bold')
        pg.texto(cx + 2.5, cy + c['y_val'], valor, t2, MARCA if destaque else GRAFITE, 'bold')
        pg.texto(cx + cw - 2.5, cy + c['y_un'], q['unidade'], c['un'], CINZA, 'semibold', ha='right')
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
    tipo = 'APLICAÇÃO AÉREA' if aerea(dados) else f"CORRETIVO · {OPERACOES[dados['operacao']].upper()}"
    tipo_txt, tt = _caber(pg, tipo, WA - 6, TIPO_TAM, 7, 'bold')
    pg.texto(x, yb + 2.3, tipo_txt, tt, MARCA, 'bold')
    y = yb + 2.3 + tt * 0.3528 * 1.35
    for texto, tam in _linhas_titulo(pg, f"{dados['cod_faz']} · {dados['nome']}", WA - 6):
        pg.texto(x, y, texto, tam, peso='bold')
        y += tam * 0.3528 * 1.2
    sub, ts = _subtitulo(pg, lista_os(dados), WA - 6, dados)
    pg.texto(x, y + 0.8, sub, ts, CINZA)
    # (b) totais por produto
    _quadros(pg, totais, xb, yb, f.wb, f.por_linha, aerea(dados))
    # (c) escala / área / safra e norte
    celulas = [('ESCALA', f'1:{escala:,}'.replace(',', '.')),
               (f'ÁREA · {len(dados["areas"])} TALHÕES' + (' + 5%' if aerea(dados) else ''),
                f'{br(area_total(dados))} ha'),
               ('SAFRA', safra_de(_data(dados)))]
    largura_txt = WC - 3 - 10            # a seta do norte fica à direita, sem encostar no texto
    for i, (titulo, valor) in enumerate(celulas):
        cy = yb + 2 + i * 7.2
        pg.texto(xc + 2.5, cy + 0.3, _cortar(pg, titulo, largura_txt, 4.8, 'semibold'), 4.8, CINZA, 'semibold')
        pg.texto(xc + 2.5, cy + 3.2, _cortar(pg, valor, largura_txt, 7, 'semibold'), 7, GRAFITE, 'semibold')
    caixa_norte(pg, xc + WC - 5.5, yb + 3)


# ---------- tabela ----------

def _linha_tabela(pg: Pagina, f: Folha, dados, yy: float, valores, bold=False, cor=GRAFITE):
    colunas = _colunas(dados)
    ultima = len(colunas) - 1
    for i, (valor, (_, fx, ha)) in enumerate(zip(valores, colunas)):
        if not valor:
            continue
        x = f.col(fx)
        tam = LETRA_LINHA
        if i == ultima and aerea(dados):              # TOTAL: reduz/corta para caber depois da ÁREA
            valor, tam = _caber(pg, valor, x - f.col(colunas[1][1]) - 10, LETRA_LINHA, 9)
        elif i == ultima:                             # O.S.: reduz/corta para caber na coluna
            valor, tam = _caber(pg, valor, M + f.larg - x - 1, LETRA_LINHA, 9)
        pg.texto(x, yy + LINHA_TAB / 2, valor, tam, cor, 'bold' if bold else 'normal', ha=ha, va='center')


def _tabela(pg: Pagina, f: Folha, dados, y, titulo, linhas, total):
    """Título, cabeçalho, linhas (zebradas) e, se total não for None, a linha de total e a nota.
    Devolve o y logo abaixo do que foi desenhado."""
    pg.texto(M, y, titulo, 12, GRAFITE, 'bold')
    for nome, fx, ha in _colunas(dados):
        pg.texto(f.col(fx), y + 8.0, nome, 10, MARCA, 'bold', ha=ha, va='center')
    pg.ret(M, y + 10.4, f.larg, 0.35, GRAFITE)
    yy = y + CAB_TAB
    grupo = -1
    for valores in linhas:
        if valores[0]:                     # linha que abre um talhão (as seguintes do mesmo talhão vêm com '')
            grupo += 1
        if grupo % 2:                      # zebrado por TALHÃO: as linhas do mesmo talhão têm o mesmo fundo
            pg.ret(M, yy, f.larg, LINHA_TAB, '#f4f6f5')
        _linha_tabela(pg, f, dados, yy, valores)
        yy += LINHA_TAB
    if total is not None:
        pg.ret(M, yy + 0.3, f.larg, 0.35, GRAFITE)
        _linha_tabela(pg, f, dados, yy + 0.3, total, bold=True)
        yy += LINHA_TAB + 0.3
        pg.texto(M, yy + 1.5, NOTA_AEREA if aerea(dados) else NOTA, 6, CINZA)
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
    total = linha_total(dados)
    hb = _altura_carimbo(f, totais, aerea(dados))
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
        _tabela(pg, f, dados, yb + hb + GAP, 'APLICAÇÕES POR TALHÃO', _recortar(linhas, *na_folha_do_mapa),
                total if n_paginas == 1 else None)
    _rodape(pg, f, dados, 1, n_paginas)

    with PdfPages(destino) as pdf:
        pdf.savefig(pg.fig)
        plt.close(pg.fig)
        for k, (ini, fim) in enumerate(so_tabela, start=2):
            pg = nova_pagina(f.W, f.H)
            _cabecalho_extra(pg, dados)
            titulo = 'APLICAÇÕES POR TALHÃO' if (f.paisagem and k == 2) else 'APLICAÇÕES POR TALHÃO (continuação)'
            _tabela(pg, f, dados, TOPO_CONT, titulo, _recortar(linhas, ini, fim), total if k == n_paginas else None)
            _rodape(pg, f, dados, k, n_paginas)
            pdf.savefig(pg.fig)
            plt.close(pg.fig)
    return 'paisagem' if f.paisagem else 'retrato'


def gerar_bytes(json_texto: str) -> bytes:
    buffer = io.BytesIO()
    gerar_pdf(json.loads(json_texto), buffer)
    return buffer.getvalue()
