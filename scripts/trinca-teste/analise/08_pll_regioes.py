"""Item 5 com o PLL 'oficial' (nosso paralelismo_pipeline.pll, LSFP 10 /
QBD 160 / CLE 10 / PLL 10) aplicado a cada fonte, recortada na mesma regiao.
Fontes:
  - ticks .jdl (pipeline atual, todos os ticks)
  - ticks documentados (so os a <30cm de ponto AgroCAD On)
  - AgroCAD: polilinhas do proprio executado.dwg / nosso LSFP nos FIELD_POINTS
  - drone: linhas de CENTRO DE PASSADA reconstruidas (media das 2 linhas de
    cana em volta de cada linha de orientacao, a cada 2 m)
  - projeto
Regioes:
  R1 = passadas plantadas por este trator e vistas pelo drone (estacoes em que
       o tick esta a <0,5 m do centro da passada do drone), buffer 2 m
  R2 = R1 ∩ cobertura AgroCAD
  R0 = toda a area do drone (so drone e projeto)
"""
import pickle, time
import numpy as np
from shapely.geometry import LineString, MultiLineString, Point
from shapely import union_all
from lib_geo import *
from paralelismo_pipeline import pll

g = carregar()
Lk = pickle.load(open(os.path.join(CACHE, "linhas.pkl"), "rb"))
S = pickle.load(open(os.path.join(CACHE, "estacoes.pkl"), "rb"))

# ---- linhas de centro de passada do drone (campo todo)
cl_cache = os.path.join(CACHE, "drone_centro.pkl")
if not os.path.exists(cl_cache):
    ref_dr = RefIndex(g["drone"], passo=0.5)
    centro_lines = []
    for li, a in enumerate(g["projeto"]):
        p, t, s = reamostrar(a, 2.0)
        if len(p) < 3:
            continue
        near = ref_dr.tree.query(p, distance_upper_bound=1.6)[0] < np.inf
        idx = np.where(near)[0]
        if len(idx) == 0:
            continue
        od = ref_dr.offsets(p[idx], t[idx], raio=1.6, max_ang=10, k=120)
        cur = []
        last = None
        for j, offs in zip(idx, od):
            b = sorted(o for o, _, _ in offs if -1.5 < o <= 1.5)
            ok = len(b) == 2 and 1.2 < b[1] - b[0] < 1.8
            if ok:
                c = np.mean(b)
                n = np.array([-t[j, 1], t[j, 0]])
                pt = tuple(p[j] + c * n)
                if last is not None and j != last + 1 and len(cur) >= 2:
                    centro_lines.append(LineString(cur)); cur = []
                elif last is not None and j != last + 1:
                    cur = []
                cur.append(pt); last = j
        if len(cur) >= 2:
            centro_lines.append(LineString(cur))
    pickle.dump(centro_lines, open(cl_cache, "wb"))
centro_lines = pickle.load(open(cl_cache, "rb"))
centro_lines = [l for l in centro_lines if l.length >= 10]
print(f"linhas de centro de passada do drone: {len(centro_lines)}, {sum(l.length for l in centro_lines)/1000:.1f} km")

# ---- regioes
def dc(r):
    b = [o for o in r["drone"] if -1.5 < o <= 1.5]
    return np.mean(b) if len(b) == 2 else np.nan
pts1, pts2 = [], []
for r in S:
    c = dc(r)
    t = [x for x in r["tick"] if -1.5 < x[0] <= 1.5]
    if not np.isfinite(c) or not t:
        continue
    o = min(t, key=lambda x: abs(x[0]))[0]
    if abs(c - o) < 0.5:
        pts1.append(Point(r["x"], r["y"]))
        a = [x for x in r["agro"] if -1.5 < x[0] <= 1.5]
        if a and abs(c - min(a, key=lambda x: abs(x[0]))[0]) < 0.5:
            pts2.append(Point(r["x"], r["y"]))
R1 = union_all([p.buffer(2.0, quad_segs=2) for p in pts1]).buffer(1.0).buffer(-1.0)
R2 = union_all([p.buffer(2.0, quad_segs=2) for p in pts2]).buffer(1.0).buffer(-1.0)
R0 = Lk["cov"]["drone"]
print(f"R1 (este trator + drone): {R1.area/1e4:.2f} ha | R2 (R1 com AgroCAD): {R2.area/1e4:.2f} ha | R0 (drone): {R0.area/1e4:.1f} ha")


def recorta(lines, R, minlen=10.0):
    out = []
    for l in lines:
        if not l.intersects(R):
            continue
        x = l.intersection(R)
        for gg in getattr(x, "geoms", [x]):
            if gg.geom_type == "LineString" and gg.length >= minlen:
                out.append(gg)
    return out


fontes = {
    "ticks .jdl (pipeline atual)": Lk["tick_lines"],
    "ticks documentados": Lk["tick_doc_lines"],
    "AgroCAD (polilinhas do executado.dwg)": Lk["agro_own"],
    "AgroCAD (nosso LSFP/QBD/CLE nos pontos)": Lk["agro_ours"],
    "DRONE centro de passada (verdade)": centro_lines,
    "projeto": Lk["proj_lines"],
}
res = {}
for nomeR, R, quais in [("R1", R1, list(fontes)), ("R2", R2, list(fontes)),
                        ("R0", R0, ["DRONE centro de passada (verdade)", "projeto"])]:
    print(f"\n### Regiao {nomeR}")
    for f in quais:
        L = recorta(fontes[f], R)
        t0 = time.time()
        r = pll(L)
        res[(nomeR, f)] = r
        print(f"  {f:42s} linhas={len(L):4d} km={sum(l.length for l in L)/1000:6.1f} | amostras={r.total_amostras:6d} "
              f"abaixo={r.pct_abaixo:5.1f}% ideal={r.pct_ideal:5.1f}% acima={r.pct_acima:5.1f}% media={r.espacamento_medio:.3f} ({time.time()-t0:.0f}s)")
pickle.dump(dict(res={k: vars(v) for k, v in res.items()}, R1=R1, R2=R2), open(os.path.join(CACHE, "pll_regioes.pkl"), "wb"))
