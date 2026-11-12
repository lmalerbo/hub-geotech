"""Itens 4 e 5 (pareado por estacao): drone x projeto x ticks x AgroCAD.
Usa cache/estacoes.pkl (06_estacoes.py). Convencoes:
  - offsets no referencial da linha de projeto (+ = esquerda do sentido do
    desenho da linha); 'faixa' k = passada centrada em 3k m (k=-1,0,+1)
  - sig = +1 se o trator andou no sentido do desenho da linha, -1 se contra;
    multiplicar por sig leva ao referencial de marcha (+ = esquerda do trator)
  - centro da passada no drone = media das 2 linhas de cana da faixa
"""
import pickle, collections
import numpy as np
from lib_geo import *

S = pickle.load(open(os.path.join(CACHE, "estacoes.pkl"), "rb"))
print("estacoes (a cada 2 m nas linhas de orientacao, com drone e ticks a <4,6 m):", len(S))


def drone_faixa(r, k):
    b = [o for o in r["drone"] if 3 * k - 1.5 < o <= 3 * k + 1.5]
    return b


def drone_centro(r, k):
    b = drone_faixa(r, k)
    return np.mean(b) if len(b) == 2 else np.nan


def exec_faixa(lst, k, filtro=lambda x: True):
    b = [x for x in lst if 3 * k - 1.5 < x[0] <= 3 * k + 1.5 and filtro(x)]
    return min(b, key=lambda x: abs(x[0] - 3 * k)) if b else None


# ---------------------------------------------------------------- 4a estrutura do drone
print("\n## 4a. Estrutura das linhas do drone (faixa central de cada estacao)")
cnt = collections.Counter(len(drone_faixa(r, 0)) for r in S)
tot = sum(cnt.values())
print("  linhas de cana dentro de +-1,5 m da linha de orientacao:",
      {k: f"{v} ({100*v/tot:.1f}%)" for k, v in sorted(cnt.items())})
gi, ge = [], []
for r in S:
    rows = [o for o in r["drone"] if -4.5 < o <= 4.5]
    for a, b in zip(rows, rows[1:]):
        (gi if np.floor((a + 1.5) / 3) == np.floor((b + 1.5) / 3) else ge).append(b - a)
print("  hipotese A (as 2 linhas em volta da linha de orientacao sao da mesma passada):")
print("   " + resumo(gi, "vao DENTRO da passada"), "| p5-p95:", np.percentile(gi, [5, 95]).round(3))
print("   " + resumo(ge, "vao ENTRE passadas  "), "| p5-p95:", np.percentile(ge, [5, 95]).round(3))
print("  (vao interno com dispersao ~3x menor => pareamento A correto: a plantadeira faz 2 linhas por passada,"
      " espacamento fixo; o paralelismo aparece no vao entre passadas)")
W = [b[1] - b[0] for b in (drone_faixa(r, 0) for r in S) if len(b) == 2]
lado = [(b[0], b[1]) for b in (drone_faixa(r, 0) for r in S) if len(b) == 2]
lado = np.array(lado)
print("  " + resumo(W, "largura entre as 2 linhas da passada"))
print(f"  linha da direita: mediana {np.median(lado[:,0]):+.3f}; linha da esquerda: mediana {np.median(lado[:,1]):+.3f} (ref. linha de projeto)")

# ---------------------------------------------------------------- 4b/4c posicoes
rec = []
for r in S:
    c0 = drone_centro(r, 0)
    t = exec_faixa(r["tick"], 0)
    a = exec_faixa(r["agro"], 0)
    rec.append((c0, t[0] if t else np.nan, t[1] if t else np.nan, t[2] if t else False,
                a[0] if a else np.nan, a[1] if a else np.nan, r["kur"], -r["ty"], r["tx"]))
R = np.array(rec, float)
c0, ot, sg, doc, oa, sga, kur, nx, ny = R.T
doc = doc.astype(bool)
m = np.isfinite(c0) & np.isfinite(ot)
assoc = m & (np.abs(c0 - ot) < 0.5)
print("\n## 4b. Deslocamento geografico constante (ajuste de dE,dN sobre a normal da linha)")
for nome, v, mm in [("drone - projeto", c0, np.isfinite(c0)), ("ticks - projeto", ot, assoc),
                    ("drone - ticks", c0 - ot, assoc), ("AgroCAD - projeto", oa, assoc & np.isfinite(oa)),
                    ("drone - AgroCAD", c0 - oa, assoc & np.isfinite(oa) & (np.abs(c0 - oa) < 0.5))]:
    N = np.c_[nx[mm], ny[mm]]
    sol, *_ = np.linalg.lstsq(N, v[mm], rcond=None)
    print(f"  {nome:18s}: n={mm.sum():6d} dE={sol[0]:+.3f} dN={sol[1]:+.3f} |d|={np.hypot(*sol):.3f} m")

print("\n## 4c. Posicoes laterais no referencial de MARCHA (+ = esquerda do trator)")
print(f"  estacoes com passada do drone (2 linhas) e tick na faixa central: {m.sum()}; "
      f"destas, tick a <0,5 m do centro do drone ('associadas'): {assoc.sum()} ({100*assoc.sum()/m.sum():.1f}%)")
