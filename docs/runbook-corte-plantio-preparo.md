# Runbook: corte do Plantio e do Preparo para o Hub

Roteiro do dia em que a equipe para de usar os sistemas antigos de Plantio e de Preparo e passa a trabalhar só no Hub Geotech (https://lmalerbo.github.io/hub-geotech/).

- **Quem executa:** Leo, no PC dele, com a equipe na mesma sala.
- **Duração da janela:** cerca de 1 hora. A migração em si leva menos de 1 minuto.
- **Colheita (Expo_safra) fica de fora:** continua no sistema antigo até o corte dela.

## Portal de download do campo

- **Portal novo:** https://lmalerbo.github.io/hub-geotech/portal.html. É público, sem login, igual aos antigos. Tem as abas Plantio e Preparo e o link direto `?m=plantio` ou `?m=preparo`.
- **Por que o portal troca no corte:** os portais antigos (`portal.html` de `project-plantio` e `project-preparo`) só leem as releases antigas. Os arquivos enviados pelo Hub vão para `hub-geotech-arquivos`, que eles não enxergam.
- **O que o portal novo mostra:** só a revisão vigente de cada documento, incluindo os arquivos antigos migrados, que continuam nas releases onde sempre estiveram.
- **No corte, os portais antigos passam a redirecionar para o novo** (passo H+30). Os links que o campo tem salvos continuam funcionando, e ninguém precisa receber link novo.
- **Antes do corte, o portal novo fica vazio:** ele só enxerga o que está no Hub, e os dados entram na migração.

## Antes de marcar a data

| Item | Como conferir |
|---|---|
| Rodada diária funcionando no servidor Geo | Card "Dados atualizados" verde no Dashboard do Hub |
| Todos da equipe conseguem entrar no Hub | Cada pessoa entra uma vez com a senha do GeoMap. Quem tem senha provisória no GeoMap precisa trocá-la lá antes. |
| Ensaio da migração passa | `python migracao/migrar_plantio_preparo.py --ensaio` termina com "✓ Tudo confere" |
| Envio de arquivo funciona pelo site publicado | Um envio de teste (depois apague a release de teste) |

## Na véspera (D-1)

1. Rodar o ensaio de novo, com os dados do dia:
   ```powershell
   cd C:\Users\lmalerbo\Documents\hub-geotech
   python migracao/migrar_plantio_preparo.py --ensaio
   ```
   Tem que terminar com **"✓ Tudo confere. ENSAIO: nada ficou gravado."**
2. Combinar com a equipe o horário. Até lá, todo mundo trabalha normalmente no sistema antigo.
3. Se a opção for o Portal Mobile, deixar pronto o aviso com o link novo para gestores e operadores.

## No dia (D)

**H−10 min: congelar o sistema antigo**
- Avisar a sala: ninguém mais mexe nos sistemas antigos de Plantio e Preparo, nem em status, nem em arquivos.
- Esperar quem estiver no meio de um envio terminar.
- Anotar a hora.

**H+0: ensaio final**
```powershell
python migracao/migrar_plantio_preparo.py --ensaio
```
Se **não** terminar com "✓ Tudo confere": pare, descongele o sistema antigo e remarque. Nada foi gravado.

**H+5: migração de verdade**
```powershell
python migracao/migrar_plantio_preparo.py
```
Digitar `MIGRAR` quando pedir. O resultado precisa ter **"✓ Tudo confere. Migração GRAVADA."** e `plantio_divergentes: 0`.

Se der erro, nada foi gravado, porque a migração roda numa transação só. Leia a mensagem, corrija e rode de novo. Ela pode ser repetida sem duplicar nada.

**H+10: conferir no Hub (Leo)**
- **Dashboard:** as contagens do Plantio batem com o resultado da migração.
- **Plantio:** abra 2 ou 3 fazendas conhecidas. Status, arquivos e revisões iguais ao sistema antigo, e o mapa baixa pelo link.
- **Preparo:** abra 2 ou 3 fazendas. As etapas estão concluídas com quem fez e quando.
- **Preparo, fazendas do BLOCO POMPEI** (10080, 10352, 10515 e 10516): o bloco aparece nas quatro.

**H+20: liberar a equipe no Hub**
- Todos entram no Hub. A partir daqui, qualquer mudança é feita só no Hub.
- Cada pessoa faz uma ação real simples e confere que funcionou.

**H+30: portal do campo**
- Abrir https://lmalerbo.github.io/hub-geotech/portal.html no celular e conferir:
  - 2 ou 3 fazendas do Plantio: o mapa abre e o projeto baixa;
  - 2 ou 3 fazendas do Preparo.
- Redirecionar os portais antigos para o novo: o Claude troca o `portal.html` de `project-plantio` para `?m=plantio` e o de `project-preparo` para `?m=preparo`, depois dá push.
- Esperar cerca de 1 minuto e abrir os links antigos no celular. Eles precisam cair no portal novo, na aba certa.

## Se alguém mexeu no sistema antigo depois do congelamento

Enquanto ninguém tiver trabalhado no Hub ainda, basta rodar a migração de novo. Ela traz o estado mais recente do sistema antigo e sobrescreve o que foi migrado.

Depois que a equipe começou a usar o Hub, não rode de novo: a mudança feita no antigo precisa ser repetida à mão no Hub.

## Plano de volta

**Se o Hub der problema sério nos primeiros dias:**
- Os sistemas antigos não foram alterados em nada: a migração só leu deles. A equipe pode voltar a usá-los na hora.
- O que foi feito no Hub nesse meio-tempo está no histórico (`hub.log_auditoria`, origem `usuario`), com quem, o quê e quando.
- Arquivos enviados pelo Hub ficam em `hub-geotech-arquivos`. Esse histórico e esses arquivos servem para repetir no sistema antigo o que foi feito no Hub.

**Para desfazer a migração no Hub** (só se for recomeçar do zero), rode no SQL Editor:
```sql
begin;
delete from hub.projetos;                                   -- apaga também revisões, origens e arquivos
delete from hub.etapa_status using hub.etapas e
 where e.id = etapa_status.etapa_id and e.modulo_id = 'preparo';
delete from hub.plantio_status_guardado where origem = 'sistema_antigo';
delete from hub.log_auditoria where origem in ('sistema_antigo', 'usuario', 'mapa_anexado');
update hub.talhao_plantio set mapeamento = 'Não', projeto = 'Aguard. Map.';
select hub.aplicar_regra_conservacao();                     -- refaz o que a regra de conservação libera
commit;
```
Isso também apaga o que a equipe fez no Hub. Use só antes de ela começar a trabalhar nele.

## Depois do corte (primeira semana)

- [ ] Conferir todo dia de manhã o card "Dados atualizados".
- [ ] Deixar os sistemas antigos só para consulta. Não apagar nada: eles são o plano de volta.
- [ ] Depois de uma semana sem problemas:
  - apagar a função da migração: `drop function hub.migrar_sistema_antigo(jsonb, boolean);`
  - apagar a conta `teste-automatizado@hub.local`.
- [ ] **Não desligar** os Workers antigos (`project-plantio-proxy` e `project-preparo-proxy`). O do Preparo também atende os relatórios `/report/*`, usados por Power BI e planilhas, e o disparo da atualização de voos. Desligar só depois de migrar esses usos.
