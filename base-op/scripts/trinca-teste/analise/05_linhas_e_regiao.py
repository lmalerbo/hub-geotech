"""Monta as linhas de cada fonte e a regiao de sobreposicao.
 - ticks: pipeline atual (todos os ticks) -> LSFP 10 / QBD 160 / CLE 10
 - ticks documentados (a <30cm de ponto AgroCAD On) -> idem (teste)
 - AgroCAD: (a) polilinhas do proprio executado.dwg (camadas 62571/64086/64088)
            (b) nosso LSFP/QBD/CLE sobre os FIELD_POINTS
 - regiao comum = cobertura drone ∩ ticks ∩ AgroCAD (buffers de 1,6 m)
"""
import pickle
import numpy as np
from shapely.geometry import LineString
from shapely import union_all
from lib_geo import *
from paralelismo_pipeline import lsfp, qbd, cle

g = carregar()


def pipeline(pts):
    L = lsfp({"f": [tuple(p) for p in pts]}, max_dist=10)
    L = qbd(L, min_angle_deg=160)
    return cle(L, min_length=10)


tick_lines = pipeline(g["ticks"])
tr = np.load(os.path.join(CACHE, "ticks_trilha.npz"))
# ticks documentados: reaplica a mascara nos ticks brutos via indice 'keep' nao salvo -> recalcula
agro_tree = cKDTree(g["agro_xy"][g["agro_on"]])
d, _ = agro_tree.query(g["ticks"])
tick_doc_lines = []
# mantem a ordem; pontos nao documentados viram "quebra" (salto) -> separa grupos
grp, cur = {}, []
k = 0
for p, ok in zip(g["ticks"], d < 0.30):
    if ok:
        cur.append(tuple(p))
    elif cur:
        grp[k] = cur; k += 1; cur = []
if cur:
    grp[k] = cur
tick_doc_lines = cle(qbd(lsfp(grp, 10), 160), 10)

agro_own = [LineString(a) for L in g["agro_pl"].values() for a in L if len(a) >= 2]
agro_ours = pipeline(g["agro_xy"])
drone_lines = [LineString(a) for a in g["drone"] if len(a) >= 2]
proj_lines = [LineString(a) for a in g["projeto"] if len(a) >= 2 and comprimento(a) > 0]

for nome, L in [("ticks (pipeline)", tick_lines), ("ticks documentados", tick_doc_lines),
                ("AgroCAD proprio", agro_own), ("AgroCAD nosso LSFP", agro_ours), ("drone", drone_lines)]:
    print(f"{nome:22s}: {len(L):5d} linhas, {sum(l.length for l in L)/1000:7.1f} km")

cov = {}
for nome, L in [("drone", drone_lines), ("ticks", tick_lines), ("agro", agro_own)]:
    cov[nome] = union_all([l.buffer(1.6, quad_segs=2) for l in L])
    print(f"cobertura {nome}: {cov[nome].area/1e4:.1f} ha")
comum = cov["drone"].intersection(cov["ticks"]).intersection(cov["agro"])
comum = comum.buffer(-1.0).buffer(1.0)
print(f"regiao comum drone∩ticks∩AgroCAD: {comum.area/1e4:.2f} ha")
dt = cov["drone"].intersection(cov["ticks"]).buffer(-1.0).buffer(1.0)
print(f"regiao drone∩ticks: {dt.area/1e4:.2f} ha")
pickle.dump(dict(tick_lines=tick_lines, tick_doc_lines=tick_doc_lines, agro_own=agro_own, agro_ours=agro_ours,
                 drone_lines=drone_lines, proj_lines=proj_lines, cov=cov, comum=comum, drone_ticks=dt),
            open(os.path.join(CACHE, "linhas.pkl"), "wb"))
