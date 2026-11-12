"""Estacoes a cada 2 m ao longo das linhas de orientacao (projeto). Em cada
estacao, numa perpendicular de +-4,6 m, mede a posicao (offset assinado no
referencial da linha de projeto, + = esquerda) de:
  - linhas do drone (todas)
  - linhas de ticks (pipeline LSFP/QBD/CLE) e sentido de marcha
  - linhas AgroCAD (proprias do executado.dwg)
Agrupa em 'faixas' k = -1, 0, +1 (passadas centradas em 3k m).
Salva cache/estacoes.npz."""
import pickle
import numpy as np
from lib_geo import *

g = carregar()
Lk = pickle.load(open(os.path.join(CACHE, "linhas.pkl"), "rb"))
proj = g["projeto"]

ref_dr = RefIndex(g["drone"], passo=0.5)
tick_arr = [np.asarray(l.coords) for l in Lk["tick_lines"]]
ref_tk = RefIndex(tick_arr, passo=0.5)
ref_ag = RefIndex([np.asarray(l.coords) for l in Lk["agro_own"]], passo=0.5)
# amostras de ticks "documentadas"
agro_tree = cKDTree(g["agro_xy"][g["agro_on"]])
doc_tk = agro_tree.query(ref_tk.p)[0] < 0.30

S = []  # registros
for li, a in enumerate(proj):
    p, t, s = reamostrar(a, 2.0)
    if len(p) < 5:
        continue
    kur = curvatura(p, t, s)
    # so estacoes com tick e drone por perto
    near_t = ref_tk.tree.query(p, distance_upper_bound=4.6)[0] < np.inf
    near_d = ref_dr.tree.query(p, distance_upper_bound=4.6)[0] < np.inf
    sel = np.where(near_t & near_d)[0]
    sel = sel[(s[sel] > 2) & (s[sel] < s[-1] - 2)]
    if len(sel) == 0:
        continue
    P, Tt = p[sel], t[sel]
    od = ref_dr.offsets(P, Tt, raio=4.6, max_ang=10, k=300)
    ot = ref_tk.offsets(P, Tt, raio=4.6, max_ang=10, k=300)
    oa = ref_ag.offsets(P, Tt, raio=4.6, max_ang=10, k=300)
    for j in range(len(sel)):
        rec = dict(lid=li, s=s[sel[j]], x=P[j, 0], y=P[j, 1], tx=Tt[j, 0], ty=Tt[j, 1], kur=kur[sel[j]],
                   drone=sorted(o for o, _, _ in od[j]),
                   tick=[(o, np.sign(ref_tk.t[i] @ Tt[j]), doc_tk[i], l) for o, l, i in ot[j]],
                   agro=[(o, np.sign(ref_ag.t[i] @ Tt[j]), l) for o, l, i in oa[j]])
        S.append(rec)
print("estacoes com drone e ticks a <4,6 m:", len(S))
pickle.dump(S, open(os.path.join(CACHE, "estacoes.pkl"), "wb"))

