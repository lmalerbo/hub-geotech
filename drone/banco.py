"""Chamadas do módulo Drone ao schema hub (service_role) e ao Supabase Storage."""
import datetime
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
    def proximo_numero(self, cod_faz, documento) -> int:
        """Número que a próxima revisão receberá (só leitura; o projeto nasce em drone_publicar)."""
        p = self.selecionar('projetos', 'id', {'modulo_id': 'eq.drone', 'tipo': 'eq.individual',
                                               'cod_faz': f'eq.{cod_faz}'})
        if not p:
            return 0
        r = self.selecionar('projeto_revisoes', 'numero', {'projeto_id': f"eq.{p[0]['id']}",
                                                           'documento': f'eq.{documento}',
                                                           'order': 'numero.desc', 'limit': '1'})
        return r[0]['numero'] + 1 if r else 0

    def publicar_revisao(self, cod_faz, documento, motivo, numero, arquivos, geracao_id=None, legado=False) -> int:
        """Revisão + arquivos + conclusão da geração/solicitação numa transação (hub.drone_publicar)."""
        return self.rpc('drone_publicar', {
            'p_cod_faz': cod_faz, 'p_documento': documento, 'p_motivo': motivo, 'p_numero': numero,
            'p_arquivos': arquivos, 'p_geracao_id': geracao_id, 'p_legado': legado})

    def previas_para_apagar(self) -> list:
        limite = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
        return self.selecionar('drone_geracoes', 'id,status,previa_zip,previa_pdf', {
            'previa_zip': 'not.is.null',
            'or': f'(status.in.(publicada,descartada),and(status.eq.pronta,concluido_em.lt.{limite}))'})

    def limpar_previa(self, geracao_id, descartar=False):
        valores = {'previa_zip': None, 'previa_pdf': None}
        if descartar:
            valores['status'] = 'descartada'
        self.atualizar('drone_geracoes', {'id': f'eq.{geracao_id}'}, valores)

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
