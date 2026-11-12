"""Figuras do relatorio."""
import pickle
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from lib_geo import *

g = carregar()
tr = np.load(os.path.join(CACHE, "ticks_trilha.npz"))
P, D, dev, trab = tr["P"], tr["D"], tr["dev"], tr["trab"]

# 1. mapa do desvio tick-projeto em referencial GEOGRAFICO (sinal pela normal "a esquerda de quem anda p/ leste")
n = np.c_[-D[:, 1], D[:, 0]]
sg = np.where(D[:, 0] >= 0, 1, -1)  # normaliza: desvio p/ lado "norte-ish" quando anda p/ leste
devg = dev * sg
fig, axs = plt.subplots(1, 2, figsize=(16, 13))
m = trab
sc = axs[0].scatter(P[m, 0], P[m, 1], c=devg[m], s=0.3, cmap="coolwarm", vmin=-0.4, vmax=0.4)
for a in g["projeto"]:
    axs[0].plot(a[:, 0], a[:, 1], color="0.85", lw=0.2, zorder=0)
plt.colorbar(sc, ax=axs[0], shrink=0.6, label="desvio tick - projeto (m), referencial geografico")
axs[0].set_title("Desvio lateral dos ticks em relacao ao projeto\n(cores opostas em passadas vizinhas = sentido; mesma cor = deslocamento geografico)")
axs[0].set_aspect("equal")
axs[1].hist(dev[m], bins=np.arange(-1, 1.001, 0.02), color="0.3")
axs[1].set_title("Desvio tick - projeto no referencial de marcha (+ = esquerda)")
axs[1].set_xlabel("m")
plt.tight_layout(); plt.savefig(os.path.join(OUT, "fig1_desvio_ticks_projeto.png"), dpi=70); plt.close()

# 2. histogramas de espacamento pareado (variante B, com AgroCAD)
rp = pickle.load(open(os.path.join(CACHE, "espac_pareado.pkl"), "rb"))
chave = [k for k in rp if k[0].startswith("B.") and k[1] == ("drone", "tick", "agro")][0]
E = rp[chave]
fig, ax = plt.subplots(figsize=(10, 5))
bins = np.arange(2.6, 3.401, 0.025)
for f, c in [("drone", "green"), ("tick", "red"), ("agro", "blue")]:
    v = E[f][(E[f] >= 2.6) & (E[f] <= 3.4)]
    ax.hist(v, bins=bins, histtype="step", lw=2, color=c, density=True,
            label=f"{f} (n={len(v)}, ideal {100*np.mean((v>=2.9)&(v<=3.1)):.0f}%)")
ax.axvspan(2.9, 3.1, color="0.9", zorder=0)
ax.set_xlabel("espacamento entre passadas (m)"); ax.legend(); ax.set_title("Espacamento pareado nas mesmas estacoes (regiao com drone+ticks+AgroCAD)")
plt.tight_layout(); plt.savefig(os.path.join(OUT, "fig2_espacamento_pareado.png"), dpi=80); plt.close()

# 3. dispersao tick x drone
chave = [k for k in rp if k[0].startswith("B.") and k[1] == ("drone", "tick")][0]
E = rp[chave]
fig, ax = plt.subplots(figsize=(6, 6))
ax.plot(E["drone"], E["tick"], ".", ms=2, alpha=0.4)
ax.plot([2.6, 3.4], [2.6, 3.4], "k-", lw=0.8)
for v in (2.9, 3.1):
    ax.axvline(v, color="0.7", lw=0.6); ax.axhline(v, color="0.7", lw=0.6)
ax.set_xlim(2.6, 3.4); ax.set_ylim(2.6, 3.4); ax.set_xlabel("espacamento real (drone)"); ax.set_ylabel("espacamento pelos ticks .jdl")
ax.set_title("Mesma estacao: ticks x drone")
plt.tight_layout(); plt.savefig(os.path.join(OUT, "fig3_tick_x_drone.png"), dpi=80); plt.close()
print("ok")
