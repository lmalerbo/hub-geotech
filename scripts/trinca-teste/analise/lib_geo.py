"""Funcoes geometricas comuns da analise de validacao (fazenda 10658)."""
import os, sys, pickle
import numpy as np
from scipy.spatial import cKDTree

BASE = r"C:\Users\lmalerbo\Documents\GitHub\base-op"
TT = os.path.join(BASE, "trinca-teste")
OUT = os.path.join(TT, "analise")
CACHE = os.path.join(OUT, "cache")
sys.path.insert(0, os.path.join(BASE, "scripts"))


def carregar():
    g = pickle.load(open(os.path.join(CACHE, "geom.pkl"), "rb"))
    t = np.load(os.path.join(CACHE, "ticks.npz"))
    g["ticks"] = np.c_[t["x"], t["y"]]
    g["ticks_arq"] = t["f"]
    rows = sorted(g["agro_pts"], key=lambda r: r["handle"])
    g["agro_xy"] = np.array([[r["x"], r["y"]] for r in rows])
    g["agro_on"] = np.array([r["status"] == "On" for r in rows])
    g["agro_rows"] = rows
    return g


def comprimento(a):
    return np.hypot(*np.diff(a, axis=0).T).sum() if len(a) > 1 else 0.0


def reamostrar(a, passo):
    """Reamostra polilinha (N,2) a cada `passo` m. Retorna pontos, tangente
    unitaria e abscissa."""
    a = np.asarray(a, float)
    seg = np.hypot(*np.diff(a, axis=0).T)
    keep = np.r_[True, seg > 1e-6]
    a = a[keep]
    if len(a) < 2:
        return np.empty((0, 2)), np.empty((0, 2)), np.empty(0)
    s = np.r_[0, np.cumsum(np.hypot(*np.diff(a, axis=0).T))]
    ss = np.arange(0, s[-1] + 1e-9, passo)
    x = np.interp(ss, s, a[:, 0]); y = np.interp(ss, s, a[:, 1])
    # tangente por diferenca central de +-1 m
    s1 = np.clip(ss - 1.0, 0, s[-1]); s2 = np.clip(ss + 1.0, 0, s[-1])
    tx = np.interp(s2, s, a[:, 0]) - np.interp(s1, s, a[:, 0])
    ty = np.interp(s2, s, a[:, 1]) - np.interp(s1, s, a[:, 1])
    n = np.hypot(tx, ty); n[n == 0] = 1
    return np.c_[x, y], np.c_[tx / n, ty / n], ss


def curvatura(pts, tan, s, janela=5.0):
    """Curvatura assinada (1/m, + = vira a esquerda) pela variacao de rumo em
    +-janela metros."""
    h = np.unwrap(np.arctan2(tan[:, 1], tan[:, 0]))
    s1 = np.clip(s - janela, s[0], s[-1]); s2 = np.clip(s + janela, s[0], s[-1])
    dh = np.interp(s2, s, h) - np.interp(s1, s, h)
    ds = s2 - s1; ds[ds == 0] = np.nan
    return dh / ds


