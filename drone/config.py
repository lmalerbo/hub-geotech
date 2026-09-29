"""Constantes e configuração do módulo Drone (bloco "drone" de ingestao/config.json)."""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CRS_TRABALHO = 31983   # SIRGAS 2000 / UTM 23S — todo cálculo de área/buffer
CRS_SAIDA = 4326       # WGS84 — shapefile entregue ao piloto
PASTA_TRABALHO = RAIZ / 'drone' / 'trabalho'
LOGO = RAIZ / 'drone' / 'assets' / 'logo-pedra.png'


def cfg() -> dict:
    with open(RAIZ / 'ingestao' / 'config.json', encoding='utf-8') as f:
        return json.load(f)['drone']
