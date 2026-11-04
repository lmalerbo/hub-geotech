"""O que o Web Worker chama no Pyodide: um arquivo por vez, e só as linhas ficam (spec §8). Arquivos sintéticos."""
import io
import json
import os
import zipfile

import pytest

from paralelismo import navegador
from paralelismo.analise import analisar_fazenda, linhas_do_grupo, para_utm
from paralelismo.navegador import Grupo, analisar
from tests.paralelismo.test_leitores_sinteticos import FDL, campo_int, fdd_sintetico, item_rico, jdl_sintetico, registro_jdl


def escrever_jdl(tmp_path, nome='a.jdl', dados=None):
    f = tmp_path / nome
    f.write_bytes(jdl_sintetico() if dados is None else dados)
    return str(f)


def escrever_gs3(tmp_path):
    (tmp_path / 's.fdl').write_text(FDL, encoding='latin-1')
    (tmp_path / 's.fdd').write_bytes(fdd_sintetico())
    return str(tmp_path / 's.fdl')


def test_ler_devolve_contagens_e_apaga_o_arquivo(tmp_path):
    caminho = escrever_jdl(tmp_path)
    r = Grupo('90001').ler('jdl', caminho, '2026-10-10')
    assert r == {'pontos': 3, 'registros': 5, 'legivel': True}
    assert not os.path.exists(caminho)


def test_ler_gs3_apaga_o_fdl_e_o_fdd(tmp_path):
    caminho = escrever_gs3(tmp_path)
    r = Grupo('90001').ler('gs3', caminho, '2026-10-10')
    assert r == {'pontos': 3, 'registros': 4, 'legivel': True}
    assert list(tmp_path.iterdir()) == []


def test_ler_apaga_o_arquivo_mesmo_se_o_leitor_estourar(tmp_path, monkeypatch):
    caminho = escrever_jdl(tmp_path)
    def estoura(_):
        raise MemoryError
    monkeypatch.setattr(navegador, 'ler_jdl', estoura)
    assert Grupo('90001').ler('jdl', caminho, None)['legivel'] is False
    assert not os.path.exists(caminho)


def test_arquivo_ilegivel_nao_quebra_e_o_grupo_segue(tmp_path):
    g = Grupo('90001')
    assert g.ler('jdl', escrever_jdl(tmp_path, 'ruim.jdl', b'isto nao e um jdl'), '2026-10-09') == {
        'pontos': 0, 'registros': 0, 'legivel': False}
    assert g.ler('jdl', escrever_jdl(tmp_path), '2026-10-10')['pontos'] == 3
    assert g.fechar()['frota'] == '90001'


def test_trilha_sem_trabalho_e_legivel(tmp_path):
    so_trilha = registro_jdl(1000, campo_int(5, 1000), [item_rico(-22.0, -48.0, [1000] * 5)])
    r = Grupo('90001').ler('jdl', escrever_jdl(tmp_path, dados=so_trilha), None)
    assert r == {'pontos': 0, 'registros': 5, 'legivel': True}


def test_tipo_desconhecido_e_erro(tmp_path):
    with pytest.raises(ValueError):
        Grupo('90001').ler('pth', escrever_jdl(tmp_path), None)


def test_fechar_da_as_mesmas_linhas_da_regressao(tmp_path, monkeypatch):
    lotes = iter([[(-22.0, -48.0 + i * 1e-5) for i in range(200)], [(-22.0, -48.0 + (200 + i) * 1e-5) for i in range(200)]])
    monkeypatch.setattr(navegador, 'ler_jdl', lambda _: (next(lotes), 200))
    g = Grupo('90001')
    g.ler('jdl', escrever_jdl(tmp_path, '1.jdl'), '2026-10-10')
    g.ler('jdl', escrever_jdl(tmp_path, '2.jdl'), '2026-10-10')
    r = g.fechar()
    esperadas = linhas_do_grupo(para_utm([(-22.0, -48.0 + i * 1e-5) for i in range(400)]))
    assert r['linhas'] and r['linhas'] == [
        {'frota': '90001', 'data': '2026-10-10', 'coords': [list(c) for c in l.coords]} for l in esperadas]


def test_data_das_linhas_e_a_com_mais_pontos(tmp_path, monkeypatch):
    lotes = iter([[(-22.0, -48.0 + i * 1e-5) for i in range(100)], [(-22.0, -48.0 + (100 + i) * 1e-5) for i in range(300)]])
    monkeypatch.setattr(navegador, 'ler_jdl', lambda _: (next(lotes), 0))
    g = Grupo('90001')
    g.ler('jdl', escrever_jdl(tmp_path, '1.jdl'), '2026-09-30')
    g.ler('jdl', escrever_jdl(tmp_path, '2.jdl'), '2026-10-01')
    r = g.fechar()
    assert r['data'] == '2026-10-01' and {l['data'] for l in r['linhas']} == {'2026-10-01'}


