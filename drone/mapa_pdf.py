"""PDF do mapa de aplicação — layout v6 (spec, seção 4). Coordenadas da página em mm (origem no topo).

O layout comum (página, grade, escala, moldura, rodapé) mora em mapas/layout.py; aqui ficam as regras do Drone."""
import datetime
from dataclasses import dataclass

import geopandas as gpd

from mapas.layout import (  # noqa: F401  (reexportados: a interface pública deste módulo continua a mesma)
    ALT_MIN, CINZA, GRAFITE, LINHA, MARCA, MM, Pagina, br, cabe, caixa_norte, escala_grafica,
    escala_numerica, eixo_mapa, grade, moldura_logo, nova_pagina, orientacao, paginas_tabela, rodape, safra_de,
)
from drone.config import LOGO  # noqa: E402
from drone.geometria import Recorte  # noqa: E402

import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

CORES = {'normal': ('#a0694b', '#5c3824', '#8a5a3f', 'NORMAL'),
         'catacao': ('#5b8c5a', '#2f5a2e', '#4d7c4c', 'CATAÇÃO')}


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
    cobertura_pct: float | None = None


def linha_incompleta(d: 'DadosMapa'):
    if d.tipo != 'normal' or d.cobertura_pct is None or d.cobertura_pct >= 99.95:
        return None
    return f'Incompleta · {d.cobertura_pct:.0f}% da fazenda'


def safra_do_mapa(d: 'DadosMapa') -> str:
    return d.safra or safra_de(d.gerado_em)


COLS = [('SEÇÃO', 0.02, 'left'), ('TALHÃO', 0.30, 'right'), ('ÁREA PROD. (ha)', 0.66, 'right'),
        ('APLICÁVEL (ha)', 0.98, 'right')]


def _linhas(d: 'DadosMapa'):
    return [[str(d.cod_faz), str(t['talhao']), br(t['area_prod']), br(t['aplicavel_ha'])]
            for t in d.recorte.por_talhao]


def _totais(d: 'DadosMapa'):
    return ['Total', '', br(d.recorte.area_total_ha), br(d.recorte.aplicacao_ha)]


def _mapa(pg: Pagina, d: DadosMapa, x, y, w, h):
    preenche, borda, _, _ = CORES[d.tipo]
    ax, s, x0, y0 = eixo_mapa(pg, d.talhoes, x, y, w, h)
    d.talhoes.plot(ax=ax, facecolor='white', edgecolor=GRAFITE, linewidth=0.5)
    gpd_recorte = gpd.GeoSeries([d.recorte.area], crs=d.talhoes.crs)
    gpd_recorte.plot(ax=ax, facecolor=preenche, edgecolor=borda, linewidth=0.3, alpha=0.92)
    for _, t in d.talhoes.iterrows():
        p = t.geometry.representative_point()
        ax.text(p.x, p.y, str(int(t['TALHAO'])), fontsize=6.5, fontweight='semibold', color=GRAFITE,
                ha='center', va='center', path_effects=[pe.withStroke(linewidth=2, foreground='white')])
    escala_grafica(ax, s, x0, y0)
    moldura_logo(pg, x, y, w, h, LOGO)
    return escala_numerica(s)


def _tabela(pg: Pagina, d: DadosMapa, x, y, w, h):
    preenche, borda, _, _ = CORES[d.tipo]
    linhas = _linhas(d)
    pg.texto(x, y, 'ÁREAS POR TALHÃO', 5.5, CINZA, 'semibold')
    if cabe(len(linhas), h):
        yy = grade(pg, COLS, linhas, x, y + 5, w, min(4.2, (h - 22) / (len(linhas) + 2)), _totais(d))
    else:
        pg.texto(x, y + 4.5, f'{len(linhas)} talhões: tabela completa a partir da página 2.', 6, GRAFITE)
        yy = grade(pg, COLS, [], x, y + 10, w, 4.2, _totais(d))
    yy += 2
    pg.ret(x, yy, 5, 3, 'white'), pg.caixa(x, yy, 5, 3, GRAFITE, 'white', 0.3, 0.4)
    pg.texto(x + 6.5, yy - 0.2, 'Talhão', 5.5, CINZA)
    pg.caixa(x + 22, yy, 5, 3, borda, preenche, 0.3, 0.4)
    pg.texto(x + 28.5, yy - 0.2, 'Área de aplicação', 5.5, CINZA)


def _cabecalho_extra(d: DadosMapa):
    """Título e subtítulo de cada página extra da tabela."""
    def desenhar(pg: Pagina):
        pg.texto(10, 10, f'{d.cod_faz} · {d.nome}', 12, peso='bold')
        pg.texto(10, 10 + 7, f'ÁREAS POR TALHÃO · Rev{d.revisao}', 5.5, CINZA, 'semibold')
    return desenhar


def _paginas_tabela(pdf, d: DadosMapa, W, H):
    """Tabela completa em colunas, nas páginas seguintes (fazendas com muitos talhões)."""
    paginas_tabela(pdf, W, H, COLS, _linhas(d), _totais(d), _cabecalho_extra(d))


def _carimbo(pg: Pagina, d: DadosMapa, x, y, w, escala):
    _, _, cor_tag, rotulo = CORES[d.tipo]
    pg.ret(x, y, 0.9, 16, MARCA)
    pg.caixa(x + 3, y, 16, 3.6, cor_tag, cor_tag, 0.5, 0.1)
    pg.texto(x + 11, y + 0.5, rotulo, 4.5, 'white', 'bold', ha='center')
    pg.texto(x + 3, y + 5, f'{d.cod_faz} · {d.nome}', 12, peso='bold')
    pg.texto(x + 3, y + 11.5, 'MAPA DE APLICAÇÃO · DRONE', 5.5, CINZA)
    aviso = linha_incompleta(d)
    if aviso:
        pg.texto(x + w, y + 11.5, aviso, 5.5, '#d4890a', 'bold', ha='right')
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
    caixa_norte(pg, x + w - 7, y + 1.3)
    y += 13
    rodape(pg, x, y, w, 'Pedra Agroindustrial S/A · Geotecnologia', f'Gerado em {d.gerado_em:%d/%m/%Y}')


ALTURA_CARIMBO = 66


def gerar_pdf(d: DadosMapa, destino) -> str:
    orient = orientacao(d.talhoes)
    W, H = (297, 210) if orient == 'paisagem' else (210, 297)
    pg = nova_pagina(W, H)
    fig = pg.fig
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
        if not cabe(len(d.recorte.por_talhao), area_tabela):
            _paginas_tabela(pdf, d, W, H)
    return orient
