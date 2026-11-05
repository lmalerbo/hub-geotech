"""O que o Web Worker chama no Pyodide (app/paralelismo-worker.js). Memória, spec §8: um arquivo por vez; por frota
numa fazenda os pontos viram linhas e são descartados; só as linhas ficam."""
import collections
import json
import os
import traceback

from paralelismo.analise import (analisar_fazenda, exportar_shapefiles, linhas_do_grupo, para_utm, sem_trabalho,
                                 talhoes_de_geojson)
from paralelismo.gs3 import gs3_completo, ler_gs3
from paralelismo.jdl import jdl_completo, ler_jdl

# .jdl: um tick a cada 0,2 s (spec §3). GS3: o arquivo não diz a frequência; 1 s por registro é suposição, usada só
# no aviso de frota sem trabalho (a fração não depende dela, o mínimo de 1 h de trilha depende).
SEGUNDOS_POR_REGISTRO = {'jdl': 0.2, 'gs3': 1.0}


class Grupo:
    """Uma frota numa fazenda. Os arquivos entram em ordem de gravação, como na regressão."""

    def __init__(self, frota):
        self.frota = frota
        self.pontos = []
        self._por_data = collections.Counter()
        self._total_s = 0.0
        self._trabalho_s = 0.0

    def ler(self, tipo, caminho, data):
        """Lê e apaga o arquivo (e o .fdd ao lado do .fdl), para ele não ficar na memória do Pyodide."""
        if self.pontos is None:
            raise RuntimeError('grupo já fechado')
        if tipo not in SEGUNDOS_POR_REGISTRO:
            raise ValueError(f'tipo desconhecido: {tipo}')
        try:
            pontos, registros = (ler_jdl if tipo == 'jdl' else ler_gs3)(caminho)
            completo = registros > 0 and (jdl_completo if tipo == 'jdl' else gs3_completo)(caminho)
        except MemoryError:  # falha do ambiente, não do arquivo: o item dá erro e pode ser refeito
            raise
        except Exception:  # o arquivo é pulado e listado, e o resto da rodada segue (spec §10)
            traceback.print_exc()
            pontos, registros, completo = [], 0, False
        finally:
            _apagar(caminho)
            if tipo == 'gs3':
                _apagar(caminho[:-4] + '.fdd')
        self.pontos.extend(para_utm(pontos))
        if data:
            self._por_data[data] += len(pontos)
        segundos = SEGUNDOS_POR_REGISTRO[tipo]
        self._total_s += registros * segundos
        self._trabalho_s += len(pontos) * segundos
        return {'pontos': len(pontos), 'registros': registros, 'legivel': registros > 0, 'completo': completo}

    def fechar(self):
        if self.pontos is None:
            raise RuntimeError('grupo já fechado')
        data = self._por_data.most_common(1)[0][0] if self._por_data else None
        linhas = [{'frota': self.frota, 'data': data, 'coords': [list(c) for c in g.coords]}
                  for g in linhas_do_grupo(self.pontos)]
        self.pontos = None
        return {'frota': self.frota, 'data': data, 'linhas': linhas,
                'duracao_total_s': self._total_s, 'duracao_trabalho_s': self._trabalho_s,
                'sem_trabalho': sem_trabalho(self._total_s, self._trabalho_s)}

    def fechar_json(self):
        return json.dumps(self.fechar())


def _apagar(caminho):
    try:
        os.remove(caminho)
    except OSError:
        pass


def analisar(linhas_json, talhoes_json, prefixo):
    """(resultado de analisar_fazenda em JSON, zip dos shapefiles). As linhas já vêm mescladas com as vigentes."""
    linhas = json.loads(linhas_json)
    resultado = analisar_fazenda(linhas, talhoes_de_geojson(json.loads(talhoes_json)))
    return json.dumps(resultado), exportar_shapefiles(resultado, linhas, prefixo)
