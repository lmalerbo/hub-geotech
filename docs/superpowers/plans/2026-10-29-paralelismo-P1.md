# Paralelismo P1: banco, níveis e declividade

Detalha a seção P1 do [plano mestre](2026-10-29-paralelismo.md). O código e os testes estão nos arquivos abaixo. Foram conferidos num Postgres local temporário, sem PostGIS: a coluna geométrica e as funções `ST_*` são stubs só nos testes, portanto a parte geométrica só roda de verdade no Supabase.

**Arquivos:**
- `supabase/migrations/20261104090000_paralelismo.sql` e `volta/20261104090000_paralelismo_volta.sql`
- `tests/paralelismo/conftest.py`, `tests/paralelismo/test_banco_sql.py`
- `app/usuarios.js`, `app/index.html`, `tests/app/usuarios_puro.test.js`
- `ingestao/base_fazendas.py`, `tests/ingestao/test_base_fazendas.py`

## Ajustes em relação ao plano mestre

1. **Nome da migration:** `20261104090000`, posterior à última que já existe.
2. **Cartão em Ferramentas sai da P1 e vai para a P3.** Antes da página existir, ele levaria a um link quebrado.
3. **`paralelismo_linhas_vigentes` devolve `{analise_id, linhas}` e aceita `p_rodada_id`.** A prévia precisa do id da vigente para mandar `base_analise_id`, e o editor precisa das linhas da rodada pendente para refazer `limpar` + PLL.
4. **`base_analise_id` vem da tela, no envio.** É a vigente na hora da prévia; calcular no envio deixaria passar uma publicação feita entre a prévia e o envio.
5. **Arquivo de rodada recusada pode voltar.** `sha256` é chave primária, então `enviar` libera os registros de rodada recusada antes de conferir repetidos.
6. **Excluir recusa também quando há prévia pendente baseada na rodada** (`rodada_pendente_depende`), porque essa prévia já embute as linhas excluídas. Isso completa a decisão 4.
7. **Reserva de id com dono e memória** (`paralelismo_reservas`, nunca apagada; a decisão 2 só proíbe linha em `paralelismo_rodadas`). Só quem reservou usa o id, e id já enviado não volta, mesmo com a rodada excluída: assim um reenvio não sobrescreve a release que fica como prova. `rodada_ja_enviada` no reenvio deve ser tratado pela tela como sucesso.
8. **Excluir apaga também a linha da rodada.** A tag fica em `log_auditoria`, por fazenda, e a release continua no GitHub.
9. **Publicar e excluir usam a mesma trava** (`pg_advisory_xact_lock`), para não trocarem a vigente ao mesmo tempo.
10. **Frotas não entram na migration.** O repositório é público e a tabela tem séries reais de tratores: a carga fica para a P4/P6, fora do git.
11. **`enviar` confere o payload:** sha repetido, linha sem análise da mesma fazenda e operação, somas das amostras (`check`) e links só `https`. Usa a mesma trava de publicar e excluir.
12. **Na P4:** as telas continuam tratando `partes[].url` e `amostras_url` como dado não confiável. `leitura` consegue ler `partes`; rever ao tornar o repositório privado.

## Ordem de entrega

1. Revisão de código e correções.
2. O **usuário** aplica a migration no SQL Editor do Supabase.
3. Só depois: merge e push. A ingestão da Base Fazendas passa a gravar `declividade`, e falharia se a coluna ainda não existisse.
4. Conferir no Supabase, com uma rodada de teste apagada em seguida, a parte que os stubs não cobrem: gravar uma linha geométrica e lê-la de volta por `paralelismo_linhas_vigentes` e `paralelismo_talhoes_fazenda`, com `st_srid` = 31983 e `st_geometrytype` = LineString; e, na P3, enviar o payload real da maior fazenda (10966) para ver se cabe no tempo limite do `authenticated`.
