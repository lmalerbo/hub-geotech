import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'migracao'))
from trazer_usuarios_geomap import ja_migrado, planejar  # noqa: E402

G = {
    'ana@x.com': {'nome': 'Ana', 'hash': '$2b$10$' + 'a' * 53, 'ativo': True, 'admin': True, 'grupos': [1, 2], 'senha_provisoria': False},
    'beto@x.com': {'nome': 'Beto', 'hash': '$2b$10$' + 'b' * 53, 'ativo': True, 'admin': False, 'grupos': [], 'senha_provisoria': True},
    'caio@x.com': {'nome': 'Caio', 'hash': '$2b$10$' + 'c' * 53, 'ativo': False, 'admin': False, 'grupos': [3], 'senha_provisoria': False},
}
A = {'ana@x.com': {'nome': 'Ana Paula', 'papel': 'editor', 'admin': True, 'modulos': ['plantio']}}


def test_mantem_campos_do_hub_e_traz_os_do_geomap():
    p = {x['email']: x for x in planejar(G, A)}
    assert p['ana@x.com']['acesso'] == {'email': 'ana@x.com', 'nome': 'Ana Paula', 'papel': 'editor', 'admin': True,
                                        'modulos': ['plantio'], 'geomap_ativo': True, 'geomap_admin': True, 'geomap_grupos': [1, 2]}
    assert p['ana@x.com']['copiar_hash'] is True and p['ana@x.com']['precisa_trocar_senha'] is False


def test_senha_provisoria_do_geomap_nao_e_copiada():
    beto = next(x for x in planejar(G, A) if x['email'] == 'beto@x.com')
    assert beto['copiar_hash'] is False and beto['precisa_trocar_senha'] is True
    assert beto['acesso']['papel'] == 'leitura' and beto['acesso']['modulos'] == []


def test_inativo_no_geomap_fica_sem_geomap_e_bloqueado():
    caio = next(x for x in planejar(G, A) if x['email'] == 'caio@x.com')
    assert caio['acesso']['geomap_ativo'] is False and caio['acesso']['geomap_grupos'] == []
    assert caio['bloquear'] is True


def test_acesso_do_hub_sem_geomap_continua():
    p = planejar(G, {**A, 'so-hub@x.com': {'nome': 'Só Hub', 'papel': 'leitura', 'admin': False, 'modulos': ['preparo']}})
    so = next(x for x in p if x['email'] == 'so-hub@x.com')
    assert so['acesso']['geomap_ativo'] is False and so['copiar_hash'] is False and so['bloquear'] is False


def test_contas_de_servico_do_geomap_ficam_de_fora():
    # Revisão final: automacao@geoportal.local (admin no GeoMap) mantém o login próprio do GeoMap;
    # contas @geoportal.local são de serviço/teste e não viram contas do Hub.
    g = {**G, 'automacao@geoportal.local': {'nome': 'Automação', 'hash': '$2b$10$' + 'z' * 53, 'ativo': True,
                                            'admin': True, 'grupos': [], 'senha_provisoria': False}}
    assert 'automacao@geoportal.local' not in {x['email'] for x in planejar(g, A)}


def test_segunda_execucao_e_recusada_depois_da_virada():
    # Revisão final: rodar de novo depois da virada desfaria senhas trocadas no Hub.
    assert ja_migrado({'ana@x.com': {'geomap_ativo': False}}) is False
    assert ja_migrado({'ana@x.com': {'geomap_ativo': True}}) is True


def test_simulacao_roda_antes_do_sql_da_virada():
    # Ensaio de 22/10: a simulação (passo 3 do runbook) vem ANTES do SQL que cria acessos.geomap_ativo (passo 4).
    from trazer_usuarios_geomap import colunas_acessos
    assert 'geomap_ativo' not in colunas_acessos(simular=True)
    assert 'geomap_ativo' in colunas_acessos(simular=False)      # a de verdade precisa dela para recusar 2ª execução
