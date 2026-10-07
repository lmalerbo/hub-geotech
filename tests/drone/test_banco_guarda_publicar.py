"""Integração (banco real, só leitura na prática: a chamada falha e a transação é desfeita).
Roda com: python -m pytest tests/drone/test_banco_guarda_publicar.py -m banco"""
import pytest

pytestmark = pytest.mark.banco


def test_publicar_geracao_sem_talhoes_e_recusado():
    from drone.banco import DroneBanco
    b = DroneBanco()
    with pytest.raises(RuntimeError, match='sem talhões'):
        b.publicar_revisao(10974, 'normal', 'teste da trava', 99, [], geracao_id=0)
