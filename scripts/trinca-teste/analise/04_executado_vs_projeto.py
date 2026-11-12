"""Item 3: desvio lateral do executado (ticks .jdl e pontos AgroCAD) em
relacao a linha de orientacao mais proxima e paralela."""
import numpy as np
from lib_geo import *

g = carregar()
ref = RefIndex(g["projeto"], passo=0.25, com_curv=True)
agro_tree = cKDTree(g["agro_xy"][g["agro_on"]])


def desvios(P, D, raio=1.6, max_ang=10):
    ok = np.isfinite(D[:, 0])
    dev = np.full(len(P), np.nan); kur = np.full(len(P), np.nan); lid = np.full(len(P), -1)
    idx = np.where(ok)[0]
    for a in range(0, len(idx), 50000):
        b = idx[a:a + 50000]
        for j, offs in zip(b, ref.offsets(P[b], D[b], raio=raio, max_ang=max_ang, k=32)):
            if not offs:
                continue
            o, l, i = min(offs, key=lambda x: abs(x[0]))
            dev[j] = -o  # + = executado a ESQUERDA da linha de orientacao (sentido de marcha)
            sgn = np.sign(ref.t[i] @ D[j])
            kur[j] = ref.k[i] * sgn  # curvatura no sentido de marcha (+ = curva a esquerda)
            lid[j] = l
    return dev, kur, lid


def ajuste_deslocamento(P, D, dev):
    """dev = n_esq . (dx, dy): deslocamento geografico constante."""
    m = np.isfinite(dev) & np.isfinite(D[:, 0])
    n = np.c_[-D[m, 1], D[m, 0]]
    sol, *_ = np.linalg.lstsq(n, dev[m], rcond=None)
    res = dev[m] - n @ sol
    return sol, res


def relatorio(nome, P, D, K, extra_mask=None):
    dev, kur, lid = desvios(P, D)
    m = np.isfinite(dev) & (np.abs(dev) < 1.0)
    if extra_mask is not None:
        m &= extra_mask
    print(f"\n### {nome}: {len(P)} pontos, em trabalho (paralelo <10 graus e |desvio|<1,0 m): {m.sum()} ({100*m.mean():.1f}%)")
    print(resumo(dev[m], "  desvio lateral (m, + = esquerda)"))
    print("  percentis |desvio| 50/68/90/95/99:", np.percentile(np.abs(dev[m]), [50, 68, 90, 95, 99]).round(3))
    sol, res = ajuste_deslocamento(P[m], D[m], dev[m])
    print(f"  deslocamento geografico constante ajustado: dE={sol[0]:+.3f} dN={sol[1]:+.3f} m; residuo dp={res.std():.3f}")
    # por sentido de marcha (rumo) -- alternancia indica deslocamento geografico
    rumo = np.degrees(np.arctan2(D[m, 0], D[m, 1])) % 360
    for a in range(0, 360, 90):
        mm = (rumo >= a) & (rumo < a + 90)
        if mm.sum() > 100:
            print(f"   rumo {a:3d}-{a+90:3d}: n={mm.sum():6d} mediana={np.median(dev[m][mm]):+.3f}")
    kk = kur[m]; dd = dev[m]
    R = 1 / np.abs(kk)
    print("  por curvatura da linha de orientacao (raio R; sinal + = curva a esquerda):")
    for lo, hi in [(500, np.inf), (200, 500), (100, 200), (50, 100), (0, 50)]:
        for sg, nm in [(1, "esq"), (-1, "dir")]:
            mm = (R >= lo) & (R < hi) & (np.sign(kk) == sg)
            if mm.sum() > 50:
                print(f"   R {lo:>4}-{hi:<5} {nm}: n={mm.sum():6d} media={dd[mm].mean():+.3f} mediana={np.median(dd[mm]):+.3f} dp={dd[mm].std():.3f}")
    return dev, kur, m


# --- ticks .jdl
P, D, K, keep, brk = trilha_ticks(g["ticks"])
dist_agro, _ = agro_tree.query(P)
doc = dist_agro < 0.30
print(f"ticks: {len(g['ticks'])} brutos, {len(P)} apos remover parados (<5 cm); "
      f"{doc.mean()*100:.1f}% a <30 cm de um ponto AgroCAD 'On' (='documentados')")
dev_t, kur_t, m_t = relatorio("TICKS .jdl (todos)", P, D, K)
relatorio("TICKS .jdl documentados (a <30cm de ponto AgroCAD On)", P, D, K, doc)
relatorio("TICKS .jdl NAO documentados", P, D, K, ~doc)
np.savez(os.path.join(CACHE, "ticks_trilha.npz"), P=P, D=D, K=K, dev=dev_t, kur=kur_t, trab=m_t, doc=doc, brk=brk)

# --- AgroCAD
A = g["agro_xy"][g["agro_on"]]
PA, DA, KA, keepA, brkA = trilha_ticks(A)
dev_a, kur_a, m_a = relatorio("PONTOS AgroCAD (On)", PA, DA, KA)
np.savez(os.path.join(CACHE, "agro_trilha.npz"), P=PA, D=DA, K=KA, dev=dev_a, kur=kur_a, trab=m_a)

# --- AgroCAD x ticks: distancia lateral (perpendicular a trilha de ticks)
tt = cKDTree(P)
d, i = tt.query(PA, k=1)
v = PA - P[i]
lat = D[i, 0] * v[:, 1] - D[i, 1] * v[:, 0]
mm = np.isfinite(lat) & (d < 1.0) & m_a
print("\n### AgroCAD x ticks (ponto AgroCAD vs tick mais proximo)")
print(resumo(d[mm], "  distancia euclidiana"))
print(resumo(lat[mm], "  componente lateral (+ = AgroCAD a esquerda do tick)"))
# mesma linha de orientacao: diferenca de desvio
print("  dp do desvio vs projeto: ticks documentados =",
      round(float(np.nanstd(dev_t[m_t & doc])), 3), " AgroCAD =", round(float(np.nanstd(dev_a[m_a])), 3))
