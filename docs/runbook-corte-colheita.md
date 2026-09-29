# Runbook: corte da Colheita (Expo_safra) para o Hub

Roteiro do dia em que a equipe para de usar o Expo_safra e passa a fazer a Colheita só no Hub Geotech (https://lmalerbo.github.io/hub-geotech/). Mesmo formato do corte do Plantio e do Preparo (`runbook-corte-plantio-preparo.md`).

- **Quem executa:** Leo, no PC dele, com a equipe na sala.
- **Duração:** cerca de 40 minutos. A migração em si leva menos de 1 minuto.

## O que muda para a equipe

- **Um campo só por talhão:** o Tipo de Linha (Linha de Vant, Desdobra de Plantio ou Sem Linhas), marcado em lote.
- **O ciclo é automático:** é sempre a safra atual (26-27).
- **O status é calculado:**
  - tipo marcado na safra atual = Concluído;
  - Sem Linhas = Sem Linhas;
  - tipo de uma safra anterior = **Reavaliar**;
  - sem tipo = A Fazer.
- **Não existe mais registrar e depois consolidar:** grava na hora, com histórico.
- **Arquivos:** Exp1L e Exp2L (`.dwg` + `.zip`) e o Mapa de partes (`.pdf`), com revisões.
  - O nome passa a ser, por exemplo, `10503_SANTA.LUZIA.5_Rev0-Exp1L.dwg`.
  - A partir da Rev1, o motivo da revisão é obrigatório.
- **Saem do sistema:** o Plano da Semana e o ranking de hectares.
- **Novo, a Regra A:** quando o Plantio fecha um talhão como Ok, a Colheita marca o projeto como "desatualizado · replantado" e avisa no sininho.
- **A demanda vem do ICOL todo dia, sozinha.** Entram todos os talhões de cada fazenda do ICOL, e a frente é texto, então `BIS - 3` e `FOCA - 22` não se perdem mais.
- **Sai a tag de voo da Falha Soca** (a "tag de porte"). Sem Linhas é avaliação do analista, e os talhões até o 3º corte já têm voo automático do setor. O acompanhamento de voo volta com a Regra B, só para talhões Sem Linhas e para os apontados com problema, no projeto **Linhas de Colheita**.

## Antes de marcar a data

| Item | Como conferir |
|---|---|
| Branch `colheita` juntado na `main` e publicado | O menu do Hub mostra "Colheita" sem "em breve" |
| Migrations da Colheita aplicadas | `20261003090000`, `20261003100000` e `20261003110000`, já aplicadas em 29/09 |
| Servidor Geo atualizado | `git pull` (a rodada diária passa a importar o ICOL) |
| ICOL na rodada diária | O card "Dados atualizados" inclui o ICOL. `agendamento\logs\diario.log` mostra `=== icol.py ===` |
| **Acesso à Colheita** | O `usuario_antigo` e o módulo `colheita` estão no `usuarios_hub.json`, no PC e no servidor, para quem trabalha na Colheita. Depois, rodar `sincronizar_usuarios.py`. |
| Ensaio passa | `python migracao/migrar_colheita.py --ensaio` termina com "✓ Tudo confere" |

## No dia (D)

**H−10: congelar o Expo_safra**
- Avisar a sala: ninguém mais registra, consolida nem envia arquivo no Expo_safra.
- Quem tiver registros do dia sem consolidar consolida antes. O que não foi consolidado **não é migrado**.

**H+0: ensaio final**
```powershell
cd C:\Users\lmalerbo\Documents\hub-geotech
python migracao/migrar_colheita.py --ensaio
```

**H+5: migração**
```powershell
python migracao/migrar_colheita.py
```
Digitar `MIGRAR` quando pedir. Tem que terminar com **"✓ Tudo confere. Migração GRAVADA."** e `talhoes_divergentes: 0`.

**H+10: conferir no Hub (Leo + Claude)**
- **Dashboard:** o card da Colheita, com Concluído, Reavaliar, Sem Linhas e A Fazer.
- **Fazendas:** abrir 3 ou 4 e comparar com o Expo_safra, que continua aberto só para consulta:
  - uma 100% concluída;
  - uma com talhões de 25-26 (devem aparecer como **Reavaliar**);
  - uma de bloco (`10531` e `10627`);
  - uma com mapa de partes.
- **Tag de voo:** aparece nos talhões Sem Linhas.

**H+20: liberar a equipe**
- Todos entram no Hub. A partir daqui, a Colheita é feita só no Hub.

**H+30: portal do campo**
- Conferir https://lmalerbo.github.io/hub-geotech/portal.html?m=colheita no celular: 2 ou 3 fazendas, com download e mapa.
- **Redirecionar o `portal-safra`:** o Claude troca o que a Action do `portal-safra` publica por uma página que redireciona para `portal.html?m=colheita`. Não mexe no código do Next.js, e voltar é reverter um commit.
- Abrir o link antigo do `portal-safra` no celular. Ele tem que cair na aba Colheita.

## Se alguém mexeu no Expo_safra depois do congelamento

Enquanto ninguém tiver trabalhado na Colheita do Hub, rode a migração de novo. Ela sobrescreve com o estado mais recente.

## Plano de volta

- **O Expo_safra não é alterado pela migração, que só lê dele.** A equipe pode voltar a usá-lo na hora.
- **O que foi feito no Hub nesse meio-tempo** está no histórico (`hub.log_auditoria`, módulo `colheita`, origem `usuario`).
- **Portal:** reverter o commit do redirecionamento no `portal-safra`.

## Expo_safra depois do corte

- O Hub não depende de nada do Expo_safra. A GitHub Action "Atualizar status de voo" de lá pode ser desligada quando ninguém mais consultar o sistema antigo.
- O Expo_safra fica aberto só para consulta durante a primeira semana, como plano de volta.

## Depois do corte (primeira semana)

- [ ] Conferir todo dia o card "Dados atualizados", que agora inclui o ICOL.
- [ ] Depois de uma semana sem problemas, apagar a função da migração: `drop function hub.migrar_colheita_antiga(jsonb, boolean);`
- [ ] Próximo: Regra B (voo e revoo com agendamento no Drone MGMT).
