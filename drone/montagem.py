"""Projeto Normal por talhão (spec Parte 2, §4.1): a revisão nova parte da vigente,
troca os talhões incluídos/refeitos, tira os removidos e copia o resto."""
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid

from drone.erros import ErroGeracao
from drone.geometria import so_poligonos

MINIMO_M2 = 1.0


def _item(geom, origem, desde_rev):
    return {'geom': geom, 'area_ha': geom.area / 1e4, 'origem': origem, 'desde_rev': desde_rev}


def _base(talhoes) -> dict:
    return {int(t['TALHAO']): make_valid(t.geometry) for _, t in talhoes.iterrows()}


def dividir_por_talhao(area, talhoes, origem, desde_rev) -> dict:
    itens = {}
    for n, g in _base(talhoes).items():
        p = so_poligonos(make_valid(area.intersection(g)))
        if p.area >= MINIMO_M2:
            itens[n] = _item(p, origem, desde_rev)
    return itens


def montar_normal(vigentes, escopo, talhoes, buffers, ajuste, nova_rev, avisos=None) -> dict:
    base = _base(talhoes)
    if escopo is None:                                   # CLI / pedido antigo: fazenda inteira pelo sistema
        escopo = {'incluir': [{'talhao': n, 'fonte': 'sistema'} for n in base], 'remover': []}
    incluir = escopo.get('incluir') or []
    remover = {int(x) for x in escopo.get('remover') or []}
    faltando = sorted(int(i['talhao']) for i in incluir if int(i['talhao']) not in base)
    if faltando:
        raise ErroGeracao(f"Talhões que não existem na Base de hoje: {', '.join(map(str, faltando))}.")
    itens = {k: v for k, v in vigentes.items() if k not in remover}
    nao_estavam = sorted(remover - set(vigentes))
    if nao_estavam and avisos is not None:
        avisos.append('Talhões marcados para remover que não estavam no projeto: '
                      + ', '.join(map(str, nao_estavam)) + '.')
    shape = unary_union([make_valid(g) for g in ajuste]) if ajuste else None
    vazios, tomados = [], []
    for i in incluir:
        n, fonte = int(i['talhao']), i.get('fonte', 'sistema')
        if fonte == 'shape':
            if shape is None:
                raise ErroGeracao('Há talhões em "subir shape", mas nenhum shape de ajuste foi enviado.')
            p = so_poligonos(make_valid(shape.intersection(base[n])))
        else:
            p = so_poligonos(make_valid(base[n].difference(buffers)))
        if p.area < MINIMO_M2:
            (vazios if fonte == 'shape' else tomados).append(n)   # sistema: obstáculo toma o talhão todo
            continue
        itens[n] = _item(p, fonte, nova_rev)
    if vazios:
        raise ErroGeracao('O shape enviado não cobre os talhões ' + ', '.join(map(str, sorted(vazios))) + '.')
    if tomados and avisos is not None:
        avisos.append('Talhões sem área de aplicação (os obstáculos tomam o talhão inteiro), ficaram fora: '
                      + ', '.join(map(str, sorted(tomados))) + '.')
    if not itens:
        raise ErroGeracao('A área de aplicação ficou vazia: o projeto ficaria sem nenhum talhão.')
    return itens


def uniao(itens):
    return so_poligonos(make_valid(unary_union([v['geom'] for v in itens.values()])))


def cobertura(itens, talhoes) -> float:
    base = _base(talhoes)
    total = sum(g.area for g in base.values())
    coberta = sum(g.area for n, g in base.items() if n in itens)
    return 100 * coberta / total if total else 0.0


def fora_da_base(itens, talhoes) -> list:
    return sorted(set(itens) - set(_base(talhoes)))


def _multi(g):
    return MultiPolygon([g]) if isinstance(g, Polygon) else g


def itens_para_json(itens) -> list:
    return [{'talhao': n, 'wkt': _multi(v['geom']).wkt, 'area_ha': round(v['area_ha'], 4),
             'origem': v['origem'], 'desde_rev': v['desde_rev']} for n, v in sorted(itens.items())]
