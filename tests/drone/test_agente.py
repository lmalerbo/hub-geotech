from drone.agente import limpar_previas


class _BancoFalso:
    def __init__(self, linhas):
        self.linhas, self.apagados, self.limpos = linhas, [], []

    def previas_para_apagar(self):
        return self.linhas

    def apagar_previas(self, destinos):
        self.apagados.extend(destinos)

    def limpar_previa(self, geracao_id, descartar):
        self.limpos.append((geracao_id, descartar))


def test_apaga_previas_descartadas_e_vencidas():
    b = _BancoFalso([
        {'id': 1, 'status': 'descartada', 'previa_zip': 'geracao-1/1.zip', 'previa_pdf': 'geracao-1/1.pdf'},
        {'id': 2, 'status': 'pronta', 'previa_zip': 'geracao-2/2.zip', 'previa_pdf': 'geracao-2/2.pdf'},
    ])
    limpar_previas(b)
    assert b.apagados == ['geracao-1/1.zip', 'geracao-1/1.pdf', 'geracao-2/2.zip', 'geracao-2/2.pdf']
    # a pronta vencida (30 dias) não pode mais ser publicada: vira descartada
    assert b.limpos == [(1, False), (2, True)]