def test_sem_data_em_nenhum_arquivo_fica_nula(tmp_path):
    g = Grupo('90001')
    g.ler('jdl', escrever_jdl(tmp_path), None)
    assert g.fechar()['data'] is None


def test_fechar_descarta_os_pontos_e_nao_fecha_duas_vezes(tmp_path):
    g = Grupo('90001')
    g.ler('jdl', escrever_jdl(tmp_path), '2026-10-10')
    g.fechar()
    assert g.pontos is None
    with pytest.raises(RuntimeError):
        g.fechar()
    with pytest.raises(RuntimeError):
        g.ler('jdl', escrever_jdl(tmp_path), '2026-10-10')


def test_duracoes_do_jdl_e_aviso_de_frota_sem_trabalho(tmp_path, monkeypatch):
    # 2 h de trilha (36.000 ticks de 0,2 s) e 3.000 ticks com trabalho: 8%.
    monkeypatch.setattr(navegador, 'ler_jdl', lambda _: ([(-22.0, -48.0)] * 3000, 36000))
    g = Grupo('90001')
    g.ler('jdl', escrever_jdl(tmp_path), None)
    r = g.fechar()
    assert r['duracao_total_s'] == pytest.approx(7200) and r['duracao_trabalho_s'] == pytest.approx(600)
    assert r['sem_trabalho'] is True


def test_duracoes_do_gs3_contam_um_segundo_por_registro(tmp_path, monkeypatch):
    monkeypatch.setattr(navegador, 'ler_gs3', lambda _: ([(-22.0, -48.0)] * 200, 7200))
    g = Grupo('90001')
    g.ler('gs3', escrever_gs3(tmp_path), None)
    r = g.fechar()
    assert r['duracao_total_s'] == pytest.approx(7200) and r['sem_trabalho'] is True


def test_grupo_com_trabalho_nao_avisa(tmp_path, monkeypatch):
    monkeypatch.setattr(navegador, 'ler_jdl', lambda _: ([(-22.0, -48.0)] * 30000, 36000))
    g = Grupo('90001')
    g.ler('jdl', escrever_jdl(tmp_path), None)
    assert g.fechar()['sem_trabalho'] is False


def passadas(espacamento=3.0, n=4, comprimento=300.0, x0=500000.0, y0=7500000.0):
    return [{'frota': '90001', 'data': '2026-10-10',
             'coords': [[x0, y0 + i * espacamento], [x0 + comprimento, y0 + i * espacamento]]} for i in range(n)]


FC_VAZIA = {'type': 'FeatureCollection', 'features': []}


def test_analisar_igual_ao_analisar_fazenda():
    json_saida, _ = analisar(json.dumps(passadas()), json.dumps(FC_VAZIA), 'torta_99999')
    r = json.loads(json_saida)
    assert r == json.loads(json.dumps(analisar_fazenda(passadas(), {})))
    assert r['pll_total'] > 0


def test_analisar_usa_os_talhoes_do_geojson():
    fc = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {'talhao': 7}, 'geometry': {
        'type': 'Polygon', 'coordinates': [[[-46, -24], [-44, -24], [-44, -20], [-46, -20], [-46, -24]]]}}]}
    r = json.loads(analisar(json.dumps(passadas()), json.dumps(fc), 'x')[0])
    assert [t['talhao_num'] for t in r['talhoes']] == [7] and r['fora_talhao'] == 0


def test_analisar_sem_linhas_zera_e_gera_zip_valido():
    json_saida, dados = analisar('[]', json.dumps(FC_VAZIA), 'x')
    r = json.loads(json_saida)
    assert (r['pll_total'], r['amostras'], r['mes']) == (0, 0, None)
    assert zipfile.ZipFile(io.BytesIO(dados)).testzip() is None


def test_analisar_shapefile_tem_amostras_e_linhas():
    _, dados = analisar(json.dumps(passadas()), json.dumps(FC_VAZIA), 'torta_99999')
    z = zipfile.ZipFile(io.BytesIO(dados))
    assert {'torta_99999_Amostras.shp', 'torta_99999_Linhas.shp', 'torta_99999_Linhas.prj'} <= set(z.namelist())


def test_analisar_com_linha_sem_data_grava_shapefile():
    linhas = [{**l, 'data': None} for l in passadas()]
    json_saida, dados = analisar(json.dumps(linhas), json.dumps(FC_VAZIA), 'x')
    assert json.loads(json_saida)['mes'] is None
    assert zipfile.ZipFile(io.BytesIO(dados)).testzip() is None


def test_publicado_no_modulo_paralelismo():
    from mapas.publicar import MODULOS
    assert 'paralelismo/navegador.py' in MODULOS['paralelismo']