for nome, v, mm in [("tick - projeto", sg * ot, assoc), ("drone(centro) - projeto", sg * c0, assoc),
                    ("drone(centro) - tick", sg * (c0 - ot), assoc),
                    ("drone(centro) - tick [so ticks documentados]", sg * (c0 - ot), assoc & doc),
                    ("drone(centro) - tick [todas, sem filtro 0,5 m]", sg * (c0 - ot), m),
                    ("AgroCAD - projeto", sga * oa, assoc & np.isfinite(oa)),
                    ("drone(centro) - AgroCAD", sga * (c0 - oa), assoc & np.isfinite(oa) & (np.abs(c0 - oa) < 0.5)),
                    ("AgroCAD - tick", sg * (oa - ot), assoc & np.isfinite(oa) & (np.abs(c0 - oa) < 0.5))]:
    print("  " + resumo(v[mm], nome))
    vv = v[mm]
    print(f"      MAD*1.4826={1.4826*np.median(np.abs(vv-np.median(vv))):.3f}")

print("\n  por curvatura da linha de orientacao no sentido de marcha (+ = curva a esquerda), estacoes associadas:")
kt = sg * kur
Rr = 1 / np.maximum(np.abs(kt), 1e-9)
print(f"   {'faixa de raio':16s} {'n':>5s} | {'tick-proj':>9s} {'drone-proj':>10s} {'drone-tick':>10s} {'AgroCAD-proj':>12s} (medianas, m)")
for lo, hi in [(500, np.inf), (200, 500), (100, 200), (50, 100), (0, 50)]:
    for s_, nm in [(1, "esq"), (-1, "dir")]:
        mm = assoc & (Rr >= lo) & (Rr < hi) & (np.sign(kt) == s_)
        if mm.sum() < 30:
            continue
        ma = mm & np.isfinite(oa)
        print(f"   R {lo:>4}-{hi:<5} {nm} {mm.sum():5d} | {np.median(sg[mm]*ot[mm]):+9.3f} {np.median(sg[mm]*c0[mm]):+10.3f} "
              f"{np.median(sg[mm]*(c0[mm]-ot[mm])):+10.3f} {np.median(sga[ma]*oa[ma]) if ma.sum()>10 else np.nan:+12.3f}")

# ---------------------------------------------------------------- 5 espacamento pareado
print("\n## 5. Espacamento entre passadas adjacentes, pareado na mesma estacao")


def espac(r, fonte, filtro=lambda x: True, assoc_max=None):
    out = []
    cs = [drone_centro(r, k) for k in (-1, 0, 1)]
    xs = []
    for k in (-1, 0, 1):
        if fonte == "drone":
            xs.append(cs[k + 1])
            continue
        e = exec_faixa(r[fonte], k, filtro)
        v = e[0] if e else np.nan
        if assoc_max is not None and not (abs(v - cs[k + 1]) < assoc_max):
            v = np.nan
        xs.append(v)
    return [xs[1] - xs[0], xs[2] - xs[1]]


variantes = [
    ("A. todas as estacoes, linha executada mais proxima da passada", {}, None),
    ("B. so passadas em que o tick/AgroCAD esta a <0,5 m do centro do drone (mesma passada)", {}, 0.5),
    ("C. idem B, so ticks documentados (a <30cm de ponto AgroCAD On)", {"doc": True}, 0.5),
]
res_par = {}
for titulo, opt, am in variantes:
    E = {f: [] for f in ("drone", "tick", "agro")}
    for r in S:
        E["drone"] += espac(r, "drone")
        filt = (lambda x: x[2]) if opt.get("doc") else (lambda x: True)
        E["tick"] += espac(r, "tick", filt, am)
        E["agro"] += espac(r, "agro", assoc_max=am)
    E = {k: np.array(v) for k, v in E.items()}
    print(f"\n  {titulo}")
    for comb in (("drone", "tick"), ("drone", "tick", "agro")):
        mm = np.all([np.isfinite(E[f]) for f in comb], axis=0)
        print(f"   pares com {'+'.join(comb)}: {mm.sum()}")
        for f in comb:
            print(f"    {f:6s} {fmt_cls(classifica(E[f][mm]))}")
        for f in comb[1:]:
            e = E[f][mm] - E["drone"][mm]
            print("    " + resumo(e, f"erro {f}-drone"))
            # concordancia de classe (so amostras validas nos dois)
            def cl(x):
                return np.where(x < 2.6, -9, np.where(x > 3.4, 9, np.where(x < 2.9, -1, np.where(x > 3.1, 1, 0))))
            a, b = cl(E["drone"][mm]), cl(E[f][mm])
            v = (np.abs(a) < 9) & (np.abs(b) < 9)
            print(f"      concordancia de classe {f} x drone (amostras validas nos dois): {100*np.mean(a[v]==b[v]):.1f}% (n={v.sum()})")
            print(f"      correlacao espacamento {f} x drone: {np.corrcoef(E[f][mm][v], E['drone'][mm][v])[0,1]:.3f}")
        res_par[(titulo, comb)] = {f: E[f][mm] for f in comb}
md = np.isfinite(E["drone"])
print(f"\n  drone, todas as estacoes perto de ticks: {fmt_cls(classifica(E['drone'][md]))}")
pickle.dump(res_par, open(os.path.join(CACHE, "espac_pareado.pkl"), "wb"))
