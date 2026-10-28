# Preparo: mês de entrega no lugar do mês de plantio + ciclo 25-26 — design

Data: 28/10/2026. Levantamento feito com o usuário em 28/10 (memória `project-preparo-mes-ciclo`).

## Problema

O Preparo (Sistematização) usa o **mês de plantio do PLANAGRI** ("MÊS PLANTIO (PLAN)") como se fosse o mês do preparo. Esse mês diz quando se planta, não quando o projeto foi feito ou usado. Aparece em dois lugares:

- **Hub, Consulta do Preparo:** coluna Mês, filtro de mês e texto copiado. Vem de `mesFaz`, que é o mês do Plantio da fazenda (`app/index.html` ~2625, `montarPreparo` em `app/dados.js`).
- **Apresentação semanal** (`Documents/GitHub/src/scripts/gerar.py`, slide "Projetos de Sistematização"): gráfico "Ha programado por mês de plantio".

Além disso, cerca de 428 ha já foram preparados no ciclo 25-26, antes do Hub existir. Eles aparecem como "a fazer".

Números de 27/10: dos 906 ha a fazer, 428 ha têm conservação entre mai e dez/2025, 90 ha em set/2026 (usados em campo, sem lançamento no Hub) e 388 ha não têm data.

## Decisões

### D1. Duas datas de campo novas, importadas do PLANAGRI
A importação diária (`ingestao/planagri.py`) passa a ler:
- **CONSERVAÇÃO (DATA)** (coluna 32 da aba Planagri) → `hub.talhao_preparo.conservacao_em date`;
- **REALIZADO PLANTIO (DATA)** (coluna 65) → `hub.talhao_plantio.plantio_realizado_em date`.

O dono das duas é o PLANAGRI. Elas são só informação de campo e **não avançam etapa sozinhas** (ver D4).

### D2. Data de entrega do talhão no Preparo
Entregue = talhão com `talhao_preparo.etapa = 'Ok'`. A data de entrega vem do Hub, não da conservação:
1. a última passagem do talhão para `Ok` no `log_auditoria` (o fluxo por talhão grava isso desde 23/10);
2. sem essa passagem, o `concluido_em` da etapa **Preparo** da fazenda em `etapa_status` (o histórico de antes de 23/10).

Classificação de cada talhão entregue (coluna `origem` da view):
- `ciclo_25_26`: veio do lançamento único (D3). A data é a de conservação.
- `lancamento_inicial`: a data de entrega cai entre 17 e 19/06/2026, que é o lote copiado do sistema antigo pela migração (`migrar_plantio_preparo.py:268`).
- `hub`: todo o resto.

Tudo isso fica numa view `hub.preparo_entregas (layer, cod_faz, entregue_em, origem)`. O Hub e a apresentação leem a mesma view.

### D3. Lançamento único do ciclo 25-26 (feito uma vez, com dado real)
Vale **por talhão** (decidido em 28/10, depois da spec): todo talhão do Preparo que ainda não está Ok e tem conservação antes de 01/04/2026 entra, mesmo que outros talhões da fazenda não tenham.
- esses talhões passam para `Ok` por `projeto_mudar_etapa` (fica registrado no `log_auditoria` com `origem = 'planagri_ciclo_25_26'` e a justificativa "ciclo 25-26 · pelo PLANAGRI");
- `etapa_status` (escopo fazenda) só é preenchido quando a fazenda inteira fica Ok com o lançamento: as 4 etapas ficam `ok = true`, com `concluido_em` = a maior data de conservação da fazenda, `usuario_id` vazio e a observação igual ao selo. **A observação que já existir não é sobrescrita.**

Regras de segurança (memória `feedback_testes_dados_reais`):
- o script começa em modo simulação e gera a **lista** (fazenda, talhões, ha, datas de conservação). O usuário confere a lista antes de qualquer gravação;
- antes de gravar, ele salva um backup das linhas que vai tocar (`talhao_preparo`, `etapa_status`);
- tem um modo de volta, que restaura o backup e apaga as linhas de log do lote.

### D4. Daqui para frente: aviso, não avanço
A cada importação, `hub.avisos_campo_planagri()` abre, atualiza ou resolve um aviso por fazenda. Segue o mesmo padrão de `colheita_aviso_desatualizado`: um aviso aberto por tipo e fazenda, e volta a ficar não lido quando muda.
- **Preparo** (`preparo_campo_sem_lancamento`): há talhão com `conservacao_em` no ciclo atual e `etapa <> 'Ok'`. Texto: "N talhão(ões) usados em campo (conservação no PLANAGRI), falta lançar no Hub."
- **Plantio** (`plantio_campo_sem_lancamento`): há talhão com `plantio_realizado_em` no ciclo atual e `projeto <> 'Ok'`. Mesmo texto, com "plantio realizado".
- O aviso se resolve sozinho quando não sobra talhão nessa condição.

Ciclo atual = parâmetro `colheita_safra` (hoje 26-27), de 1º/abr a 31/mar.

### D5. Hub — Consulta do Preparo
- A coluna **Mês** vira **Entregue em**, com o mês/ano da entrega da fazenda (a maior `entregue_em` dos talhões dela, quando todos estão Ok). Fazenda não entregue mostra "—".
- Fazenda do lançamento único mostra o selo "ciclo 25-26 · PLANAGRI" e, na coluna Ciclo, "25-26".
- O filtro e o texto copiado usam o novo valor. O Preparo deixa de usar `mesFaz`.
- Na tabela de talhões da fazenda, a data de conservação aparece como informação.
- O Plantio continua por mês de plantio, sem mudança.

### D6. Apresentação semanal — slide de Sistematização
- O gráfico vira **"Projetos entregues pela Geotecnologia por mês"**, com ha entregues por mês de `entregue_em` dentro do ciclo atual. A barra **"Lançamento inicial (jun/26)"** fica separada no começo.
- O ciclo 25-26 **não aparece no slide** ("estamos no ciclo 26-27"). Os talhões com `origem = 'ciclo_25_26'` ficam fora do gráfico, dos KPIs (total, concluído, a fazer) e do painel por etapa. A nota de fonte diz quantos ha ficaram de fora por isso.
- A nota de fonte muda: sai "Mês = primeiro mês de plantio da fazenda" e entra a regra da data de entrega.
- O `extrair.py` passa a exportar `preparo_entregas`.
- A pasta `GitHub/src` **não é um repositório git**. Copiar `gerar.py` e `extrair.py` antes de editar.

## Fora do escopo
- Avançar etapa automaticamente pela data de campo.
- Mudar o Plantio, além de importar a data e gerar o aviso.
- Os 388 ha sem data de conservação continuam como estão.

## Pontos confirmados com o usuário (28/10)
1. Os avisos olham só datas do ciclo atual.
2. "Entregue em" mostra o mês do último talhão entregue da fazenda.
3. O lançamento único inclui todo talhão com conservação antes de 01/04/2026, talhão a talhão.
4. O ciclo 25-26 não aparece na apresentação.
