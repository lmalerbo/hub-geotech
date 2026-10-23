# Publicação: tela de Usuários e fluxo de projetos (23/10/2026)

Ordem: **Usuários primeiro** (GeoMap → banco do Hub → função → app), **depois o fluxo** (banco → app).
Comandos do Hub rodam na raiz do repositório, com a CLI ligada ao projeto
(`supabase link --project-ref dpvsivypabmvmrrpgmhc`). Quem preferir pode colar os mesmos arquivos no SQL Editor.

## Já feito e conferido (sem gravar nada em produção)

- Testes locais: Hub 53 pytest (`tests/fluxo`, `tests/contas`) + 42 node; GeoMap 119.
- Cadeia inteira de migrações (28) num Postgres local, com stubs de Supabase, PostGIS e Storage
  (`tests/fluxo/hublocal.py`). As 88 funções do banco real são idênticas às da cadeia local (sem deriva).
- Volta do fluxo gerada da cadeia (`tests/fluxo/gerar_volta.py`) e testada (`tests/fluxo/testar_volta.py`):
  funções, permissões e view voltam iguais; `etapa_status` do Preparo é reconstruído pela etapa dos talhões.
- Ensaio no banco real numa transação desfeita (níveis + fluxo + ponta a ponta + volta), impressão digital
  igual antes e depois:
  - conversão de níveis: totais por módulo iguais; Corretivos vira editor (8);
  - Preparo: Identificação 78, Observações 9, Ok 373; fazendas 10329/10828 não têm talhão (ficam fora);
  - portal: +5 arquivos (PDF do "projeto" escondido atrás de um .dwg mais novo), nenhum some;
  - avançar / voltar com justificativa / desfazer no Preparo e no Plantio, revisão nova (número = maior + 1),
    linha do tempo, RPC antiga da tela publicada, leitor recusado: tudo certo;
  - volta: 0 funções diferentes, view igual, `etapa_status` igual.

## Parte 1 — Usuários

1. **GeoMap, banco (Neon):** em `geomap-acesso-mapa/backend`, com o `.env` de produção:
   `node --env-file=../../geomap/backend/.env src/db/migrate.js` → deve aplicar só `020_permissoes_usuario.sql`.
   Só acrescenta tabela e view; o GeoMap publicado continua igual.
2. **GeoMap, código:** merge de `feat/acesso-por-mapa` em `master` e push (Render publica).
3. **Hub, banco:** `supabase db query --linked -f supabase/migrations/20261023090000_niveis_por_modulo.sql`.
   A partir daqui a tela Usuários publicada fica fora até o passo 5 (minutos). O resto do Hub funciona.
   Conferir:
   ```sql
   select m.nivel, m.modulo_id, count(*) from hub.usuario_modulos m group by 1, 2 order by 1, 2;
   -- editor: colheita 3, corretivos 8, drone 3, plantio 3, preparo 3; leitura: colheita 12, drone 9, plantio 12, preparo 12
   select proname from pg_proc where pronamespace='hub'::regnamespace and prosrc ~* '\mpapel\M';
   -- só acesso_salvar e acesso_remover
   ```
4. **Função:** `supabase functions deploy contas --project-ref dpvsivypabmvmrrpgmhc`.
5. **App:** push do `main` com o merge da `usuarios-niveis` (GitHub Pages publica).
6. **Conferência (Leo):** `python -m pytest -m banco tests/contas/test_funcao_contas.py` e
   `python tests/app/teste_drone_tela.py` com `HUB_CONTA_TESTE`; na tela, três pessoas reais, um mapa
   individual "Ver" numa conta `@hub.local` (aparece no GeoMap, some ao tirar).

**Voltar a Usuários:** reverter o merge no `main` e push; republicar a função `contas` da versão anterior;
`supabase db query --linked -f supabase/migrations/volta/20261023090000_niveis_por_modulo_volta.sql`
(ensaiada no banco real: devolve as funções idênticas). GeoMap: reverter o merge (a tabela fica sem uso).
**Se o fluxo já estiver publicado, voltar o fluxo antes** (a volta de Usuários recria uma `nova_revisao` antiga).

## Parte 2 — Fluxo de projetos

1. Impressão digital antes: `supabase db query --linked -o csv -f tests/fluxo/impressao_banco.sql > antes.csv`.
2. **Banco:** `supabase db query --linked -f supabase/migrations/20261023100000_fluxo_projetos.sql`.
   A tela publicada continua funcionando (as RPCs antigas chamam as novas).
3. **App:** merge de `fluxo-integracao` no `main` e push.
4. **Ponta a ponta no banco real:** `supabase db query --linked -o csv -f tests/fluxo/ponta_a_ponta_banco_real.sql`
   (transação desfeita no fim). Tirar a impressão digital logo antes e logo depois dele: as duas têm de ser
   iguais. (A do passo 1 muda com a migração, porque as tabelas ganham colunas.)
5. **Na tela (Leo):** abrir Projetos, avançar um talhão, voltar com justificativa, desfazer.

**Voltar o fluxo:** reverter o merge no `main` e push;
`supabase db query --linked -f supabase/migrations/volta/20261023100000_fluxo_projetos_volta.sql`.
Colunas e tabela novas ficam (histórico); para reaplicar o fluxo depois, rodar antes o bloco comentado no
fim do script de volta.
