# Arquivos de amostra do paralelismo

**Os arquivos `amostra.*` não vão para o git:** têm GPS real e este repositório é público (ver `.gitignore`). Para rodar `pytest -m dados_reais`, copie-os da origem abaixo (`EXECUTADOS\2026-2027\BRUTOS`) para esta pasta, sem alterar, com os nomes da tabela. Os números são os que o `base-op` dá para eles (commit `935543c`).

| Arquivo | Origem | Números |
|---|---|---|
| `amostra.jdl` | `TORTA\10233Rev0\55804\JD-Data\log\2026_08_23_[16_29]_{f4208b65-cef3-4444-af5e-f76c65a7e08d}.jdl` | 10.682 pontos com trabalho, 23.663 ticks |
| `amostra.fdl` + `amostra.fdd` | `CANA\10966Rev0\64086\GS3_2630\64086\RCD\EIC\Documentation\F8\6aca18f8-0000-1000-7118-e1e1e13fcac8` | 366 pontos da antena 5140, 366 registros |

A regressão completa (`test_regressao.py`) usa `TORTA\10233Rev0` e `CANA\10966Rev0`, por `PARALELISMO_10233` e `PARALELISMO_10966`. No GS3, cada subpasta de `10966Rev0` é uma frota, porque o LSFP só liga pontos da mesma frota.
