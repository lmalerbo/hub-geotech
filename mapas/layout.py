"""Layout comum de PDF de mapa (coordenadas da página em mm, origem no topo).

Sem regra de negócio: quem chama passa os textos, os dados e os caminhos."""
import matplotlib

matplotlib.use('Agg')
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon as MplPolygon, Rectangle  # noqa: E402

MARCA, GRAFITE, CINZA, LINHA = '#138a3e', '#1f2a30', '#6b7479', '#cfd5d8'
MM = 1 / 25.4
ALT_MIN = 3.2   # mm por linha: abaixo disso a tabela fica ilegível e vai para as páginas seguintes
FONTES = ['Segoe UI', 'Selawik', 'DejaVu Sans']
plt.rcParams['font.family'] = FONTES
plt.rcParams['pdf.fonttype'] = 42


def orientacao(talhoes) -> str:
    minx, miny, maxx, maxy = talhoes.total_bounds
    return 'paisagem' if (maxx - minx) > (maxy - miny) else 'retrato'


def safra_de(data) -> str:
    ano = data.year if data.month >= 4 else data.year - 1
    return f'{ano % 100:02d}/{(ano + 1) % 100:02d}'


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


def nova_pagina(W, H) -> Pagina:
    """Figura nova em W x H mm, com a faixa da marca no topo."""
    fig = plt.figure(figsize=(W * MM, H * MM))
    pg = Pagina(fig, W, H)
    pg.ret(0, 0, W, 4, MARCA)
    return pg


def eixo_mapa(pg: Pagina, gdf, x, y, w, h):
    """Cria o eixo do mapa já enquadrado no GeoDataFrame. Devolve (ax, s, x0, y0): s = mm por metro."""
    ax = pg.eixo(x, y, w, h)
    minx, miny, maxx, maxy = gdf.total_bounds
    topo, base, lado = 22, 14, 8                      # reserva para logo (cima) e escala (baixo)
    s = min((w - 2 * lado) / (maxx - minx), (h - topo - base) / (maxy - miny))
    x0 = minx - (lado + ((w - 2 * lado) - (maxx - minx) * s) / 2) / s
    y0 = miny - (base + ((h - topo - base) - (maxy - miny) * s) / 2) / s
    ax.set_xlim(x0, x0 + w / s)
    ax.set_ylim(y0, y0 + h / s)
    ax.set_facecolor('#fbfcfb')
    ax.set_xticks([]), ax.set_yticks([])
    for lado_ax in ax.spines.values():
        lado_ax.set_visible(False)
    return ax, s, x0, y0


def escala_grafica(ax, s, x0, y0):
    """Barra de escala colada no canto inferior esquerdo (sem contorno)."""
    barra = next(b for b in (100, 250, 500, 1000, 2000, 5000) if b * s >= 25)
    bx, by, alt = x0 + 5 / s, y0 + 3 / s, 1.3 / s
    for ini, fim, cor in [(0, .25, GRAFITE), (.25, .5, 'white'), (.5, 1, GRAFITE)]:
        ax.add_patch(Rectangle((bx + ini * barra, by), (fim - ini) * barra, alt, facecolor=cor,
                               edgecolor=GRAFITE, linewidth=0.3))
    for frac, rotulo in [(0, '0'), (.5, str(barra // 2)), (1, f'{barra} m')]:
        ax.text(bx + frac * barra, by + alt * 2.2, rotulo, fontsize=5, color=GRAFITE, ha='center' if frac else 'left')


def moldura_logo(pg: Pagina, x, y, w, h, logo):
    """Moldura arredondada + logo colado no canto superior esquerdo (34x15 mm, sem contorno)."""
    pg.caixa(x, y, w, h, cor_borda=GRAFITE, fundo='none', raio=3, largura=0.7)
    eixo_logo = pg.eixo(x + 2, y + 2, 34, 15)
    eixo_logo.imshow(mpimg.imread(logo))
    eixo_logo.axis('off')


def escala_numerica(s) -> int:
    return round(1000 / s / 500) * 500 or 500


def cabe(n, h) -> bool:
    return (h - 22) / (n + 2) >= ALT_MIN


def grade(pg: Pagina, colunas, linhas, x, y, w, alt, total=None):
    """Cabeçalho + linhas (+ total, se não for None) a partir de y; devolve o y logo abaixo.

    colunas = [(titulo, fx, ha)]; linhas = list[list[str]]; total = list[str] | None."""
    tam = max(4.0, min(alt * 1.55, 6.5))
    for nome, fx, ha in colunas:
        pg.texto(x + fx * w, y, nome, 5, MARCA, 'bold', ha=ha)
    pg.ret(x, y + 3.4, w, 0.35, GRAFITE)
    yy = y + 4.2
    for i, valores in enumerate(linhas):
        if i % 2:
            pg.ret(x, yy, w, alt, '#f4f6f5')
        for valor, (_, fx, ha) in zip(valores, colunas):
            pg.texto(x + fx * w, yy + alt * 0.15, valor, tam, ha=ha)
        yy += alt
    if total is not None:
        pg.ret(x, yy + 0.3, w, 0.35, GRAFITE)
        for valor, (_, fx, ha) in zip(total, colunas):
            pg.texto(x + fx * w, yy + 1.2, valor, tam, peso='bold', ha=ha)
        yy += alt + 1
    return yy


def paginas_tabela(pdf, W, H, colunas, linhas, total, cabecalho):
    """Tabela completa em colunas, nas páginas seguintes. A página 1 é o mapa (o rótulo 'Página k de n' conta com ela).

    cabecalho(pg) desenha o título/subtítulo de cada página extra; total entra só na última."""
    M, alt, gut = 10, 4.2, 8
    ncol = 3 if W > H else 2
    cw = (W - 2 * M - (ncol - 1) * gut) / ncol
    por_col = int((H - 2 * M - 30) / alt)
    por_pag = por_col * ncol
    paginas = [linhas[i:i + por_pag] for i in range(0, len(linhas), por_pag)]
    for k, pag in enumerate(paginas):
        pg = nova_pagina(W, H)
        cabecalho(pg)
        pg.texto(W - M, M + 7, f'Página {k + 2} de {len(paginas) + 1}', 5.5, CINZA, ha='right')
        for c in range(ncol):
            fatia = pag[c * por_col:(c + 1) * por_col]
            if fatia:
                ultima = k == len(paginas) - 1 and (c + 1) * por_col >= len(pag)
                grade(pg, colunas, fatia, M + c * (cw + gut), M + 14, cw, alt, total if ultima else None)
        pdf.savefig(pg.fig)
        plt.close(pg.fig)


def caixa_norte(pg: Pagina, nx, ny):
    """Seta de norte (ponta em nx, ny) + 'N'."""
    for pts, cor in [([(0, 0), (2.4, 6), (0, 4.8), (-2.4, 6)], GRAFITE), ([(0, 0), (0, 4.8), (-2.4, 6)], CINZA)]:
        pg.fig.patches.append(MplPolygon([((nx + px) / pg.W, 1 - (ny + py) / pg.H) for px, py in pts],
                                         closed=True, transform=pg.fig.transFigure, color=cor, linewidth=0))
    pg.texto(nx, ny + 6.4, 'N', 5.5, peso='bold', ha='center')


def rodape(pg: Pagina, x, y, w, esquerda, direita):
    """Linha fina + texto à esquerda e à direita."""
    pg.ret(x, y, w, 0.2, LINHA)
    pg.texto(x, y + 1.2, esquerda, 4.8, CINZA)
    pg.texto(x + w, y + 1.2, direita, 4.8, CINZA, ha='right')
