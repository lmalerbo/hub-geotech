"""PDF do mapa de aplicação — layout v6 (spec, seção 4). Coordenadas da página em mm (origem no topo)."""
import datetime
from dataclasses import dataclass

import geopandas as gpd
import matplotlib

matplotlib.use('Agg')
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon as MplPolygon, Rectangle  # noqa: E402

from drone.config import LOGO  # noqa: E402
from drone.geometria import Recorte  # noqa: E402

MARCA, GRAFITE, CINZA, LINHA = '#138a3e', '#1f2a30', '#6b7479', '#cfd5d8'
CORES = {'normal': ('#a0694b', '#5c3824', '#8a5a3f', 'NORMAL'),
         'catacao': ('#5b8c5a', '#2f5a2e', '#4d7c4c', 'CATAÇÃO')}
MM = 1 / 25.4
plt.rcParams['font.family'] = ['Segoe UI', 'DejaVu Sans']
plt.rcParams['pdf.fonttype'] = 42


@dataclass
class DadosMapa:
    cod_faz: int
    nome: str
    tipo: str
    revisao: int
    talhoes: gpd.GeoDataFrame
    recorte: Recorte
    gerado_em: datetime.date
    safra: str | None = None      # legado: safra original do projeto (ex.: '24/25')


def orientacao(talhoes) -> str:
    minx, miny, maxx, maxy = talhoes.total_bounds
    return 'paisagem' if (maxx - minx) > (maxy - miny) else 'retrato'


def safra_de(data: datetime.date) -> str:
    ano = data.year if data.month >= 4 else data.year - 1
    return f'{ano % 100:02d}/{(ano + 1) % 100:02d}'


def safra_do_mapa(d: 'DadosMapa') -> str:
    return d.safra or safra_de(d.gerado_em)


def br(v: float) -> str:
    return f'{v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


class Pagina:
    """Ajuda a desenhar em mm, com y contado a partir do topo da folha."""

    def __init__(self, fig, W, H):
        self.fig, self.W, self.H = fig, W, H

    def eixo(self, x, y, w, h):
        return self.fig.add_axes([x / self.W, 1 - (y + h) / self.H, w / self.W, h / self.H])

    def caixa(self, x, y, w, h, cor_borda=LINHA, fundo='white', raio=1.6, largura=0.6):
        self.fig.patches.append(FancyBboxPatch(
            (x / self.W, 1 - (y + h) / self.H), w / self.W, h / self.H,
            boxstyle=f'round,pad=0,rounding_size={raio / self.W}', transform=self.fig.transFigure,
            facecolor=fundo, edgecolor=cor_borda, linewidth=largura))

    def texto(self, x, y, s, tam=7, cor=GRAFITE, peso='normal', ha='left', va='top', **kw):
        self.fig.text(x / self.W, 1 - y / self.H, s, fontsize=tam, color=cor, fontweight=peso,
                      ha=ha, va=va, **kw)

    def ret(self, x, y, w, h, cor):
        self.fig.patches.append(Rectangle((x / self.W, 1 - (y + h) / self.H), w / self.W, h / self.H,
                                          transform=self.fig.transFigure, color=cor, linewidth=0))


