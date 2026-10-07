from drone.migrar_parte2 import origem_da_revisao


def test_origem_da_revisao():
    assert origem_da_revisao('Importado do legado (consolidado: 24/25 Rev1)') == 'legado'
    assert origem_da_revisao('Novo levantamento de infestação') == 'sistema'
    assert origem_da_revisao(None) == 'sistema'
