"""
Reimplementacao em Python do fluxo AgroCAD usado pra analise de paralelismo
de linhas executadas em campo: GOIMP -> LSFP -> QBD -> CLE -> PLL.

Ver a documentacao do procedimento original (parametros: LSFP 12m/FIELD,
QBD 160 graus, CLE 15m, PLL ideal 2.90-3.10m / ignorar <2.60 ou >3.40 /
amostragem 10m) e a memoria de projeto `projeto_paralelismo_gs3_rcd_pedra.md`
pro contexto de onde vem os pontos de entrada (export DXF do GOIMP no
AgroCAD, ja que o binario JD-Data/.fdd/EvenByteDelta nao foi decifrado).

O formato de saida do PLL foi validado abrindo um DWG real da Usina da
Pedra ("10003 ANALISE DE PARALELISMO.dwg"): camada `AGROCAD PLL` com um
segmento de 2 pontos por amostra + bloco `tab_espac` com os atributos
Q_AMO/Q_INF/Q_IDE/Q_SUP/P_AMO/P_INF/P_IDE/P_SUP/AVG -- e esse o alvo do
`PLLResultado` abaixo.
"""
import math
from dataclasses import dataclass

from shapely.geometry import LineString, Point
from shapely.ops import nearest_points
from shapely.strtree import STRtree


def lsfp(grouped_points: dict, max_dist: float = 12.0) -> list[LineString]:
    """Conecta pontos consecutivos do mesmo grupo (fazenda/campo/passada,
    equivalente ao atributo FIELD usado pelo AgroCAD) em polilinhas,
    quebrando toda vez que a distancia entre pontos consecutivos ultrapassa
    max_dist. grouped_points: dict[chave_do_grupo] -> lista de (x, y) na
    ordem de gravacao."""
    lines = []
    for pts in grouped_points.values():
        if not pts:
            continue
        current = [pts[0]]
        for prev, cur in zip(pts, pts[1:]):
            if math.dist(prev, cur) > max_dist:
                if len(current) >= 2:
                    lines.append(LineString(current))
                current = [cur]
            else:
                current.append(cur)
        if len(current) >= 2:
            lines.append(LineString(current))
    return lines


def _angulo_interno_graus(a, b, c) -> float:
    """Angulo interno em b, formado pelos segmentos a->b e b->c."""
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        return 180.0
    cos_ang = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(cos_ang))


def qbd(lines: list[LineString], min_angle_deg: float = 160.0) -> list[LineString]:
    """Quebra cada polilinha nos vertices onde o angulo interno for menor
    que min_angle_deg (mudanca de direcao brusca, ex: manobra de cabeceira)."""
    result = []
    for line in lines:
        coords = list(line.coords)
        if len(coords) < 3:
            result.append(line)
            continue
        current = [coords[0]]
        for i in range(1, len(coords) - 1):
            current.append(coords[i])
            if _angulo_interno_graus(coords[i - 1], coords[i], coords[i + 1]) < min_angle_deg:
                if len(current) >= 2:
                    result.append(LineString(current))
                current = [coords[i]]
        current.append(coords[-1])
        if len(current) >= 2:
            result.append(LineString(current))
    return result


def cle(lines: list[LineString], min_length: float = 15.0) -> list[LineString]:
    """Remove polilinhas com comprimento total menor que min_length."""
    return [line for line in lines if line.length >= min_length]


