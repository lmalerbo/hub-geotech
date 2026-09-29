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
    """Revisões de um único projeto/documento; a última é a vigente."""
    def __init__(self):
        self.revisoes, self.arquivos = [], []   # revisoes: [{'id', 'numero', 'motivo'}]

    def fazenda(self, cod):
        return {'cod_faz': cod, 'nome': 'POSSES'}

    def projeto_individual(self, cod, nome):
        return 7

    def revisao_vigente(self, projeto_id, documento):
        return self.revisoes[-1] if self.revisoes else None

    def nova_revisao(self, projeto_id, documento, motivo):
        if self.revisoes and not motivo:
            raise RuntimeError('motivo obrigatório')
        rev = {'id': 11 + len(self.revisoes), 'numero': len(self.revisoes), 'motivo': motivo}
        self.revisoes.append(rev)
        return rev

    def arquivos_da_revisao(self, revisao_id):
        return [nome for r, nome in self.arquivos if r == revisao_id]

    def registrar_arquivo(self, revisao_id, nome, url, tamanho):   # upsert, como o real
        if (revisao_id, nome) not in self.arquivos:
            self.arquivos.append((revisao_id, nome))


class _GhFalso:
    def __init__(self, falhar_em=None):
        self.falhar_em = falhar_em

    def release(self, tag, titulo):
        assert tag == 'drone-10156'
        return {'id': 1, 'assets': []}

    def subir(self, rel, caminho, nome):
        if self.falhar_em and nome.endswith(self.falhar_em):
            raise RuntimeError('GitHub fora')
        return f'https://x/{nome}', 1


def _arquivos(tmp_path, pdf=True):
    zip_, pdf_ = tmp_path / 'p.zip', tmp_path / 'p.pdf'
    zip_.write_bytes(b'z')
    pdf_.write_bytes(b'p')
    return {'zip': zip_, 'pdf': pdf_ if pdf else None}


def test_publicar_cria_rev0_e_registra_zip_e_pdf(tmp_path):
    b = _BancoFalso()
    rev = publicar(b, _GhFalso(), 10156, 'normal', None, _arquivos(tmp_path))
    assert rev == 11
    assert b.arquivos == [(11, '10156_POSSES_Rev0-Normal.zip'), (11, '10156_POSSES_Rev0-Normal.pdf')]


def test_catacao_nova_revisao_usa_motivo_padrao(tmp_path):
    b = _BancoFalso()
    publicar(b, _GhFalso(), 10156, 'catacao', None, _arquivos(tmp_path, pdf=False))
    publicar(b, _GhFalso(), 10156, 'catacao', None, _arquivos(tmp_path, pdf=False))
    assert b.revisoes[-1]['motivo'] == 'Novo levantamento de infestação'
    assert b.revisoes[-1]['numero'] == 1


def test_normal_nova_revisao_sem_motivo_da_erro(tmp_path):
    b = _BancoFalso()
    publicar(b, _GhFalso(), 10156, 'normal', None, _arquivos(tmp_path))
    with pytest.raises(RuntimeError, match='motivo'):
        publicar(b, _GhFalso(), 10156, 'normal', None, _arquivos(tmp_path))


def test_repetir_depois_de_falha_no_github_reaproveita_a_revisao(tmp_path):
    b = _BancoFalso()
    with pytest.raises(RuntimeError, match='GitHub'):
        publicar(b, _GhFalso(falhar_em='.pdf'), 10156, 'normal', None, _arquivos(tmp_path))
    rev = publicar(b, _GhFalso(), 10156, 'normal', None, _arquivos(tmp_path))
    assert len(b.revisoes) == 1 and rev == 11
    assert sorted(b.arquivos_da_revisao(11)) == ['10156_POSSES_Rev0-Normal.pdf', '10156_POSSES_Rev0-Normal.zip']