def _mapa(pg: Pagina, d: DadosMapa, x, y, w, h):
    preenche, borda, _, _ = CORES[d.tipo]
    ax = pg.eixo(x, y, w, h)
    minx, miny, maxx, maxy = d.talhoes.total_bounds
    topo, base, lado = 22, 14, 8                      # reserva para logo (cima) e escala (baixo)
    s = min((w - 2 * lado) / (maxx - minx), (h - topo - base) / (maxy - miny))   # mm por metro
    x0 = minx - (lado + ((w - 2 * lado) - (maxx - minx) * s) / 2) / s
    y0 = miny - (base + ((h - topo - base) - (maxy - miny) * s) / 2) / s
    ax.set_xlim(x0, x0 + w / s)
    ax.set_ylim(y0, y0 + h / s)
    ax.set_facecolor('#fbfcfb')
    ax.set_xticks([]), ax.set_yticks([])
    for lado_ax in ax.spines.values():
        lado_ax.set_visible(False)
    d.talhoes.plot(ax=ax, facecolor='white', edgecolor=GRAFITE, linewidth=0.5)
    gpd.GeoSeries([d.recorte.area], crs=d.talhoes.crs).plot(ax=ax, facecolor=preenche, edgecolor=borda,
                                                             linewidth=0.3, alpha=0.92)
    for _, t in d.talhoes.iterrows():
        p = t.geometry.representative_point()
        ax.text(p.x, p.y, str(int(t['TALHAO'])), fontsize=6.5, fontweight='semibold', color=GRAFITE,
                ha='center', va='center', path_effects=[pe.withStroke(linewidth=2, foreground='white')])
    # barra de escala colada no canto inferior esquerdo (sem contorno)
    barra = next(b for b in (100, 250, 500, 1000, 2000, 5000) if b * s >= 25)
    bx, by, alt = x0 + 5 / s, y0 + 3 / s, 1.3 / s
    for i, (ini, fim, cor) in enumerate([(0, .25, GRAFITE), (.25, .5, 'white'), (.5, 1, GRAFITE)]):
        ax.add_patch(Rectangle((bx + ini * barra, by), (fim - ini) * barra, alt, facecolor=cor,
                               edgecolor=GRAFITE, linewidth=0.3))
    for frac, rotulo in [(0, '0'), (.5, str(barra // 2)), (1, f'{barra} m')]:
        ax.text(bx + frac * barra, by + alt * 2.2, rotulo, fontsize=5, color=GRAFITE, ha='center' if frac else 'left')
    # moldura arredondada e logo colado no canto superior esquerdo (sem contorno)
    pg.caixa(x, y, w, h, cor_borda=GRAFITE, fundo='none', raio=3, largura=0.7)
    logo = pg.eixo(x + 2, y + 2, 34, 15)
    logo.imshow(mpimg.imread(LOGO))
    logo.axis('off')
    return round(1000 / s / 500) * 500 or 500


ALT_MIN = 3.2   # mm por linha: abaixo disso a tabela fica ilegível e vai para as páginas seguintes
COLS = [('SEÇÃO', 0.02, 'left'), ('TALHÃO', 0.30, 'right'), ('ÁREA PROD. (ha)', 0.66, 'right'),
        ('APLICÁVEL (ha)', 0.98, 'right')]


def _cabe(n, h) -> bool:
    return (h - 22) / (n + 2) >= ALT_MIN


def _grade(pg: Pagina, d: DadosMapa, linhas, x, y, w, alt, total=True):
    """Cabeçalho + linhas (+ total) a partir de y; devolve o y logo abaixo."""
    tam = max(4.0, min(alt * 1.55, 6.5))
    for nome, fx, ha in COLS:
        pg.texto(x + fx * w, y, nome, 5, MARCA, 'bold', ha=ha)
    pg.ret(x, y + 3.4, w, 0.35, GRAFITE)
    yy = y + 4.2
    for i, t in enumerate(linhas):
        if i % 2:
            pg.ret(x, yy, w, alt, '#f4f6f5')
        for valor, (_, fx, ha) in zip([str(d.cod_faz), str(t['talhao']), br(t['area_prod']), br(t['aplicavel_ha'])], COLS):
            pg.texto(x + fx * w, yy + alt * 0.15, valor, tam, ha=ha)
        yy += alt
    if total:
        pg.ret(x, yy + 0.3, w, 0.35, GRAFITE)
        for valor, (_, fx, ha) in zip(['Total', '', br(d.recorte.area_total_ha), br(d.recorte.aplicacao_ha)], COLS):
            pg.texto(x + fx * w, yy + 1.2, valor, tam, peso='bold', ha=ha)
        yy += alt + 1
    return yy


def _tabela(pg: Pagina, d: DadosMapa, x, y, w, h):
    preenche, borda, _, _ = CORES[d.tipo]
    linhas = d.recorte.por_talhao
    pg.texto(x, y, 'ÁREAS POR TALHÃO', 5.5, CINZA, 'semibold')
    if _cabe(len(linhas), h):
        yy = _grade(pg, d, linhas, x, y + 5, w, min(4.2, (h - 22) / (len(linhas) + 2)))
    else:
        pg.texto(x, y + 4.5, f'{len(linhas)} talhões: tabela completa a partir da página 2.', 6, GRAFITE)
        yy = _grade(pg, d, [], x, y + 10, w, 4.2)
    yy += 2
    pg.ret(x, yy, 5, 3, 'white'), pg.caixa(x, yy, 5, 3, GRAFITE, 'white', 0.3, 0.4)
    pg.texto(x + 6.5, yy - 0.2, 'Talhão', 5.5, CINZA)
    pg.caixa(x + 22, yy, 5, 3, borda, preenche, 0.3, 0.4)
    pg.texto(x + 28.5, yy - 0.2, 'Área de aplicação', 5.5, CINZA)


def _paginas_tabela(pdf, d: DadosMapa, W, H):
    """Tabela completa em colunas, nas páginas seguintes (fazendas com muitos talhões)."""
    M, alt, gut = 10, 4.2, 8
    ncol = 3 if W > H else 2
    cw = (W - 2 * M - (ncol - 1) * gut) / ncol
    por_col = int((H - 2 * M - 30) / alt)
    linhas = d.recorte.por_talhao
    por_pag = por_col * ncol
    paginas = [linhas[i:i + por_pag] for i in range(0, len(linhas), por_pag)]
    for k, pag in enumerate(paginas):
        fig = plt.figure(figsize=(W * MM, H * MM))
        pg = Pagina(fig, W, H)
        pg.ret(0, 0, W, 4, MARCA)
        pg.texto(M, M, f'{d.cod_faz} · {d.nome}', 12, peso='bold')
        pg.texto(M, M + 7, f'ÁREAS POR TALHÃO · Rev{d.revisao}', 5.5, CINZA, 'semibold')
        pg.texto(W - M, M + 7, f'Página {k + 2} de {len(paginas) + 1}', 5.5, CINZA, ha='right')
        for c in range(ncol):
            fatia = pag[c * por_col:(c + 1) * por_col]
            if fatia:
                ultima = k == len(paginas) - 1 and (c + 1) * por_col >= len(pag)
                _grade(pg, d, fatia, M + c * (cw + gut), M + 14, cw, alt, total=ultima)
        pdf.savefig(fig)
        plt.close(fig)


def _carimbo(pg: Pagina, d: DadosMapa, x, y, w, escala):
    _, _, cor_tag, rotulo = CORES[d.tipo]
    pg.ret(x, y, 0.9, 16, MARCA)
    pg.caixa(x + 3, y, 16, 3.6, cor_tag, cor_tag, 0.5, 0.1)
    pg.texto(x + 11, y + 0.5, rotulo, 4.5, 'white', 'bold', ha='center')
    pg.texto(x + 3, y + 5, f'{d.cod_faz} · {d.nome}', 12, peso='bold')
    pg.texto(x + 3, y + 11.5, 'MAPA DE APLICAÇÃO · DRONE', 5.5, CINZA)
    y += 19
    meia = (w - 3) / 2
    pct = d.recorte.aplicacao_ha / d.recorte.area_total_ha * 100 if d.recorte.area_total_ha else 0
    for i, (titulo, valor, extra, destaque) in enumerate([
            ('ÁREA DE APLICAÇÃO', d.recorte.aplicacao_ha, f'{br(pct)}% da área', True),
            ('ÁREA TOTAL', d.recorte.area_total_ha, f'{len(d.recorte.por_talhao)} talhões', False)]):
        cx = x + i * (meia + 3)
        pg.caixa(cx, y, meia, 15, '#b9dcc4' if destaque else LINHA, '#f1f8f3' if destaque else 'white')
        pg.texto(cx + 2.5, y + 1.8, titulo, 4.8, CINZA, 'semibold')
        pg.texto(cx + 2.5, y + 5, f'{br(valor)}', 12, MARCA if destaque else GRAFITE, 'bold')
        pg.texto(cx + meia - 2.5, y + 6.8, 'ha', 5.5, CINZA, 'semibold', ha='right')
        pg.texto(cx + 2.5, y + 11.2, extra, 5, CINZA)
    y += 18
    pg.caixa(x, y, w, 10)
    celula = (w - 14) / 3
    for i, (titulo, valor) in enumerate([('ESCALA', f'1:{escala:,}'.replace(',', '.')),
                                         ('SAFRA', safra_do_mapa(d)), ('REVISÃO', f'Rev{d.revisao}')]):
        cx = x + i * celula
        if i:
            pg.ret(cx, y + 1.5, 0.25, 7, LINHA)
        pg.texto(cx + 2.5, y + 1.8, titulo, 4.5, CINZA, 'semibold')
        pg.texto(cx + 2.5, y + 4.8, valor, 7, peso='semibold')
    nx, ny = x + w - 7, y + 1.3            # seta de norte desenhada
    for pts, cor in [([(0, 0), (2.4, 6), (0, 4.8), (-2.4, 6)], GRAFITE), ([(0, 0), (0, 4.8), (-2.4, 6)], CINZA)]:
        pg.fig.patches.append(MplPolygon([((nx + px) / pg.W, 1 - (ny + py) / pg.H) for px, py in pts],
                                         closed=True, transform=pg.fig.transFigure, color=cor, linewidth=0))
    pg.texto(nx, ny + 6.4, 'N', 5.5, peso='bold', ha='center')
    y += 13
    pg.ret(x, y, w, 0.2, LINHA)
    pg.texto(x, y + 1.2, 'Pedra Agroindustrial S/A · Geotecnologia', 4.8, CINZA)
    pg.texto(x + w, y + 1.2, f'Gerado em {d.gerado_em:%d/%m/%Y}', 4.8, CINZA, ha='right')


ALTURA_CARIMBO = 66


def gerar_pdf(d: DadosMapa, destino) -> str:
    orient = orientacao(d.talhoes)
    W, H = (297, 210) if orient == 'paisagem' else (210, 297)
    fig = plt.figure(figsize=(W * MM, H * MM))
    pg = Pagina(fig, W, H)
    pg.ret(0, 0, W, 4, MARCA)                                   # faixa da marca no topo
    M = 10
    if orient == 'paisagem':
        mw = W * 0.63
        escala = _mapa(pg, d, M, M, mw, H - 2 * M)
        px, pw = M + mw + 7, W - (M + mw + 7) - M
        _tabela(pg, d, px, M, pw, H - 2 * M - ALTURA_CARIMBO - 6)
        _carimbo(pg, d, px, H - M - ALTURA_CARIMBO, pw, escala)
    else:
        mh = H - 2 * M - ALTURA_CARIMBO - 8
        escala = _mapa(pg, d, M, M, W - 2 * M, mh)
        cw = (W - 2 * M - 8) / 2
        _tabela(pg, d, M, M + mh + 8, cw, ALTURA_CARIMBO)
        _carimbo(pg, d, M + cw + 8, M + mh + 8, cw, escala)
    area_tabela = (H - 2 * M - ALTURA_CARIMBO - 6) if orient == 'paisagem' else ALTURA_CARIMBO
    with PdfPages(destino) as pdf:
        pdf.savefig(fig)
        plt.close(fig)
        if not _cabe(len(d.recorte.por_talhao), area_tabela):
            _paginas_tabela(pdf, d, W, H)
    return orient