class RefIndex:
    """Indice de amostras densas de um conjunto de polilinhas de referencia."""

    def __init__(self, linhas, passo=0.25, com_curv=False):
        P, Tn, L, K = [], [], [], []
        for i, a in enumerate(linhas):
            p, t, s = reamostrar(a, passo)
            if len(p) < 2:
                continue
            P.append(p); Tn.append(t); L.append(np.full(len(p), i))
            if com_curv:
                K.append(curvatura(p, t, s))
        self.p = np.vstack(P); self.t = np.vstack(Tn); self.lid = np.concatenate(L)
        self.k = np.concatenate(K) if com_curv else None
        self.tree = cKDTree(self.p)

    def offsets(self, q, qdir, raio=4.6, max_ang=10.0, k=64):
        """Para cada ponto q com direcao qdir, retorna listas de (offset
        assinado no referencial de q [+ = esquerda], id da linha, idx amostra)
        das linhas de referencia paralelas dentro de `raio`. Para cada linha,
        so a amostra mais proxima. Offset medido perpendicular a REFERENCIA."""
        cosmax = np.cos(np.radians(max_ang))
        dd, ii = self.tree.query(q, k=k, distance_upper_bound=raio)
        res = []
        for j in range(len(q)):
            best = {}
            for d, i in zip(dd[j], ii[j]):
                if not np.isfinite(d):
                    break
                lid = self.lid[i]
                if lid in best and best[lid][0] <= d:
                    continue
                c = self.t[i] @ qdir[j]
                if abs(c) < cosmax:
                    continue
                best[lid] = (d, i, c)
            out = []
            for lid, (d, i, c) in best.items():
                t = self.t[i] * np.sign(c)  # tangente da ref orientada como q
                v = q[j] - self.p[i]
                # offset da REF em relacao a q, no referencial de q: + = ref a esquerda de q
                off = -(t[0] * v[1] - t[1] * v[0])
                out.append((off, lid, i))
            res.append(out)
        return res


def trilha_ticks(T, passo_min=0.05):
    """Remove ticks parados (repetidos) mantendo a ordem; retorna pontos e
    direcao de marcha (diferenca +-1 m ao longo da trilha) e curvatura."""
    keep = [0]
    for i in range(1, len(T)):
        if np.hypot(*(T[i] - T[keep[-1]])) >= passo_min:
            keep.append(i)
    keep = np.array(keep)
    P = T[keep]
    seg = np.hypot(*np.diff(P, axis=0).T)
    # quebra em saltos > 10 m (mesmo criterio LSFP)
    brk = np.r_[0, np.cumsum(seg > 10)]
    s = np.r_[0, np.cumsum(np.where(seg > 10, 0, seg))]
    D = np.zeros_like(P); K = np.full(len(P), np.nan)
    for b in np.unique(brk):
        m = np.where(brk == b)[0]
        if len(m) < 3:
            continue
        ss = s[m]; x = P[m, 0]; y = P[m, 1]
        s1 = np.clip(ss - 1.0, ss[0], ss[-1]); s2 = np.clip(ss + 1.0, ss[0], ss[-1])
        dx = np.interp(s2, ss, x) - np.interp(s1, ss, x)
        dy = np.interp(s2, ss, y) - np.interp(s1, ss, y)
        n = np.hypot(dx, dy); n[n == 0] = np.nan
        D[m] = np.c_[dx / n, dy / n]
        K[m] = curvatura(P[m], D[m], ss)
    return P, D, K, keep, brk


def resumo(v, nome=""):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    if len(v) == 0:
        return f"{nome}: n=0"
    a = np.abs(v)
    return (f"{nome}: n={len(v)} media={v.mean():+.3f} mediana={np.median(v):+.3f} dp={v.std():.3f} "
            f"|.|p50={np.median(a):.3f} |.|p90={np.percentile(a, 90):.3f} |.|p95={np.percentile(a, 95):.3f}")


def classifica(esp, lo=2.90, hi=3.10, ig_lo=2.60, ig_hi=3.40):
    e = np.asarray(esp, float); e = e[np.isfinite(e)]
    v = e[(e >= ig_lo) & (e <= ig_hi)]
    n = len(v)
    if n == 0:
        return dict(n=0, abaixo=np.nan, ideal=np.nan, acima=np.nan, media=np.nan, n_total=len(e))
    return dict(n=n, abaixo=100 * np.mean(v < lo), ideal=100 * np.mean((v >= lo) & (v <= hi)),
                acima=100 * np.mean(v > hi), media=v.mean(), dp=v.std(), n_total=len(e))


def fmt_cls(c):
    if c["n"] == 0:
        return "n=0"
    return (f"n={c['n']} (de {c['n_total']}) abaixo={c['abaixo']:.1f}% ideal={c['ideal']:.1f}% "
            f"acima={c['acima']:.1f}% media={c['media']:.3f} dp={c['dp']:.3f}")
