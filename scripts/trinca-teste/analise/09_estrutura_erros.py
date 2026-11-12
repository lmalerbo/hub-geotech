"""Estrutura dos erros:
 (a) desvio tick-projeto: parte constante por passada x variacao dentro da passada
 (b) ruido de alta frequencia (residuo de media movel ~10 m) nos ticks e no AgroCAD
 (c) autocorrelacao ao longo da passada da diferenca drone(centro)-tick
 (d) correlacao da diferenca drone-tick entre passadas VIZINHAS na mesma estacao
     (referencial geografico): alta => erro comum (deformacao do ortomosaico
     ou deriva por declive) que nao afeta o espacamento
 (e) IC 95% (bootstrap por linha de orientacao) das diferencas de %ideal e
     media entre cada fonte e o drone, nas estacoes pareadas (variante B)
"""
import pickle
import numpy as np
from lib_geo import *

rng = np.random.default_rng(0)

# (a) e (b) ticks
tr = np.load(os.path.join(CACHE, "ticks_trilha.npz"))
ag = np.load(os.path.join(CACHE, "agro_trilha.npz"))


def estrutura(nome, dev, trab, brk, minpts):
    seg = np.cumsum(np.r_[1, (np.diff(trab.astype(int)) != 0) | (np.diff(brk) != 0)])
    within, med, hf, resid = [], [], [], []
    for s in np.unique(seg[trab]):
        m = (seg == s) & trab
        if m.sum() < minpts:
            continue
        v = dev[m]
        within.append(v.std()); med.append(np.median(v)); resid.extend(v - np.median(v))
        k = max(5, int(round(minpts / 3)) | 1)
        if len(v) > 3 * k:
            sm = np.convolve(v, np.ones(k) / k, mode="valid")
            hf.extend(v[k // 2:k // 2 + len(sm)] - sm)
    within, med, hf = map(np.array, (within, med, hf))
    print(f"\n## (a/b) {nome}: trechos de trabalho continuos >= ~30 m: {len(within)}")
    print(f"  dp do desvio DENTRO do trecho: mediana {np.median(within):.3f} (p25 {np.percentile(within,25):.3f}, p75 {np.percentile(within,75):.3f})")
    print(f"  desvio mediano POR trecho (m, + = esquerda do sentido de marcha): p5/p25/p50/p75/p95 = {np.percentile(med,[5,25,50,75,95]).round(3)}")
    print(f"  fracao de trechos com |desvio mediano| > 0,15 m: {100*np.mean(np.abs(med)>0.15):.1f}%")
    h, e = np.histogram(dev[trab], bins=np.arange(-0.6, 0.601, 0.02))
    picos = [round(float(e[i] + 0.01), 2) for i in range(1, len(h) - 1) if h[i] >= h[i - 1] and h[i] >= h[i + 1] and h[i] > 0.2 * h.max()]
    print(f"  modas do histograma de desvio (m): {picos}")
    ra = np.abs(np.array(resid))
    print(f"  desvio apos remover a mediana do trecho: |.| p50 {np.median(ra):.3f} p68 {np.percentile(ra,68):.3f} p90 {np.percentile(ra,90):.3f} p95 {np.percentile(ra,95):.3f}")
    print(f"  ruido de alta frequencia (residuo de media movel ~10 m): dp {hf.std():.3f}  MAD*1,48 {1.4826*np.median(np.abs(hf)):.3f}")


brk_t = tr["brk"]
estrutura("ticks .jdl", tr["dev"], tr["trab"], brk_t, 100)
# AgroCAD: ~3 pontos/m tambem (0,34 m entre pontos)
estrutura("AgroCAD", ag["dev"], ag["trab"], np.zeros(len(ag["dev"]), int) if "brk" not in ag else ag["brk"], 90)

# (c) e (d)
S = pickle.load(open(os.path.join(CACHE, "estacoes.pkl"), "rb"))


def dcent(r, k):
    b = [o for o in r["drone"] if 3 * k - 1.5 < o <= 3 * k + 1.5]
    return np.mean(b) if len(b) == 2 else np.nan


def tickk(r, k):
    b = [x for x in r["tick"] if 3 * k - 1.5 < x[0] <= 3 * k + 1.5]
    return min(b, key=lambda x: abs(x[0] - 3 * k)) if b else None


rows = []
viz = []
for r in S:
    vals = {}
    for k in (-1, 0, 1):
        c = dcent(r, k); t = tickk(r, k)
        if t is not None and np.isfinite(c) and abs(c - t[0]) < 0.5:
            vals[k] = (c - t[0], t[1], t[3])
    if 0 in vals:
        rows.append((r["lid"], r["s"], vals[0][1] * vals[0][0], vals[0][2]))
    for k in (-1, 1):
        if 0 in vals and k in vals and vals[0][2] != vals[k][2]:
            viz.append((vals[0][0], vals[k][0], vals[0][1] * vals[k][1]))
A = np.array(rows)
print("\n## (c) autocorrelacao ao longo da passada de [centro drone - tick] (referencial de marcha)")
for lag in (2, 4, 10, 20, 50, 100):
    x, y = [], []
    for lid in np.unique(A[:, 0]):
        a = A[A[:, 0] == lid]
        idx = {round(s): i for i, s in enumerate(a[:, 1])}
        for i, s in enumerate(a[:, 1]):
            j = idx.get(round(s + lag))
            if j is not None and a[i, 3] == a[j, 3]:
                x.append(a[i, 2]); y.append(a[j, 2])
    x, y = np.array(x), np.array(y)
    print(f"  defasagem {lag:3d} m: n={len(x):5d} correlacao={np.corrcoef(x, y)[0,1]:.3f}")
V = np.array(viz)
print("\n## (d) [centro drone - tick] em passadas vizinhas, mesma estacao (referencial geografico)")
for nm, mm in [("todas", np.ones(len(V), bool)), ("sentidos opostos", V[:, 2] < 0), ("mesmo sentido", V[:, 2] > 0)]:
    if mm.sum() > 10:
        print(f"  {nm:16s}: n={mm.sum():5d} correlacao={np.corrcoef(V[mm,0], V[mm,1])[0,1]:.3f}  "
              f"dp(diferenca)={np.std(V[mm,0]-V[mm,1]):.3f} (= erro que o espacamento do executado herda)")

# (e) bootstrap
print("\n## (e) IC 95% bootstrap (reamostrando linhas de orientacao) -- estacoes pareadas, variante B")


def espac_rows(fonte, docreq=False):
    out = []
    for r in S:
        cs = [dcent(r, k) for k in (-1, 0, 1)]
        xs = []
        for k in (-1, 0, 1):
            lst = r[fonte]
            b = [x for x in lst if 3 * k - 1.5 < x[0] <= 3 * k + 1.5 and (not docreq or x[2])]
            v = min(b, key=lambda x: abs(x[0] - 3 * k))[0] if b else np.nan
            if not abs(v - cs[k + 1]) < 0.5:
                v = np.nan
            xs.append(v)
        for i, j in ((0, 1), (1, 2)):
            out.append((r["lid"], cs[j] - cs[i], xs[j] - xs[i]))
    return np.array(out)


def stats(e):
    v = e[(e >= 2.6) & (e <= 3.4)]
    if len(v) == 0:
        return np.nan, np.nan, np.nan, np.nan
    return 100 * np.mean(v < 2.9), 100 * np.mean((v >= 2.9) & (v <= 3.1)), 100 * np.mean(v > 3.1), v.mean()


Tt = espac_rows("tick"); Ta = espac_rows("agro"); Td = espac_rows("tick", True)
for nome, M, other in [("ticks (todos)", Tt, None), ("ticks documentados", Td, None), ("AgroCAD", Ta, None)]:
    for restr, mask in [("so onde a fonte existe", np.isfinite(M[:, 1]) & np.isfinite(M[:, 2])),
                        ("pares com ticks E AgroCAD", np.isfinite(Tt[:, 1]) & np.isfinite(Tt[:, 2]) & np.isfinite(Ta[:, 2]))]:
        X = M[mask]
        lids = np.unique(X[:, 0])
        grupos = {l: X[X[:, 0] == l] for l in lids}
        base = np.array(stats(X[:, 2])) - np.array(stats(X[:, 1]))
        boots = []
        for _ in range(1000):
            amostra = np.vstack([grupos[l] for l in rng.choice(lids, len(lids))])
            boots.append(np.array(stats(amostra[:, 2])) - np.array(stats(amostra[:, 1])))
        B = np.array(boots)
        lo, hi = np.nanpercentile(B, [2.5, 97.5], axis=0)
        sd, sf = stats(X[:, 1]), stats(X[:, 2])
        print(f"  {nome:20s} [{restr}] n={len(X)} pares, {len(lids)} linhas")
        print(f"     drone : abaixo {sd[0]:5.1f}% ideal {sd[1]:5.1f}% acima {sd[2]:5.1f}% media {sd[3]:.3f}")
        print(f"     fonte : abaixo {sf[0]:5.1f}% ideal {sf[1]:5.1f}% acima {sf[2]:5.1f}% media {sf[3]:.3f}")
        print(f"     fonte-drone: abaixo {base[0]:+5.1f} [{lo[0]:+.1f},{hi[0]:+.1f}] ideal {base[1]:+5.1f} [{lo[1]:+.1f},{hi[1]:+.1f}] "
              f"acima {base[2]:+5.1f} [{lo[2]:+.1f},{hi[2]:+.1f}] media {base[3]:+.3f} [{lo[3]:+.3f},{hi[3]:+.3f}]")
