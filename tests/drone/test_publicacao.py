from pathlib import Path

import pytest

from drone.publicacao import GitHubReleases, nome_arquivo, nome_fazenda_arquivo, publicar


def test_nome_da_fazenda_igual_ao_worker():
    assert nome_fazenda_arquivo('VISCONDE DO PARNAÍBA 3') == 'VISCONDE.DO.PARNAIBA.3'
    assert nome_fazenda_arquivo('SANTO AGOSTINHO (STO ANTON. 9)') == 'SANTO.AGOSTINHO.STO.ANTON.9'


def test_nome_do_arquivo():
    assert nome_arquivo(10156, 'POSSES', 2, 'catacao', 'zip') == '10156_POSSES_Rev2-Catacao.zip'


class _Resposta:
    def __init__(self, status, dados):
        self.status_code, self._dados = status, dados
        self.ok = status < 400

    def json(self):
        return self._dados


def test_subir_reaproveita_asset_existente(monkeypatch, tmp_path):
    chamadas = []
    monkeypatch.setattr('drone.publicacao.requests.post', lambda *a, **k: chamadas.append(a) or _Resposta(201, {}))
    gh = GitHubReleases('t', 'dono/repo')
    arq = tmp_path / 'a.zip'
    arq.write_bytes(b'x')
    rel = {'id': 1, 'assets': [{'name': 'a.zip', 'browser_download_url': 'https://x/a.zip', 'size': 1}]}
    assert gh.subir(rel, arq, 'a.zip') == ('https://x/a.zip', 1)
    assert chamadas == []


class _BancoFalso:
    """Imita hub.drone_publicar: abre a revisão, confere o número e registra os arquivos numa transação só."""
    def __init__(self):
        self.revisoes = []   # [{'id', 'numero', 'motivo', 'arquivos', 'geracao_id', 'legado'}]

    def fazenda(self, cod):
        return {'cod_faz': cod, 'nome': 'POSSES'}

    def proximo_numero(self, cod_faz, documento):
        return len(self.revisoes)

    def publicar_revisao(self, cod_faz, documento, motivo, numero, arquivos, geracao_id=None, legado=False):
        if numero != len(self.revisoes):
            raise RuntimeError('número da revisão mudou')
        if numero > 0 and not motivo:
            raise RuntimeError('motivo obrigatório')
        rev = {'id': 11 + numero, 'numero': numero, 'motivo': motivo, 'geracao_id': geracao_id, 'legado': legado,
               'arquivos': [a['nome'] for a in arquivos]}
        self.revisoes.append(rev)
        return rev['id']


class _GhFalso:
    def __init__(self, falhar_em=None):
        self.falhar_em, self.enviados = falhar_em, []

    def release(self, tag, titulo):
        assert tag == 'drone-10156'
        return {'id': 1, 'assets': []}

    def subir(self, rel, caminho, nome):
        if self.falhar_em and nome.endswith(self.falhar_em):
            raise RuntimeError('GitHub fora')
        self.enviados.append(nome)
        return f'https://x/{nome}', 1


def _arquivos(tmp_path, pdf=True):
    zip_, pdf_ = tmp_path / 'p.zip', tmp_path / 'p.pdf'
    zip_.write_bytes(b'z')
    pdf_.write_bytes(b'p')
    return {'zip': zip_, 'pdf': pdf_ if pdf else None}


def test_publicar_cria_rev0_e_registra_zip_e_pdf(tmp_path):
    b = _BancoFalso()
    rev = publicar(b, _GhFalso(), 10156, 'normal', None, _arquivos(tmp_path), geracao_id=3)
    assert rev == 11
    assert b.revisoes[0]['arquivos'] == ['10156_POSSES_Rev0-Normal.zip', '10156_POSSES_Rev0-Normal.pdf']
    assert b.revisoes[0]['geracao_id'] == 3


def test_catacao_nova_revisao_usa_motivo_padrao(tmp_path):
    b = _BancoFalso()
    publicar(b, _GhFalso(), 10156, 'catacao', None, _arquivos(tmp_path, pdf=False))
    publicar(b, _GhFalso(), 10156, 'catacao', None, _arquivos(tmp_path, pdf=False))
    assert b.revisoes[-1]['motivo'] == 'Novo levantamento de infestação'
    assert b.revisoes[-1]['numero'] == 1


def test_normal_nova_revisao_sem_motivo_da_erro_sem_subir_nada(tmp_path):
    b = _BancoFalso()
    publicar(b, _GhFalso(), 10156, 'normal', None, _arquivos(tmp_path))
    gh = _GhFalso()
    with pytest.raises(RuntimeError, match='motivo'):
        publicar(b, gh, 10156, 'normal', None, _arquivos(tmp_path))
    assert gh.enviados == []


def test_falha_no_github_nao_mexe_no_banco_e_repetir_publica_uma_vez(tmp_path):
    b = _BancoFalso()
    with pytest.raises(RuntimeError, match='GitHub'):
        publicar(b, _GhFalso(falhar_em='.pdf'), 10156, 'normal', None, _arquivos(tmp_path))
    assert b.revisoes == []            # portal continua mostrando a revisão anterior
    rev = publicar(b, _GhFalso(), 10156, 'normal', None, _arquivos(tmp_path))
    assert rev == 11 and len(b.revisoes) == 1


def test_revisao_prevista_diferente_recusa_antes_de_subir(tmp_path):
    b = _BancoFalso()
    publicar(b, _GhFalso(), 10156, 'catacao', None, _arquivos(tmp_path))
    gh = _GhFalso()
    with pytest.raises(RuntimeError, match='Rev0.*Rev1'):
        publicar(b, gh, 10156, 'catacao', None, _arquivos(tmp_path), numero_esperado=0)
    assert gh.enviados == [] and len(b.revisoes) == 1


def test_legado_vai_marcado_para_o_banco(tmp_path):
    b = _BancoFalso()
    publicar(b, _GhFalso(), 10156, 'normal', 'Importado do legado', _arquivos(tmp_path, pdf=False), legado=True)
    assert b.revisoes[0]['legado'] is True and b.revisoes[0]['arquivos'] == ['10156_POSSES_Rev0-Normal.zip']
