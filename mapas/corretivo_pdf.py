"""PDF do mapa de aplicação de corretivos (layout do Drone, faixas e quadros por produto).

Coordenadas da página em mm (origem no topo). O layout comum mora em mapas/layout.py; as regras do
corretivo (cores, linhas da tabela, totais) mora em mapas/corretivo_dados.py."""
import datetime
import io
import json
import math
from pathlib import Path

import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from mapas.corretivo_dados import (
    CORES, OPERACOES, SEM_APLICACAO, area_total, chave_cor, faixas, linhas_tabela, lista_os, rotulo,
    totais_por_produto, _ordenadas,
)
from mapas.layout import (
    CINZA, GRAFITE, LINHA, MARCA, Pagina, br, cabe, caixa_norte, escala_grafica, escala_numerica,
    eixo_mapa, grade, moldura_logo, nova_pagina, orientacao, paginas_tabela, rodape, safra_de,
)

LOGO = Path(__file__).resolve().parent.parent / 'drone' / 'assets' / 'logo-pedra.png'
EPSG_UTM = 31983
COLS = [('TALHÃO', 0.02, 'left'), ('ÁREA', 0.20, 'right'), ('APLICAÇÃO', 0.24, 'left'),
        ('DOSE', 0.70, 'right'), ('TOTAL', 0.85, 'right'), ('O.S.', 0.98, 'right')]
M = 10
ALTURA_CARIMBO_BASE = 48          # carimbo = 48 + 18 por linha de quadros (66 com uma linha, como no Drone)
RESERVA_LEGENDA = 14              # mm reservados abaixo da grade (nota + legenda)


def _gdf(dados) -> gpd.GeoDataFrame:
    gdf = gpd.GeoDataFrame.from_features(dados['talhoes_geo']['features'], crs='EPSG:4326')
    return gdf.to_crs(EPSG_UTM)


def _data(dados) -> datetime.date:
    return datetime.date.fromisoformat(str(dados['data'])[:10])


def _aplicacoes_por_talhao(dados) -> dict:
    por_talhao: dict[int, list[dict]] = {}
    for a in _ordenadas(dados):
        for t in a['talhoes']:
            por_talhao.setdefault(int(t), []).append(a)
    return por_talhao


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
    return escala_numerica(s)


def _legenda(pg: Pagina, dados, x, y, w) -> float:
    """Quadradinhos só dos tipos usados; devolve o y logo abaixo da legenda."""
    rotulos: dict[str, str] = {}
    for a in _ordenadas(dados):
        rotulos.setdefault(chave_cor(a), rotulo(a))
    cursor, yy = x, y
    for chave, texto in rotulos.items():
        largura = 6.5 + 1.5 * len(texto) + 4
        if cursor + largura > x + w and cursor > x:
            cursor, yy = x, yy + 5
        pg.ret(cursor, yy, 5, 3, CORES[chave])
        pg.texto(cursor + 6.5, yy - 0.2, texto, 5.5, CINZA)
        cursor += largura
    if any(len(aps) >= 2 for aps in _aplicacoes_por_talhao(dados).values()):
        if cursor + 34 > x + w and cursor > x:
            cursor, yy = x, yy + 5
        pg.texto(cursor, yy - 0.2, '◩ duas aplicações', 5.5, CINZA)
        yy += 5
    return yy + 5 if rotulos else yy


def _tabela(pg: Pagina, dados, x, y, w, h):
    linhas = linhas_tabela(dados)
    total = ['Total', br(area_total(dados)), '', '', '', '']
    disp = h - RESERVA_LEGENDA
    pg.texto(x, y, 'APLICAÇÕES POR TALHÃO', 5.5, CINZA, 'semibold')
    if cabe(len(linhas), disp):
        alt = min(4.2, (disp - 22) / (len(linhas) + 2))
        yy = grade(pg, COLS, linhas, x, y + 5, w, alt, total)
    else:
        pg.texto(x, y + 4.5, f'{len(linhas)} linhas: tabela completa a partir da página 2.', 6, GRAFITE)
        yy = grade(pg, COLS, [], x, y + 10, w, 4.2, total)
    pg.texto(x, yy + 1, '* área editada · ÁREA ha · DOSE t/ha · TOTAL t', 4.8, CINZA)
    _legenda(pg, dados, x, yy + 6, w)


def _cabecalho_extra(dados):
    """Título e subtítulo de cada página extra da tabela."""
    def desenhar(pg: Pagina):
        pg.texto(10, 10, f"{dados['cod_faz']} · {dados['nome']}", 12, peso='bold')
        pg.texto(10, 17, 'APLICAÇÕES POR TALHÃO', 5.5, CINZA, 'semibold')
    return desenhar