def _perfil_vizinhanca(lines: list[LineString], tree: STRtree, i: int, passo: float,
                       max_angulo: float, colada: float, raio: float) -> tuple[float, float]:
    """(fracao das amostras com vizinha paralela entre `colada` e `raio` m,
    fracao das amostras com vizinha paralela a menos de `colada` m)."""
    line = lines[i]
    n = max(int(line.length // passo), 1)
    apoio = sobreposta = 0
    for k in range(n):
        d = (k + 0.5) * line.length / n
        p = line.interpolate(d)
        a = line.interpolate(max(d - 1.0, 0))
        b = line.interpolate(min(d + 1.0, line.length))
        dx, dy = b.x - a.x, b.y - a.y
        norm = math.hypot(dx, dy)
        if norm == 0:
            continue
        nx, ny = -dy / norm, dx / norm
        raio_perp = LineString([(p.x - nx * raio, p.y - ny * raio), (p.x + nx * raio, p.y + ny * raio)])
        tem_apoio = tem_sobreposta = False
        for j in tree.query(raio_perp):
            if j == i:
                continue
            outra = lines[j]
            inter = raio_perp.intersection(outra)
            if inter.is_empty:
                continue
            q = nearest_points(p, inter)[1]
            s = outra.project(q)
            qa = outra.interpolate(max(s - 1.0, 0))
            qb = outra.interpolate(min(s + 1.0, outra.length))
            ox, oy = qb.x - qa.x, qb.y - qa.y
            onorm = math.hypot(ox, oy)
            if onorm == 0:
                continue
            cos_ang = abs(dx * ox + dy * oy) / (norm * onorm)
            if math.degrees(math.acos(min(1.0, cos_ang))) > max_angulo:
                continue
            if p.distance(q) < colada:
                tem_sobreposta = True
            else:
                tem_apoio = True
        apoio += tem_apoio
        sobreposta += tem_sobreposta
    return apoio / n, sobreposta / n


def _direcao(line: LineString, s: float) -> tuple[float, float]:
    a = line.interpolate(max(s - 1.0, 0))
    b = line.interpolate(min(s + 1.0, line.length))
    return b.x - a.x, b.y - a.y


def _cruza_em_angulo(l1: LineString, l2: LineString, min_angulo: float) -> bool:
    """True se l1 cruza l2 em algum ponto com angulo > min_angulo graus.
    Cruzamento rasante (encontro de passadas em curva de nivel, ponta de
    passada) nao conta."""
    if not l1.crosses(l2):
        return False
    inter = l1.intersection(l2)
    pontos = getattr(inter, "geoms", [inter])
    for g in pontos:
        if g.geom_type != "Point":
            continue
        d1 = _direcao(l1, l1.project(g))
        d2 = _direcao(l2, l2.project(g))
        n = math.hypot(*d1) * math.hypot(*d2)
        if n == 0:
            continue
        cos_ang = abs(d1[0] * d2[0] + d1[1] * d2[1]) / n
        if math.degrees(math.acos(min(1.0, cos_ang))) > min_angulo:
            return True
    return False


def limpar(lines: list[LineString], passo: float = 5.0, max_angulo: float = 15.0,
           colada: float = 1.0, raio: float = 4.5, min_apoio: float = 0.2,
           max_sobreposta: float = 0.5, min_angulo_cruzamento: float = 25.0,
           max_apoio_cruzamento: float = 0.6,
           motivos: dict | None = None) -> list[LineString]:
    """Limpeza depois do CLE, pra tirar o que sobrou de manobra/deslocamento
    (o que o analista apagava na mao no AutoCAD antes do PLL). Linha de
    plantio nao cruza outra linha, nao anda colada em outra e tem vizinha
    paralela a ~1,5-3 m. Entao:
      1. em cada par que se cruza em angulo > `min_angulo_cruzamento`, sai a
         linha com menos apoio paralelo (empate: a mais curta), desde que
         esse apoio seja < `max_apoio_cruzamento` -- em curva de nivel duas
         passadas boas as vezes se encostam na ponta, e essas ficam;
      2. sai a linha com mais de `max_sobreposta` do comprimento a menos de
         `colada` m de outra paralela (passada repetida por cima), se for a
         mais curta do par;
      3. sai a linha com menos de `min_apoio` do comprimento com vizinha
         paralela (deslocamento solto na borda)."""
    linhas = list(lines)
    if len(linhas) < 2:
        return linhas
    tree = STRtree(linhas)
    perfil = [_perfil_vizinhanca(linhas, tree, i, passo, max_angulo, colada, raio) for i in range(len(linhas))]
    nota = [(perfil[i][0], linhas[i].length) for i in range(len(linhas))]
    fora = set()

    # 1. cruzamentos -- da pior pra melhor, pra que uma linha ruim que cruza
    # varias boas saia antes de derrubar alguma delas
    for i in sorted(range(len(linhas)), key=lambda k: nota[k]):
        if i in fora:
            continue
        for j in tree.query(linhas[i]):
            if j == i or j in fora or not _cruza_em_angulo(linhas[i], linhas[j], min_angulo_cruzamento):
                continue
            k = i if nota[i] <= nota[j] else j
            if perfil[k][0] >= max_apoio_cruzamento:
                continue  # as duas sao passadas boas que se encostam numa ponta
            fora.add(k)
            if motivos is not None:
                motivos[k] = "cruza"
            if i in fora:
                break

    # 2. passada repetida por cima de outra
    for i in sorted(range(len(linhas)), key=lambda k: linhas[k].length):
        if i in fora or perfil[i][1] <= max_sobreposta:
            continue
        perto = linhas[i].buffer(colada)
        if any(j != i and j not in fora and linhas[j].length >= linhas[i].length
               and linhas[j].intersects(perto) for j in tree.query(perto)):
            fora.add(i)
            if motivos is not None:
                motivos[i] = "sobreposta"

    # 3. sem vizinha paralela
    for i in range(len(linhas)):
        if i not in fora and perfil[i][0] < min_apoio:
            fora.add(i)
            if motivos is not None:
                motivos[i] = "isolada"
    return [l for k, l in enumerate(linhas) if k not in fora]


@dataclass
class PLLResultado:
    total_amostras: int
    abaixo: int
    ideais: int
    acima: int
    espacamento_medio: float
    ideal_min: float
    ideal_max: float

    @property
    def pct_abaixo(self) -> float:
        return 100.0 * self.abaixo / self.total_amostras if self.total_amostras else 0.0

    @property
    def pct_ideal(self) -> float:
        return 100.0 * self.ideais / self.total_amostras if self.total_amostras else 0.0

    @property
    def pct_acima(self) -> float:
        return 100.0 * self.acima / self.total_amostras if self.total_amostras else 0.0

    def resumo(self) -> str:
        return (
            f"RESUMO DA ANALISE VETORIAL DE PARALELISMO\n"
            f"  amostras: {self.total_amostras} (100.0%)\n"
            f"  inferiores a {self.ideal_min:.2f}: {self.abaixo} ({self.pct_abaixo:.2f}%)\n"
            f"  ideais {self.ideal_min:.2f}-{self.ideal_max:.2f}: {self.ideais} ({self.pct_ideal:.2f}%)\n"
            f"  superiores a {self.ideal_max:.2f}: {self.acima} ({self.pct_acima:.2f}%)\n"
            f"  espacamento medio entre as linhas: {self.espacamento_medio:.2f}"
        )


def pll(
    lines: list[LineString],
    ideal_min: float = 2.90,
    ideal_max: float = 3.10,
    ignore_below: float = 2.60,
    ignore_above: float = 3.40,
    sample_interval: float = 10.0,
    max_angulo_vizinha: float = 15.0,
) -> PLLResultado:
    """Resumo do PLL -- ver pll_amostras."""
    espacamentos = [a.espacamento for a in pll_amostras(lines, ignore_below, ignore_above,
                                                         sample_interval, max_angulo_vizinha)]
    abaixo = sum(1 for e in espacamentos if e < ideal_min)
    ideais = sum(1 for e in espacamentos if ideal_min <= e <= ideal_max)
    acima = sum(1 for e in espacamentos if e > ideal_max)
    media = sum(espacamentos) / len(espacamentos) if espacamentos else 0.0
    return PLLResultado(len(espacamentos), abaixo, ideais, acima, media, ideal_min, ideal_max)


@dataclass
class Amostra:
    linha: int          # indice da linha amostrada em `lines`
    x: float            # ponto amostrado na linha
    y: float
    x_vizinha: float    # ponto correspondente na linha vizinha
    y_vizinha: float
    espacamento: float


def pll_amostras(
    lines: list[LineString],
    ignore_below: float = 2.60,
    ignore_above: float = 3.40,
    sample_interval: float = 10.0,
    max_angulo_vizinha: float = 15.0,
) -> list[Amostra]:
    """Amostra cada linha a cada sample_interval metros; em cada amostra,
    lanca uma perpendicular a direcao local da linha e mede, em CADA lado, a
    distancia ate a linha vizinha mais proxima -- cada lado e uma amostra.
    (Ficar so com o menor dos dois lados enviesava a media pra baixo: validado
    contra o PLL do AgroCAD na fazenda 10233, media 2,94 -> 3,00.)
    So conta como vizinha uma linha cuja direcao local no cruzamento difere
    no maximo max_angulo_vizinha graus -- senao um trecho de manobra cruzando
    em angulo vira um "espacamento" sem sentido.
    Devolve so as amostras dentro de [ignore_below, ignore_above] (as de fora
    nao entram no total), com a posicao de cada uma."""
    search_radius = ignore_above * 1.5
    tree = STRtree(lines)
    amostras = []

    for i, line in enumerate(lines):
        length = line.length
        n_samples = int(length // sample_interval)
        for s in range(1, n_samples + 1):
            d = s * sample_interval
            if d >= length:
                continue
            p = line.interpolate(d)
            p_antes = line.interpolate(max(d - 0.5, 0))
            p_depois = line.interpolate(min(d + 0.5, length))
            dx, dy = p_depois.x - p_antes.x, p_depois.y - p_antes.y
            norm = math.hypot(dx, dy)
            if norm == 0:
                continue
            nx, ny = -dy / norm, dx / norm  # direcao perpendicular

            melhor_por_lado = {}
            for j in tree.query(p.buffer(search_radius)):
                if j == i:
                    continue
                outra = lines[j]
                for sinal in (1, -1):
                    alvo = Point(p.x + sinal * nx * search_radius, p.y + sinal * ny * search_radius)
                    inter = LineString([p, alvo]).intersection(outra)
                    if inter.is_empty:
                        continue
                    q = nearest_points(p, inter)[1]
                    s = outra.project(q)
                    q_antes = outra.interpolate(max(s - 0.5, 0))
                    q_depois = outra.interpolate(min(s + 0.5, outra.length))
                    ox, oy = q_depois.x - q_antes.x, q_depois.y - q_antes.y
                    onorm = math.hypot(ox, oy)
                    if onorm == 0:
                        continue
                    cos_ang = abs(dx * ox + dy * oy) / (norm * onorm)
                    if math.degrees(math.acos(min(1.0, cos_ang))) > max_angulo_vizinha:
                        continue
                    dist = p.distance(q)
                    if dist < melhor_por_lado.get(sinal, (math.inf,))[0]:
                        melhor_por_lado[sinal] = (dist, q)
            for dist, q in melhor_por_lado.values():
                if ignore_below <= dist <= ignore_above:
                    amostras.append(Amostra(i, p.x, p.y, q.x, q.y, dist))

    return amostras


def analisar(
    grouped_points: dict,
    lsfp_max_dist: float = 12.0,
    qbd_min_angle: float = 160.0,
    cle_min_length: float = 15.0,
    pll_ideal_min: float = 2.90,
    pll_ideal_max: float = 3.10,
    pll_ignore_below: float = 2.60,
    pll_ignore_above: float = 3.40,
    pll_sample_interval: float = 10.0,
) -> PLLResultado:
    """Roda o fluxo completo LSFP -> QBD -> CLE -> limpar -> PLL."""
    linhas = lsfp(grouped_points, max_dist=lsfp_max_dist)
    linhas = qbd(linhas, min_angle_deg=qbd_min_angle)
    linhas = cle(linhas, min_length=cle_min_length)
    linhas = limpar(linhas)
    return pll(
        linhas,
        ideal_min=pll_ideal_min,
        ideal_max=pll_ideal_max,
        ignore_below=pll_ignore_below,
        ignore_above=pll_ignore_above,
        sample_interval=pll_sample_interval,
    )


if __name__ == "__main__":
    import random

    random.seed(42)

    # dados sinteticos: 8 passadas paralelas de ~150m, espacadas 3.00m +-
    # ruido pequeno, cada uma com um trecho de manobra em angulo fechado no
    # final (deve ser cortado pelo QBD) e um fragmento solto de <15m
    # (deve ser removido pelo CLE).
    grouped = {}
    n_passadas = 8
    comprimento = 150.0
    espacamento_nominal = 3.00
    passo = 2.0  # distancia entre pontos gravados

    for k in range(n_passadas):
        y0 = k * espacamento_nominal
        pts = []
        d = 0.0
        while d <= comprimento:
            ruido = random.uniform(-0.05, 0.05)
            pts.append((d, y0 + ruido))
            d += passo
        # manobra de cabeceira: vira quase 90 graus no fim da passada
        ultimo = pts[-1]
        pts.append((ultimo[0] + 3.0, ultimo[1] + 3.0))
        pts.append((ultimo[0] + 3.0, ultimo[1] + 8.0))
        grouped[f"passada_{k}"] = pts

    # fragmento solto (< 15m), simula ruido/residuo de processamento
    grouped["fragmento_residual"] = [(50.0, 100.0), (52.0, 101.0), (53.5, 101.8)]

    resultado = analisar(grouped)
    print(resultado.resumo())
