"""Base de Talhões do dia (Talhoes_da_Pedra_DD_MM_AAAA_fme.shp), fonte oficial da geometria."""
import datetime
import glob
import os
import re
from pathlib import Path

import pyogrio
from shapely.validation import make_valid

from drone.config import CRS_TRABALHO
from drone.erros import ErroGeracao

DATA_NO_NOME = re.compile(r'_(\d{2})_(\d{2})_(\d{4})_fme\.shp$', re.IGNORECASE)


def arquivo_mais_recente(pasta: str, padrao: str) -> tuple:
    candidatos = []
    for caminho in glob.glob(os.path.join(pasta, padrao)):
        m = DATA_NO_NOME.search(caminho)
        if m:
            dia, mes, ano = map(int, m.groups())
            candidatos.append((datetime.date(ano, mes, dia), Path(caminho)))
    if not candidatos:
        raise ErroGeracao(f'Nenhum arquivo da Base de Talhões ({padrao}) em {pasta}.')
    return max(candidatos)


def talhoes_da_fazenda(caminho: Path, cod_faz: int):
    try:
        gdf = pyogrio.read_dataframe(caminho, columns=['SECAO', 'TALHAO', 'AREA_PROD'],
                                     where=f'CAST(SECAO AS integer) = {int(cod_faz)}')   # SECAO é texto na Base
    except Exception as e:  # rede fora, arquivo corrompido
        raise ErroGeracao(f'Não foi possível ler a Base de Talhões ({caminho.name}): {e}') from e
    gdf = gdf[gdf.geometry.notna()]
    if gdf.empty:
        raise ErroGeracao(f'A fazenda {cod_faz} não tem talhões na Base de Talhões ({caminho.name}).')
    gdf = gdf.to_crs(CRS_TRABALHO)
    gdf['geometry'] = gdf.geometry.apply(make_valid)
    gdf['TALHAO'] = gdf['TALHAO'].astype(float).astype(int)
    gdf['AREA_PROD'] = gdf['AREA_PROD'].astype(float)
    return gdf[['TALHAO', 'AREA_PROD', 'geometry']].reset_index(drop=True)
