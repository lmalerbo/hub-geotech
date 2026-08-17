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
) -> PLLResultado:
    """Amostra cada linha a cada sample_interval metros; em cada amostra,
    lanca uma perpendicular a direcao local da linha (nos dois sentidos) e
    mede a distancia ate a linha vizinha mais proxima nessa direcao.
    Classifica o espacamento e ignora amostras fora de
    [ignore_below, ignore_above] (nao entram no total)."""
    search_radius = ignore_above * 1.5
    tree = STRtree(lines)
    espacamentos = []

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

            melhor_dist = None
            for j in tree.query(p.buffer(search_radius)):
                if j == i:
                    continue
                outra = lines[j]
                for sinal in (1, -1):
                    alvo = Point(p.x + sinal * nx * search_radius, p.y + sinal * ny * search_radius)
                    inter = LineString([p, alvo]).intersection(outra)
                    if inter.is_empty:
                        continue
                    dist = p.distance(inter)
                    if melhor_dist is None or dist < melhor_dist:
                        melhor_dist = dist
            if melhor_dist is not None:
                espacamentos.append(melhor_dist)

    validos = [e for e in espacamentos if ignore_below <= e <= ignore_above]
    abaixo = sum(1 for e in validos if e < ideal_min)
    ideais = sum(1 for e in validos if ideal_min <= e <= ideal_max)
    acima = sum(1 for e in validos if e > ideal_max)
    media = sum(validos) / len(validos) if validos else 0.0

    return PLLResultado(len(validos), abaixo, ideais, acima, media, ideal_min, ideal_max)


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
    """Roda o fluxo completo LSFP -> QBD -> CLE -> PLL."""
    linhas = lsfp(grouped_points, max_dist=lsfp_max_dist)
    linhas = qbd(linhas, min_angle_deg=qbd_min_angle)
    linhas = cle(linhas, min_length=cle_min_length)
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
