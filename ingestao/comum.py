"""Peças compartilhadas pelas importações diárias do Hub: credenciais,
acesso ao Supabase (schema hub) e registro de cada execução."""

import datetime
import json
import os
import unicodedata

import requests

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def carregar_env(caminho=os.path.join(RAIZ, 'hub-geotech-supabase.env')):
    valores = {}
    with open(caminho, encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith('#') or '=' not in linha:
                continue
            chave, valor = linha.split('=', 1)
            valores[chave.strip()] = valor.strip().strip('"').strip("'")
    return valores


def carregar_config():
    with open(os.path.join(RAIZ, 'ingestao', 'config.json'), encoding='utf-8') as f:
        return json.load(f)


def agora_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def norm(valor):
    """Sem acento, sem espaço nas pontas, maiúsculo — pra comparar nomes."""
    s = unicodedata.normalize('NFD', str(valor or ''))
    return s.encode('ascii', 'ignore').decode().strip().upper()


def calc_layer(cod_faz, talhao):
    return cod_faz * 1000 + talhao


def para_int(valor):
    s = str(valor).strip()
    if '_' in s:
        # float() aceita "10728_11" como 1072811 — foi assim que o LAYER dos
        # sistemas antigos saiu no formato errado.
        return None
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def achar_aba(workbook, nome):
    for aba in workbook.sheetnames:
        if norm(aba) == norm(nome):
            return workbook[aba]
    raise RuntimeError(f"Aba '{nome}' não encontrada (abas: {workbook.sheetnames})")


def ler_tabela(aba, obrigatorias, max_linhas_cabecalho=30):
    """Acha a linha de cabeçalho pelos nomes das colunas (nunca pela posição)
    e devolve (colunas, linhas). colunas mapeia nome normalizado → lista de
    índices, na ordem em que aparecem (há planilhas com nome repetido)."""
    linhas = list(aba.iter_rows(values_only=True))
    for i, linha in enumerate(linhas[:max_linhas_cabecalho]):
        colunas = {}
        for j, v in enumerate(linha):
            if v is not None:
                colunas.setdefault(norm(v), []).append(j)
        if all(norm(o) in colunas for o in obrigatorias):
            return colunas, linhas[i + 1:]
    raise RuntimeError(f'Cabeçalho com {obrigatorias} não encontrado nas primeiras {max_linhas_cabecalho} linhas')


class Hub:
    """Cliente mínimo do PostgREST do Supabase, apontado pro schema hub,
    usando a service_role (as importações gravam sem passar pelo RLS)."""

    def __init__(self):
        env = carregar_env()
        self.url = env['SUPABASE_URL'].rstrip('/') + '/rest/v1'
        chave = env['SUPABASE_SERVICE_ROLE_KEY']
        self.headers = {
            'apikey': chave,
            'Authorization': f'Bearer {chave}',
            'Accept-Profile': 'hub',
            'Content-Profile': 'hub',
            'Content-Type': 'application/json',
        }

    def _checar(self, resposta, tabela):
        if not resposta.ok:
            raise RuntimeError(f'{tabela}: HTTP {resposta.status_code} {resposta.text[:300]}')

    def upsert(self, tabela, linhas, conflito, lote=1000):
        # merge-duplicates só atualiza as colunas enviadas: o que outra fonte
        # grava na mesma linha fica intacto (regra de dono de campo).
        for i in range(0, len(linhas), lote):
            r = requests.post(
                f'{self.url}/{tabela}',
                params={'on_conflict': conflito},
                headers={**self.headers, 'Prefer': 'resolution=merge-duplicates,return=minimal'},
                json=linhas[i:i + lote],
                timeout=120,
            )
            self._checar(r, tabela)

    def selecionar(self, tabela, colunas, filtro=None, pagina=1000):
        # O PostgREST devolve no máximo ~1000 linhas por chamada: pagina sempre.
        resultado, inicio = [], 0
        while True:
            r = requests.get(
                f'{self.url}/{tabela}',
                params={'select': colunas, **(filtro or {})},
                headers={**self.headers, 'Range': f'{inicio}-{inicio + pagina - 1}'},
                timeout=120,
            )
            self._checar(r, tabela)
            lote = r.json()
            resultado.extend(lote)
            if len(lote) < pagina:
                return resultado
            inicio += pagina

    def layers_existentes(self):
        return {t['layer'] for t in self.selecionar('talhoes', 'layer')}

    def inserir(self, tabela, linha):
        r = requests.post(
            f'{self.url}/{tabela}',
            headers={**self.headers, 'Prefer': 'return=representation'},
            json=linha,
            timeout=60,
        )
        self._checar(r, tabela)
        return r.json()[0]

    def rpc(self, funcao, parametros=None):
        r = requests.post(f'{self.url}/rpc/{funcao}', headers=self.headers, json=parametros or {}, timeout=120)
        self._checar(r, funcao)
        return r.json() if r.content else None   # função que devolve void → 204 sem corpo

    def atualizar(self, tabela, filtro, valores):
        r = requests.patch(
            f'{self.url}/{tabela}',
            params=filtro,
            headers={**self.headers, 'Prefer': 'return=minimal'},
            json=valores,
            timeout=60,
        )
        self._checar(r, tabela)


class Execucao:
    """Registra a execução em hub.execucoes_ingestao (rodando → ok/erro)."""

    def __init__(self, hub, fonte):
        self.hub = hub
        self.fonte = fonte
        self.linhas_lidas = None
        self.linhas_gravadas = None
        self.detalhes = None

    def __enter__(self):
        self.id = self.hub.inserir('execucoes_ingestao', {'fonte': self.fonte})['id']
        return self

    def __exit__(self, tipo, erro, _tb):
        self.hub.atualizar('execucoes_ingestao', {'id': f'eq.{self.id}'}, {
            'finalizado_em': agora_iso(),
            'status': 'erro' if erro else 'ok',
            'linhas_lidas': self.linhas_lidas,
            'linhas_gravadas': self.linhas_gravadas,
            'detalhes': self.detalhes,
            'erro': str(erro)[:1000] if erro else None,
        })
        return False
