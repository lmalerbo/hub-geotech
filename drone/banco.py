"""Chamadas do módulo Drone ao schema hub (service_role) e ao Supabase Storage."""
import sys
from pathlib import Path

import requests
from shapely import wkt as shapely_wkt

from drone.config import RAIZ

sys.path.insert(0, str(RAIZ / 'ingestao'))
from comum import Hub, agora_iso, carregar_env  # noqa: E402,F401  (carregar_env é reexportado para o agente)

BUCKET = 'drone-previas'


class DroneBanco(Hub):
    def __init__(self):
        super().__init__()
        self.storage = self.url.replace('/rest/v1', '/storage/v1')

    # ── parâmetros e sinal de vida ──────────────────────────────────
    def parametros(self) -> dict:
        return {p['chave']: p['valor'] for p in self.selecionar('drone_parametros', 'chave,valor')}

    def distancias(self) -> dict:
        return {c['classe_m']: float(c['distancia_m'])
                for c in self.selecionar('drone_classes_restricao', 'classe_m,distancia_m')}

    def batimento(self):
        self.atualizar('drone_parametros', {'chave': 'eq.agente_ultimo_ciclo'},
                       {'valor': agora_iso(), 'atualizado_em': agora_iso()})

    # ── leitura ─────────────────────────────────────────────────────
    def fazenda(self, cod_faz) -> dict:
        r = self.selecionar('fazendas', 'cod_faz,nome', {'cod_faz': f'eq.{cod_faz}'})
        if not r:
            raise RuntimeError(f'Fazenda {cod_faz} não existe em hub.fazendas')
        return r[0]

    def obstaculos_vigentes(self, cod_faz):
        linhas = self.rpc('drone_obstaculos_vigentes', {'p_cod_faz': cod_faz}) or []
        geoms, versoes = {}, {}
        for l in linhas:
            geoms.setdefault(l['classe_m'], []).append(shapely_wkt.loads(l['wkt']))
            versoes[l['versao_id']] = {'classe_m': l['classe_m'], 'versao_id': l['versao_id'],
                                       'enviado_em': l['enviado_em']}
        return geoms, list(versoes.values())

    def infestacao(self, infestacao_id) -> list:
        return [shapely_wkt.loads(l['wkt'])
                for l in self.rpc('drone_infestacao_wkt', {'p_infestacao_id': infestacao_id}) or []]

    def ultima_infestacao(self, solicitacao_id):
        r = self.selecionar('drone_infestacoes', 'id',
                            {'solicitacao_id': f'eq.{solicitacao_id}', 'order': 'id.desc', 'limit': '1'})
        return r[0]['id'] if r else None

    def solicitacao(self, id_) -> dict:
        return self.selecionar('drone_solicitacoes', '*', {'id': f'eq.{id_}'})[0]

    # ── escrita ─────────────────────────────────────────────────────
    def criar_solicitacao(self, cod_faz, tipo, origem, status=None, data_desejada=None) -> dict:
        linha = {'cod_faz': cod_faz, 'tipo': tipo, 'origem': origem, 'data_desejada': data_desejada}
        if status:
            linha['status'] = status
        return self.inserir('drone_solicitacoes', linha)

    def pedir_geracao(self, solicitacao_id, infestacao_id=None) -> dict:
        self.atualizar('drone_solicitacoes', {'id': f'eq.{solicitacao_id}', 'status': 'eq.solicitado'},
                       {'status': 'em_elaboracao', 'iniciado_em': agora_iso()})
        return self.inserir('drone_geracoes', {'solicitacao_id': solicitacao_id, 'infestacao_id': infestacao_id})

    def pegar_geracao(self):
        r = self.rpc('drone_pegar_geracao')
        return r[0] if r else None

    def concluir_geracao(self, id_, **campos):
        self.atualizar('drone_geracoes', {'id': f'eq.{id_}'}, {'concluido_em': agora_iso(), **campos})

    def pedir_publicacao(self, geracao_id, motivo=None):
        self.atualizar('drone_geracoes', {'id': f'eq.{geracao_id}', 'status': 'eq.pronta'},
                       {'publicar_pedido_em': agora_iso(), 'publicar_motivo': motivo, 'publicacao_erro': None})

    def pegar_publicacao(self):
        r = self.rpc('drone_pegar_publicacao')
        return r[0] if r else None

    def erro_publicacao(self, id_, msg):
        self.atualizar('drone_geracoes', {'id': f'eq.{id_}'},
                       {'publicacao_erro': msg[:1000], 'publicacao_iniciada_em': None})

    def gravar_obstaculos(self, cod_faz, classe_m, origem, arquivo, geoms) -> int:
        return self.rpc('drone_gravar_obstaculos', {
            'p_cod_faz': cod_faz, 'p_classe_m': classe_m, 'p_origem': origem, 'p_arquivo': arquivo,
            'p_wkts': [g.wkt for g in geoms]})

    def gravar_infestacao(self, solicitacao_id, empresa, arquivo, geoms) -> int:
        return self.rpc('drone_gravar_infestacao', {
            'p_solicitacao_id': solicitacao_id, 'p_empresa': empresa, 'p_arquivo': arquivo,
            'p_wkts': [g.wkt for g in geoms]})

    # ── projeto e revisões (tabelas existentes do Hub) ──────────────
    def projeto_individual(self, cod_faz, nome) -> int:
        r = self.selecionar('projetos', 'id', {'modulo_id': 'eq.drone', 'tipo': 'eq.individual',
                                               'cod_faz': f'eq.{cod_faz}'})
        if r:
            return r[0]['id']
        return self.inserir('projetos', {'modulo_id': 'drone', 'tipo': 'individual',
                                         'cod_faz': cod_faz, 'nome': nome})['id']

    def revisao_vigente(self, projeto_id, documento):
        r = self.selecionar('projeto_revisoes', 'id,numero,motivo',
                            {'projeto_id': f'eq.{projeto_id}', 'documento': f'eq.{documento}', 'vigente': 'is.true'})
        return r[0] if r else None

    def nova_revisao(self, projeto_id, documento, motivo) -> dict:
        rev_id = self.rpc('nova_revisao', {'p_projeto_id': projeto_id, 'p_documento': documento,
                                            'p_motivo': motivo, 'p_origens': None})
        return self.selecionar('projeto_revisoes', 'id,numero', {'id': f'eq.{rev_id}'})[0]

    def arquivos_da_revisao(self, revisao_id) -> list:
        return [a['nome_arquivo'] for a in self.selecionar('revisao_arquivos', 'nome_arquivo',
                                                           {'revisao_id': f'eq.{revisao_id}'})]

    def registrar_arquivo(self, revisao_id, nome, url, tamanho):
        self.upsert('revisao_arquivos', [{'revisao_id': revisao_id, 'nome_arquivo': nome,
                                          'release_url': url, 'tamanho_bytes': tamanho}],
                    'revisao_id,nome_arquivo')

    def concluir_publicacao(self, geracao_id, revisao_id):
        self.rpc('drone_concluir_publicacao', {'p_geracao_id': geracao_id, 'p_revisao_id': revisao_id})

    # ── Storage (prévias) ───────────────────────────────────────────
    def _storage_headers(self):
        return {'apikey': self.headers['apikey'], 'Authorization': self.headers['Authorization']}

    def subir_previa(self, caminho: Path, destino: str) -> str:
        r = requests.post(f'{self.storage}/object/{BUCKET}/{destino}', data=Path(caminho).read_bytes(),
                          headers={**self._storage_headers(), 'x-upsert': 'true',
                                   'Content-Type': 'application/octet-stream'}, timeout=120)
        self._checar(r, 'storage')
        return destino

    def baixar_previa(self, destino: str, caminho: Path) -> Path:
        r = requests.get(f'{self.storage}/object/{BUCKET}/{destino}', headers=self._storage_headers(), timeout=120)
        self._checar(r, 'storage')
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        Path(caminho).write_bytes(r.content)
        return Path(caminho)

    def apagar_previas(self, destinos: list):
        destinos = [d for d in destinos if d]
        if destinos:
            r = requests.delete(f'{self.storage}/object/{BUCKET}', json={'prefixes': destinos},
                                headers=self._storage_headers(), timeout=60)
            self._checar(r, 'storage')
