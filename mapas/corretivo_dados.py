"""Regras do mapa de corretivos que não dependem de desenho: cores, rótulos, linhas da tabela,
totais por produto e divisão do talhão em faixas (duas ou mais aplicações)."""
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

CORES = {'calcario:dolomitico': '#2f6db5', 'calcario:ph7': '#22a39f', 'fosfato': '#e07b1a', 'blend': '#7b4fb3'}
SEM_APLICACAO = '#e4e7e8'
OPERACOES = {'subsolagem': 'SubSolagem', 'supergrade': 'SuperGrade', 'arado': 'Arado'}
_CALCARIO = {'dolomitico': 'Dolomítico', 'ph7': 'PH7'}


def br(v: float) -> str:
    return f'{v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def chave_cor(ap: dict) -> str:
    return f"calcario:{ap['calcario']}" if ap['tipo'] == 'calcario' else ap['tipo']


def rotulo(ap: dict) -> str:
    if ap['tipo'] == 'calcario':
        return f"Calc. {_CALCARIO[ap['calcario']]}"
    if ap['tipo'] == 'blend':
        return f"Blend · {_CALCARIO[ap['calcario']]}"
    return 'Fosfato'


def _ordenadas(dados) -> list[dict]:
    return sorted(dados['aplicacoes'], key=lambda a: a['ordem'])


def _area(dados, talhao) -> float:
    return float(dados['areas'][str(talhao)]['area_ha'])


def linhas_tabela(dados) -> list[list[str]]:
    linhas = []
    for chave in sorted(dados['areas'], key=int):
        t = int(chave)
        area = _area(dados, t)
        area_txt = br(area) + ('*' if dados['areas'][chave].get('editada') else '')
        aps = [a for a in _ordenadas(dados) if t in a['talhoes']]
        if not aps:
            linhas.append([str(t), area_txt, '—', '', '', ''])
            continue
        primeira = True
        for a in aps:
            cab = [str(t), area_txt] if primeira else ['', '']
            linhas.append(cab + [rotulo(a), br(a['dose']), br(area * a['dose']), a['os']])
            if a['tipo'] == 'blend':
                linhas.append(['', '', '+ Gesso', br(a['dose_gesso']), br(area * a['dose_gesso']), a['os']])
            primeira = False
    return linhas


def totais_por_produto(dados) -> list[dict]:
    soma: dict[str, list[float]] = {}
    for a in _ordenadas(dados):
        area = sum(_area(dados, t) for t in a['talhoes'])
        if a['tipo'] == 'blend':
            titulo = f"Blend {_CALCARIO[a['calcario']]}"
            calc, gesso = soma.setdefault(titulo, [0.0, 0.0])
            soma[titulo] = [calc + area * a['dose'], gesso + area * a['dose_gesso']]
        else:
            titulo = 'Fosfato' if a['tipo'] == 'fosfato' else f"Calcário {_CALCARIO[a['calcario']]}"
            soma.setdefault(titulo, [0.0])
            soma[titulo][0] += area * a['dose']
    ordem = ['Calcário Dolomítico', 'Calcário PH7', 'Fosfato', 'Blend Dolomítico', 'Blend PH7']
    saida = []
    for titulo in ordem:
        if titulo not in soma:
            continue
        v = soma[titulo]
        if titulo.startswith('Blend'):
            saida.append({'titulo': titulo, 'toneladas': round(v[0] + v[1], 2),
                          'detalhe': f'calc. {br(v[0])} t + gesso {br(v[1])} t'})
        else:
            saida.append({'titulo': titulo, 'toneladas': round(v[0], 2), 'detalhe': None})
    return saida


def area_total(dados) -> float:
    return sum(_area(dados, t) for t in dados['areas'])


def lista_os(dados) -> list[str]:
    return sorted({a['os'] for a in dados['aplicacoes']})


def faixas(geom: BaseGeometry, n: int) -> list[BaseGeometry]:
    """Divide o talhão em n faixas diagonais (perpendiculares à direção x+y) de mesma largura."""
    if n <= 1:
        return [geom]
    minx, miny, maxx, maxy = geom.bounds
    # intervalo de x+y pelos vértices (não pelo retângulo envolvente, que deixava faixa vazia); igual a crFaixas na tela
    somas = [x + y for parte in getattr(geom, 'geoms', [geom])
             for anel in [parte.exterior, *parte.interiors] for x, y in anel.coords]
    umin, umax = min(somas), max(somas)
    passo = (umax - umin) / n
    folga = (maxx - minx) + (maxy - miny) + 1
    partes = []
    for i in range(n):
        u0 = umin + i * passo if i else umin - folga
        u1 = umin + (i + 1) * passo if i < n - 1 else umax + folga
        # faixa entre as retas x+y=u0 e x+y=u1, larga o bastante para cobrir o talhão
        faixa = Polygon([(u0 - miny + folga, miny - folga), (u1 - miny + folga, miny - folga),
                         (u1 - maxy - folga, maxy + folga), (u0 - maxy - folga, maxy + folga)])
        partes.append(geom.intersection(faixa))
    return partes