def _quadros(pg: Pagina, totais, x, y, w):
    cw = (w - 6) / 3
    for idx, q in enumerate(totais):
        r, c = divmod(idx, 3)
        cx, cy = x + c * (cw + 3), y + r * 18
        destaque = idx == 0
        pg.caixa(cx, cy, cw, 15, '#b9dcc4' if destaque else LINHA, '#f1f8f3' if destaque else 'white')
        pg.texto(cx + 2.5, cy + 1.8, q['titulo'], 4.8, CINZA, 'semibold')
        pg.texto(cx + 2.5, cy + 5, br(q['toneladas']), 12, MARCA if destaque else GRAFITE, 'bold')
        pg.texto(cx + cw - 2.5, cy + 6.8, 't', 5.5, CINZA, 'semibold', ha='right')
        if q['detalhe']:
            pg.texto(cx + 2.5, cy + 11.2, q['detalhe'], 5, CINZA)


def _carimbo(pg: Pagina, dados, x, y, w, escala, quadros_linhas):
    texto_tag = f"CORRETIVO · {OPERACOES[dados['operacao']].upper()}"
    tag_w = 1.45 * len(texto_tag) + 4
    pg.ret(x, y, 0.9, 16, MARCA)
    pg.caixa(x + 3, y, tag_w, 3.6, MARCA, MARCA, 0.5, 0.1)
    pg.texto(x + 3 + tag_w / 2, y + 0.5, texto_tag, 4.5, 'white', 'bold', ha='center')
    pg.texto(x + 3, y + 5, f"{dados['cod_faz']} · {dados['nome']}", 12, peso='bold')
    pg.texto(x + 3, y + 11.5, 'MAPA DE APLICAÇÃO · CORRETIVOS · O.S. ' + ', '.join(lista_os(dados)), 5.5, CINZA)
    y += 19
    _quadros(pg, totais_por_produto(dados), x, y, w)
    y += 18 * quadros_linhas
    pg.caixa(x, y, w, 10)
    celula = (w - 14) / 3
    n_talhoes = len(dados['areas'])
    celulas = [('ESCALA', f'1:{escala:,}'.replace(',', '.')),
               (f'ÁREA · {n_talhoes} TALHÕES', f'{br(area_total(dados))} ha'),
               ('SAFRA', safra_de(_data(dados)))]
    for i, (titulo, valor) in enumerate(celulas):
        cx = x + i * celula
        if i:
            pg.ret(cx, y + 1.5, 0.25, 7, LINHA)
        pg.texto(cx + 2.5, y + 1.8, titulo, 4.5, CINZA, 'semibold')
        pg.texto(cx + 2.5, y + 4.8, valor, 7, peso='semibold')
    caixa_norte(pg, x + w - 7, y + 1.3)
    y += 13
    rodape(pg, x, y, w, 'Pedra Agroindustrial S/A · Geotecnologia',
           f"Gerado em {_data(dados):%d/%m/%Y} por {dados.get('gerado_por', '')}")


def _altura_carimbo(dados) -> float:
    rows = max(1, math.ceil(len(totais_por_produto(dados)) / 3))
    return ALTURA_CARIMBO_BASE + 18 * rows


def gerar_pdf(dados: dict, destino) -> str:
    gdf = _gdf(dados)
    orient = orientacao(gdf)
    W, H = (297, 210) if orient == 'paisagem' else (210, 297)
    altura = _altura_carimbo(dados)
    quadros_linhas = (altura - ALTURA_CARIMBO_BASE) // 18
    pg = nova_pagina(W, H)
    if orient == 'paisagem':
        mw = W * 0.63
        escala = _mapa(pg, dados, gdf, M, M, mw, H - 2 * M)
        px, pw = M + mw + 7, W - (M + mw + 7) - M
        _tabela(pg, dados, px, M, pw, H - 2 * M - altura - 6)
        _carimbo(pg, dados, px, H - M - altura, pw, escala, quadros_linhas)
    else:
        mh = H - 2 * M - altura - 8
        escala = _mapa(pg, dados, gdf, M, M, W - 2 * M, mh)
        cw = (W - 2 * M - 8) / 2
        _tabela(pg, dados, M, M + mh + 8, cw, altura)
        _carimbo(pg, dados, M + cw + 8, M + mh + 8, cw, escala, quadros_linhas)
    h_tab = (H - 2 * M - altura - 6) if orient == 'paisagem' else altura
    with PdfPages(destino) as pdf:
        pdf.savefig(pg.fig)
        plt.close(pg.fig)
        if not cabe(len(linhas_tabela(dados)), h_tab - RESERVA_LEGENDA):
            total = ['Total', br(area_total(dados)), '', '', '', '']
            paginas_tabela(pdf, W, H, COLS, linhas_tabela(dados), total, _cabecalho_extra(dados))
    return orient


def gerar_bytes(json_texto: str) -> bytes:
    buffer = io.BytesIO()
    gerar_pdf(json.loads(json_texto), buffer)
    return buffer.getvalue()
