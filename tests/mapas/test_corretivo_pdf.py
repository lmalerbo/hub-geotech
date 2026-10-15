import json

import pytest
from shapely.geometry import box, mapping
from shapely.ops import transform
from pyproj import Transformer

from mapas.corretivo_pdf import gerar_bytes, gerar_pdf

pymupdf = pytest.importorskip('pymupdf')
PARA_4326 = Transformer.from_crs(31983, 4326, always_xy=True).transform


def _geo(n, largura=100):
    feats = [{'type': 'Feature', 'properties': {'talhao': i + 1},
              'geometry': mapping(transform(PARA_4326, box(300000 + i * (largura + 20), 7600000,
                                                           300000 + i * (largura + 20) + largura, 7600000 + 300)))}
             for i in range(n)]
    return {'type': 'FeatureCollection', 'features': feats}


def _dados(n=5, aplicacoes=None, sem_geo=()):
    geo = _geo(n)
    geo['features'] = [f for f in geo['features'] if f['properties']['talhao'] not in sem_geo]
    return {'cod_faz': 10156, 'nome': 'FAZENDA TESTE', 'operacao': 'subsolagem', 'data': '2026-10-15',
            'gerado_por': 'Ana', 'talhoes_geo': geo,
            'areas': {str(i + 1): {'area_ha': 10.0 + i, 'editada': i == 3} for i in range(n)},
            'aplicacoes': aplicacoes or [
                {'tipo': 'calcario', 'calcario': 'dolomitico', 'dose': 2.0, 'dose_gesso': None, 'os': '4520',
                 'ordem': 1, 'talhoes': [1, 3]},
                {'tipo': 'fosfato', 'calcario': None, 'dose': 0.5, 'dose_gesso': None, 'os': '4521', 'ordem': 2,
                 'talhoes': [2, 3]},
                {'tipo': 'blend', 'calcario': 'dolomitico', 'dose': 1.5, 'dose_gesso': 1.0, 'os': '4530',
                 'ordem': 3, 'talhoes': [4, 5]}]}


def _texto(caminho):
    doc = pymupdf.open(caminho)
    return len(doc), '\n'.join(p.get_text() for p in doc)


def test_pdf_basico(tmp_path):
    destino = tmp_path / 'c.pdf'
    gerar_pdf(_dados(), destino)
    paginas, texto = _texto(destino)
    assert paginas == 1
    for esperado in ['CORRETIVO · SUBSOLAGEM', '10156 · FAZENDA TESTE', 'O.S. 4520, 4521, 4530',
                     'Calcário Dolomítico', 'Fosfato', 'Blend Dolomítico', 'calc. 40,50 t + gesso 27,00 t',
                     'Blend · Dolomítico', '+ Gesso', '13,00*', 'Gerado em 15/10/2026 por Ana']:
        assert esperado in texto, esperado
    assert 'Rev' not in texto


def test_gerar_bytes_igual_ao_arquivo(tmp_path):
    b = gerar_bytes(json.dumps(_dados()))
    assert b.startswith(b'%PDF')


def test_pdf_talhao_sem_geometria(tmp_path):
    destino = tmp_path / 'c.pdf'
    gerar_pdf(_dados(sem_geo=(2,)), destino)
    _, texto = _texto(destino)
    assert '11,00' in texto            # área do talhão 2 continua na tabela


def test_pdf_muitas_linhas_pagina_extra(tmp_path):
    n = 60
    aps = [{'tipo': 'calcario', 'calcario': 'ph7', 'dose': 1.0, 'dose_gesso': None, 'os': '1', 'ordem': 1,
            'talhoes': list(range(1, n + 1))},
           {'tipo': 'blend', 'calcario': 'ph7', 'dose': 1.0, 'dose_gesso': 0.5, 'os': '2', 'ordem': 2,
            'talhoes': list(range(1, n + 1))}]
    destino = tmp_path / 'c.pdf'
    gerar_pdf(_dados(n, aps), destino)
    paginas, texto = _texto(destino)
    assert paginas >= 2
    assert 'CORRETIVO · SUBSOLAGEM' in texto and 'Blend PH7' in texto


def test_tres_aplicacoes_no_mesmo_talhao(tmp_path):
    aps = [{'tipo': t, 'calcario': c, 'dose': 1.0, 'dose_gesso': g, 'os': str(i), 'ordem': i, 'talhoes': [1]}
           for i, (t, c, g) in enumerate([('calcario', 'dolomitico', None), ('fosfato', None, None),
                                          ('blend', 'ph7', 1.0)], 1)]
    destino = tmp_path / 'c.pdf'
    gerar_pdf(_dados(1, aps), destino)
    assert _texto(destino)[0] == 1


def test_nome_longo_cabe_na_pagina(tmp_path):
    aps = [{'tipo': 'calcario', 'calcario': 'dolomitico', 'dose': 2.0, 'dose_gesso': None, 'os': '4520',
            'ordem': 1, 'talhoes': [1, 2, 3]}]
    dados = _dados(3, aps)
    vertical = {'type': 'FeatureCollection', 'features': []}
    for i in range(3):
        y0 = 7600000 + i * 320
        geom = box(300000, y0, 300300, y0 + 300)
        vertical['features'].append({'type': 'Feature', 'properties': {'talhao': i + 1},
                                     'geometry': mapping(transform(PARA_4326, geom))})
    dados['talhoes_geo'] = vertical
    dados['cod_faz'] = 10372
    dados['nome'] = 'FAZENDA SANTA RITA DO PASSA QUATRO'
    destino = tmp_path / 'c.pdf'
    assert gerar_pdf(dados, destino) == 'retrato'
    doc = pymupdf.open(destino)
    page = doc[0]
    limite = page.rect.width - 8
    for palavra in ['10372', 'QUATRO']:
        rects = page.search_for(palavra)
        assert rects, palavra
        assert all(r.x1 <= limite for r in rects), (palavra, [r.x1 for r in rects], limite)


def test_legenda_blend_unico(tmp_path):
    from mapas.corretivo_dados import linhas_tabela
    aps = [{'tipo': 'calcario', 'calcario': 'dolomitico', 'dose': 2.0, 'dose_gesso': None, 'os': '4520',
            'ordem': 1, 'talhoes': [1, 3]},
           {'tipo': 'blend', 'calcario': 'dolomitico', 'dose': 1.5, 'dose_gesso': 1.0, 'os': '4530',
            'ordem': 2, 'talhoes': [4, 5]},
           {'tipo': 'blend', 'calcario': 'ph7', 'dose': 1.0, 'dose_gesso': 0.5, 'os': '4531',
            'ordem': 3, 'talhoes': [1, 2]}]
    dados = _dados(5, aps)
    destino = tmp_path / 'c.pdf'
    gerar_pdf(dados, destino)
    _, texto = _texto(destino)
    linhas = linhas_tabela(dados)
    for rot in ['Blend · Dolomítico', 'Blend · PH7']:
        esperado = sum(1 for l in linhas if rot in l)
        assert texto.count(rot) == esperado, rot
    assert 'Blend' in texto
