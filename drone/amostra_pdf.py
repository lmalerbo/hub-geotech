"""Gera PDFs de amostra a partir de projetos reais do G:\\ para comparar com a maquete v6.
Uso: python -m drone.amostra_pdf <shp_base_talhoes> <cod_faz> <nome> <normal|catacao> <shp_aplicacao> <saida.pdf>"""
import datetime
import sys
from pathlib import Path

import geopandas as gpd

from drone.base_talhoes import talhoes_da_fazenda
from drone.geometria import recortar, uniao_buffers
from drone.mapa_pdf import DadosMapa, gerar_pdf

base, cod, nome, tipo, aplic, saida = sys.argv[1:7]
t = talhoes_da_fazenda(Path(base), int(cod))
infest = list(gpd.read_file(aplic).to_crs(31983).geometry)
r = recortar(t, uniao_buffers({}, {}), infestacao=infest, margem=0)
print(gerar_pdf(DadosMapa(int(cod), nome, tipo, 0, t, r, datetime.date.today()), saida))
