"""Regras dos Mapas de aplicação que não dependem de desenho: cores, rótulos, linhas da tabela,
totais por produto e divisão do talhão em faixas (duas ou mais aplicações).
Corretivo (subsolagem/supergrade/arado): calcário, fosfato e blend em t/ha.
Aplicação aérea: insumos do cadastro em L/ha ou kg/ha, com margem de 5% (linha do talhão 400 na tabela e
total de cada insumo = dose × área dos talhões dele × 1,05)."""
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

CORES = {'calcario:dolomitico': '#2f6db5', 'calcario:ph7': '#22a39f', 'fosfato': '#e07b1a', 'blend': '#7b4fb3'}
SEM_APLICACAO = '#e4e7e8'
OPERACOES = {'subsolagem': 'SubSolagem', 'supergrade': 'SuperGrade', 'arado': 'Arado', 'aerea': 'Aplicação aérea'}
_CALCARIO = {'dolomitico': 'Dolomítico', 'ph7': 'PH7'}
# Cores dos insumos, dadas na ordem em que aparecem no mapa (igual a CR_PALETA_INSUMOS na tela).
PALETA_INSUMOS = ['#2f6db5', '#e07b1a', '#22a39f', '#7b4fb3', '#c23b3b', '#8a6d1f', '#2e8b57', '#d4558f', '#5b6770', '#b59a00']
MARGEM_AEREA = 0.05
TALHAO_MARGEM = '400'
_UNIDADE = {'L': 'L', 'KG': 'kg'}


def br(v: float) -> str:
    return f'{v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def br_dose(v: float) -> str:
    """Dose com 2 casas, ou 3 quando a terceira importa (0,008 kg/ha)."""
    s = f'{v:,.3f}'
    if s.endswith('0'):
        s = s[:-1]
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')


def aerea(dados) -> bool:
    return dados.get('operacao') == 'aerea'


def nome_insumo(nome: str) -> str:
    """'INSETICIDA BOUVERIZ WP PR' -> 'Inseticida Bouveriz WP PR' (siglas de até 3 letras ficam como estão)."""
    return ' '.join(p if len(p) <= 3 else p.title() for p in str(nome).split())


def unidade(ap: dict) -> str:
    return _UNIDADE[ap['insumo_unidade']] if ap['tipo'] == 'insumo' else 't'


def chave_cor(ap: dict) -> str:
    if ap['tipo'] == 'insumo':
        return f"insumo:{ap['insumo_nome']}"
    return f"calcario:{ap['calcario']}" if ap['tipo'] == 'calcario' else ap['tipo']


def cores_do_mapa(dados) -> dict:
    """chave_cor -> cor. Corretivo: cores fixas; insumo: paleta na ordem em que aparece (repete acima de 10)."""
    cores: dict[str, str] = {}
    for a in _ordenadas(dados):
        k = chave_cor(a)
        if k in cores:
            continue
        if a['tipo'] == 'insumo':
            cores[k] = PALETA_INSUMOS[sum(1 for c in cores if c.startswith('insumo:')) % len(PALETA_INSUMOS)]
        else:
            cores[k] = CORES[k]
    return cores


def rotulo(ap: dict) -> str:
    if ap['tipo'] == 'insumo':
        return nome_insumo(ap['insumo_nome'])
    if ap['tipo'] == 'calcario':
        return f"Calc. {_CALCARIO[ap['calcario']]}"
    if ap['tipo'] == 'blend':
        return f"Blend · {_CALCARIO[ap['calcario']]}"
    return 'Fosfato'


def _ordenadas(dados) -> list[dict]:
    return sorted(dados['aplicacoes'], key=lambda a: a['ordem'])


def _area(dados, talhao) -> float:
    return float(dados['areas'][str(talhao)]['area_ha'])


def margem(dados) -> float:
    """Área do talhão 400 (só no aéreo): 5% da soma das áreas dos talhões do mapa."""
    if not aerea(dados):
        return 0
    return round(sum(_area(dados, t) for t in dados['areas']) * MARGEM_AEREA, 2)


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
            if a['tipo'] == 'insumo':
                un = unidade(a)
                linhas.append(cab + [rotulo(a), f"{br_dose(a['dose'])} {un}", f"{br(area * a['dose'])} {un}", a['os']])
                primeira = False
                continue
            linhas.append(cab + [rotulo(a), br(a['dose']), br(area * a['dose']), a['os']])
            if a['tipo'] == 'blend':
                linhas.append(['', '', '+ Gesso', br(a['dose_gesso']), br(area * a['dose_gesso']), a['os']])
            primeira = False
    if aerea(dados):
        linhas.append([TALHAO_MARGEM, br(margem(dados)), '', '', '', ''])
    return linhas


def totais_por_produto(dados) -> list[dict]:
    if aerea(dados):
        return _totais_insumos(dados)
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
            saida.append({'titulo': titulo, 'total': round(v[0] + v[1], 2), 'unidade': 't',
                          'detalhe': f'calc. {br(v[0])} t + gesso {br(v[1])} t'})
        else:
            saida.append({'titulo': titulo, 'total': round(v[0], 2), 'unidade': 't', 'detalhe': None})
    return saida


def _totais_insumos(dados) -> list[dict]:
    """Um quadro por insumo, na ordem de aparição: dose × área dos talhões dele × 1,05 (somado entre aplicações)."""
    soma: dict[str, list] = {}
    for a in _ordenadas(dados):
        area = sum(_area(dados, t) for t in a['talhoes'])
        q = soma.setdefault(a['insumo_nome'], [0.0, unidade(a)])
        q[0] += area * (1 + MARGEM_AEREA) * a['dose']
    return [{'titulo': nome_insumo(n), 'total': round(v, 2), 'unidade': un, 'detalhe': None} for n, (v, un) in soma.items()]


def area_total(dados) -> float:
    """Soma das áreas dos talhões; no aéreo, com a margem do talhão 400."""
    return round(sum(_area(dados, t) for t in dados['areas']) + margem(dados), 2)


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
