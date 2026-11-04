"""
Separa os ticks de plantio (produtivo) dos de manobra, cabeceira, estrada e
trator parado.

O .jdl (telemetria JDLink) nao traz o WorkStatus da plantadeira por tick --
foi procurado em todos os itens do campo 9 usando o executado do AgroCAD da
10658 (pontos On/Off com data/hora) como gabarito. Entao o filtro combina:

  - velocidade em janela de +-1s entre VEL_MIN e VEL_MAX (tira parado e estrada);
  - mudanca de rumo em +-15m <= CURVA_15M e em +-5m <= CURVA_5M (tira
    cabeceira e lacos de manobra, deixa passar curva de nivel suave);
  - estado 0/1 do registro (jdl_rich_fields.estado_trabalho), com folga de um
    registro pra cada lado pra nao cortar inicio/fim de passada.

Na 10658 (gabarito por tempo+posicao): sem filtro 23% dos ticks sao plantio;
com o filtro, ~88% dos ticks mantidos sao plantio e ~91% do plantio e mantido.
"""
import numpy as np

VEL_MIN = 0.8      # m/s (~3 km/h)
VEL_MAX = 2.5      # m/s (~9 km/h)
CURVA_15M = 30.0   # graus
CURVA_5M = 12.0    # graus
SALTO_MAX = 5.0    # m entre ticks consecutivos -> trechos independentes
DT_TICK = 0.2      # s


def _mudanca_rumo(xy: np.ndarray, s: np.ndarray, raio: float) -> np.ndarray:
    """Angulo (graus) entre o rumo dos `raio` m anteriores e dos `raio` m
    seguintes. 180 onde o trecho nao tem distancia suficiente dos dois lados."""
    n = len(xy)
    jb = np.clip(np.searchsorted(s, s - raio), 0, n - 1)
    jf = np.clip(np.searchsorted(s, s + raio, side="right") - 1, 0, n - 1)
    a = xy - xy[jb]
    b = xy[jf] - xy
    h1 = np.arctan2(a[:, 1], a[:, 0])
    h2 = np.arctan2(b[:, 1], b[:, 0])
    ang = np.degrees(np.abs((h2 - h1 + np.pi) % (2 * np.pi) - np.pi))
    ok = (s - s[jb] > 0.8 * raio) & (s[jf] - s > 0.8 * raio)
    return np.where(ok, ang, 180.0)


def _mascara_trecho(xy: np.ndarray) -> np.ndarray:
    n = len(xy)
    if n < 3:
        return np.zeros(n, bool)
    s = np.r_[0.0, np.cumsum(np.hypot(*np.diff(xy, axis=0).T))]
    k = 5
    i0 = np.clip(np.arange(n) - k, 0, n - 1)
    i1 = np.clip(np.arange(n) + k, 0, n - 1)
    vel = (s[i1] - s[i0]) / np.maximum((i1 - i0) * DT_TICK, DT_TICK)
    return ((vel >= VEL_MIN) & (vel <= VEL_MAX)
            & (_mudanca_rumo(xy, s, 15.0) <= CURVA_15M)
            & (_mudanca_rumo(xy, s, 5.0) <= CURVA_5M))


def mascara_produtiva(xy: np.ndarray, estado: np.ndarray | None = None) -> np.ndarray:
    """xy: (n, 2) em metros (UTM), na ordem de gravacao de UM arquivo/sessao.
    estado: (n,) com o estado do registro de cada tick ja dilatado (0 = fora,
    1 = trabalhando, -1 = desconhecido) ou None pra usar so geometria."""
    xy = np.asarray(xy, float)
    n = len(xy)
    mask = np.zeros(n, bool)
    if n == 0:
        return mask
    saltos = np.flatnonzero(np.hypot(*np.diff(xy, axis=0).T) > SALTO_MAX) + 1
    for a, b in zip(np.r_[0, saltos], np.r_[saltos, n]):
        mask[a:b] = _mascara_trecho(xy[a:b])
    if estado is not None:
        mask &= np.asarray(estado) != 0
    return mask


def dilatar_estado(estados: list[int | None]) -> list[int]:
    """Estado por registro -> 1 se ele ou um vizinho imediato for 1; 0 se o
    proprio for 0; -1 se desconhecido."""
    out = []
    for i, e in enumerate(estados):
        viz = estados[max(i - 1, 0):i + 2]
        if 1 in viz:
            out.append(1)
        elif e == 0:
            out.append(0)
        else:
            out.append(-1)
    return out
