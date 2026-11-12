"""Item 2: espacamento projetado entre linhas de orientacao adjacentes."""
import numpy as np, time, json
from lib_geo import *
from shapely.geometry import LineString
from paralelismo_pipeline import pll

g = carregar()
proj = g["projeto"]
L = np.array([comprimento(a) for a in proj])
print("linhas de projeto:", len(proj), "comprimento p5/p50/p95:", np.percentile(L, [5, 50, 95]).round(1),
      "menores que 10 m:", (L < 10).sum())

ref = RefIndex(proj, passo=0.25)
esp_e, esp_d = [], []
for i, a in enumerate(proj):
    p, t, s = reamostrar(a, 10.0)
    if len(p) < 3:
        continue
    p, t = p[1:-1], t[1:-1]
    for offs in ref.offsets(p, t, raio=4.6, max_ang=15):
        pos = [o for o, lid, _ in offs if lid != i and o > 0.3]
        neg = [-o for o, lid, _ in offs if lid != i and o < -0.3]
        esp_e.append(min(pos) if pos else np.nan)
        esp_d.append(min(neg) if neg else np.nan)
esp = np.r_[esp_e, esp_d]
esp = esp[np.isfinite(esp)]
print("espacamento projeto (amostras a cada 10 m, cada lado):")
print("  percentis 1/5/25/50/75/95/99:", np.percentile(esp, [1, 5, 25, 50, 75, 95, 99]).round(3))
print("  classificacao PLL:", fmt_cls(classifica(esp)))
h, e = np.histogram(esp, bins=[0, 2.6, 2.8, 2.9, 2.95, 2.98, 3.02, 3.05, 3.1, 3.2, 3.4, 5])
print("  histograma:", list(zip(e[:-1].round(2), h)))

t0 = time.time()
r = pll([LineString(a) for a in proj if len(a) >= 2 and comprimento(a) > 0])
print(f"PLL oficial (nosso pll) nas linhas do projeto ({time.time()-t0:.0f}s):")
print(r.resumo())
np.save(os.path.join(CACHE, "esp_projeto.npy"), esp)
