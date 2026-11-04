"""Leitores com arquivos montados aqui, com coordenadas inventadas: rodam no pytest normal,
sem as amostras reais (que ficam fora do git, ver tests/dados/paralelismo/LEIAME.md)."""
import struct

import pytest

from paralelismo.gs3 import ler_gs3
from paralelismo.jdl import ler_jdl


def varint(v):
    saida = bytearray()
    while v > 0x7F:
        saida.append(v & 0x7F | 0x80)
        v >>= 7
    return bytes(saida) + bytes([v])


def campo_int(n, v):
    return varint(n << 3) + varint(v)


def campo_f64(n, v):
    return varint(n << 3 | 1) + struct.pack('<d', v)


def campo_bytes(n, b):
    return varint(n << 3 | 2) + varint(len(b)) + b


def zigzag(v):
    return v << 1 if v >= 0 else (-v << 1) - 1


def registro_jdl(inicio, duracao, itens):
    corpo = campo_int(4, inicio) + duracao + campo_bytes(9, b''.join(campo_bytes(3, i) for i in itens))
    return campo_bytes(4, corpo)


def item_rico(lat, lon, deltas):
    return (campo_f64(1, lat * 1e9) + campo_f64(2, lon * 1e9) + campo_f64(4, 1_000_000.0)
            + campo_bytes(12, b''.join(varint(zigzag(d)) for d in deltas))
            + campo_bytes(13, b''.join(varint(zigzag(d)) for d in deltas)))


def item_estado(instante, estado):
    return campo_int(1, 0) + campo_int(2, 0) + campo_bytes(3, bytes([0x0a, 0x01, estado])) + campo_int(12, instante)


def jdl_sintetico():
    """5 ticks em 1200, 1400, ..., 2000 ms; o trabalho liga em 1500 ms: sobram 3."""
    return registro_jdl(1000, campo_int(5, 1000), [item_rico(-22.0, -48.0, [1000] * 5), item_estado(1500, 1)])


def test_jdl_so_pontos_com_trabalho(tmp_path):
    f = tmp_path / 'a.jdl'
    f.write_bytes(jdl_sintetico())
    pontos, ticks = ler_jdl(str(f))
    assert ticks == 5 and len(pontos) == 3
    assert pontos[0] == pytest.approx((-22.0 + 3e-6, -48.0 + 3e-6))


def test_jdl_cortado_em_qualquer_byte_nao_quebra(tmp_path):
    dados = jdl_sintetico()
    f = tmp_path / 'a.jdl'
    for corte in range(len(dados)):
        f.write_bytes(dados[:corte])
        pontos, ticks = ler_jdl(str(f))
        assert len(pontos) <= 3 and ticks <= 5


def test_jdl_com_duracao_nan_conta_como_ilegivel(tmp_path):
    f = tmp_path / 'a.jdl'
    f.write_bytes(registro_jdl(1000, campo_f64(5, float('nan')), [item_rico(-22.0, -48.0, [1000] * 5)]))
    assert ler_jdl(str(f)) == ([], 0)


def test_jdl_inexistente(tmp_path):
    assert ler_jdl(str(tmp_path / 'nao_existe.jdl')) == ([], 0)


ESTADOS = ['dtiRecordingStatusOn', 'dtiRecordingStatusOff']
MARCADOR = b'\x02\x00\x00\x02\x00\x70\x00'
COL_ESTADO = 4


def coluna_numerica(nome, inicial):
    n = nome.encode()
    return (struct.pack('<HHH', 4, len(n) + 3, len(n)) + n + b'\x00' + struct.pack('<H', 24)
            + struct.pack('<3d', 1e-6, 0.0, inicial))


def coluna_estado(nome):
    n = nome.encode()
    nomes = b''.join(struct.pack('<H', len(e)) + e.encode() for e in ESTADOS)
    return (struct.pack('<HHH', 1, len(n) + 3, len(n)) + n + b'\x00'
            + struct.pack('<HH', len(ESTADOS), len(nomes)) + nomes)


def registro_gs3(estado=None):
    extras = b'' if estado is None else struct.pack('<HHh', 1, 2, estado)
    mascara_b = 0 if estado is None else 1 << COL_ESTADO
    return MARCADOR + struct.pack('<II', 0, mascara_b) + struct.pack('<4i', 10, 10, 20, 20) + extras


def fdd_sintetico():
    """Colunas das duas antenas e o estado; 4 registros, o 3º com a gravação desligada."""
    catalogo = (struct.pack('<H', 5) + coluna_numerica('GPSLatitude_5140', -22.0)
                + coluna_numerica('GPSLongitude_5140', -48.0) + coluna_numerica('GPSLatitude_5141', -23.0)
                + coluna_numerica('GPSLongitude_5141', -49.0) + coluna_estado('Section1_State'))
    return b'\xff\xff' + catalogo + registro_gs3(0) + registro_gs3() + registro_gs3(1) + registro_gs3(0)


FDL = ('<RCDLogFile><rcdsetup:Farm erid="f1" name="99999Rev0" />'
       '<rcdsetup:Field erid="t1" name="1" farmRef="f1" /><FieldRef eridRef="t1" />'
       '<LogTaskRegion timeStamp="2026-10-10T10:52:40.400Z" />'
       '<EvenByteDelta filePosition="0" /></RCDLogFile>')


def sessao(tmp_path, fdd=None):
    (tmp_path / 's.fdl').write_text(FDL, encoding='latin-1')
    if fdd is not None:
        (tmp_path / 's.fdd').write_bytes(fdd)
    return str(tmp_path / 's.fdl')


def test_gs3_antena_do_trator_com_gravacao_ligada(tmp_path):
    pontos, registros = ler_gs3(sessao(tmp_path, fdd_sintetico()))
    assert registros == 4 and len(pontos) == 3
    assert pontos[0] == pytest.approx((-22.0 + 10e-6, -48.0 + 10e-6))


def test_gs3_fdd_cortado_em_qualquer_byte_nao_quebra(tmp_path):
    dados = fdd_sintetico()
    for corte in range(len(dados)):
        pontos, registros = ler_gs3(sessao(tmp_path, dados[:corte]))
        assert len(pontos) <= 3 and registros <= 4


def test_gs3_sem_fdd(tmp_path):
    assert ler_gs3(sessao(tmp_path)) == ([], 0)
