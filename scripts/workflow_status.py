"""
Log de status do pipeline (append-only, JSON Lines) -- alimentado pelos
scripts do pipeline (dxf_para_gen4.py, build_bundle_completo.py, etc.) e
consumido pelo painel de acompanhamento (painel_workflow.html).

Cada linha do log e um evento: uma etapa concluida ou com erro, pra uma
fazenda/tipo especifico.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path("linhas-vant/workflow_log.jsonl")

ETAPAS = ["dxf", "classificacao", "mapa", "qualidade", "gen4", "gs3_2630", "agdata", "aggps"]


def registrar(codigo: str, nome: str, tipo: str, etapa: str, status: str,
              detalhes: dict | None = None):
    """status: 'ok' ou 'erro'. etapa: uma de ETAPAS (ou livre, pra eventos extras)."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    evento = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "codigo": codigo,
        "nome": nome,
        "tipo": tipo,
        "etapa": etapa,
        "status": status,
        "detalhes": detalhes or {},
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(evento, ensure_ascii=False) + "\n")


def ler_eventos() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    eventos = []
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if linha:
                eventos.append(json.loads(linha))
    return eventos


class rastrear_etapa:
    """Context manager: registra 'ok' se o bloco terminar sem excecao, 'erro'
    (com a mensagem) se lancar. Uso:
        with rastrear_etapa(codigo, nome, tipo, "classificacao") as r:
            ... faz a etapa ...
            r.detalhes = {"n_partes": 50}   # opcional, anexado ao evento 'ok'
    """

    def __init__(self, codigo: str, nome: str, tipo: str, etapa: str):
        self.codigo, self.nome, self.tipo, self.etapa = codigo, nome, tipo, etapa
        self.detalhes = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            registrar(self.codigo, self.nome, self.tipo, self.etapa, "ok", self.detalhes)
        else:
            registrar(self.codigo, self.nome, self.tipo, self.etapa, "erro",
                      {"erro": str(exc_val)})
        return False  # nao suprime a excecao
