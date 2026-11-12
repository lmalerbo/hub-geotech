# Contexto do Projeto — Automação de Linhas de Guia via API (JD + outros fabricantes)

## Objetivo
Automatizar o fluxo completo de geração e distribuição de linhas de guia (sulco/plantio) do dado bruto (restituição de drone) até o monitor do trator, substituindo o processo manual via AgroCAD, usando APIs dos fabricantes (John Deere confirmado, outros a mapear).

## Situação atual (ponto de partida)
- Hoje o fluxo depende do AgroCAD (plugin Tecgraf, dentro do AutoCAD Civil 3D) pra gerar e exportar as linhas no formato proprietário de cada monitor.
- Já existe experiência prévia com engenharia reversa de formatos de exportação no projeto **AGROEXPORT** (formatos John Deere Gen4, GS3-2630, PTx Trimble AgGPS, AgData/.agf com AES-128-CBC).
- Padrão de arquitetura já estabelecido pra esse tipo de projeto: **EXPCOLHEITA** (HTML sem build + Python watcher + fila JSON em pasta compartilhada) — avaliar se esse padrão se aplica aqui ou se o projeto pede outra estrutura (mais orientado a API/cloud do que a arquivo compartilhado).
- 10 frentes de trabalho, 3–5 máquinas cada. Aproximadamente metade das frentes tem conectividade (JDLink/WDT), a outra metade não.

## Acesso à API John Deere — já aprovado
**Ticket 4363488** — resolvido em 23/jul, acesso liberado gratuitamente (sem custo, diferente da API de Setup Builder que parece ser paga/restrita).

Rotas já liberadas (lista completa do ticket):
```
GET    /platform/organizations/*/boundaries
GET    /platform/fieldOperations/*/boundary
GET    /platform/organizations/*/fields/*/boundaries/*
POST   /platform/organizations/*/fields/*/boundaries
POST   /platform/organizations/*/clients
GET    /platform/organizations/*/clients
PUT    /platform/organizations/*/clients/*
POST   /platform/organizations/*/fields
GET    /platform/organizations/*/fields/*/farms
GET    /platform/organizations/*/farms/*/fields
GET    /platform/organizations/*/fields/*
DELETE /platform/organizations/*/connections
GET    /platform/connections
DELETE /platform/connections/*
PUT    /platform/organizations/*/fields/*/guidanceLines/*
PUT    /platform/organizations/*/workPlans/*
GET    /platform/organizations/*/clients/*
GET    /platform/organizations/*/fields/*/guidanceLines/*
GET    /platform/organizations/*
GET    /platform/partnerships/*
GET    /platform/partnerships
DELETE /platform/organizations/*/workPlans/*
DELETE /platform/organizations/*/fields/*
PUT    /platform/organizations/*/fields/*
GET    /platform/organizations/*/clients/*/fields
GET    /platform/organizations/*/clients/*/farms
GET    /platform/organizations/*/fields/*/boundaries
POST   /platform/organizations/*/workPlans
GET    /platform/organizations/*/farms
GET    /platform/organizations/*/fields/*/clients
POST   /platform/organizations/*/fields/*/guidanceLines
GET    /platform/organizations/*/fields/*/guidanceLines
DELETE /platform/organizations/*/workPlans/*
PATCH  /platform/organizations/*/workPlans/*
GET    /platform/organizations/*/farms/*
PUT    /platform/organizations/*/farms/*
DELETE /platform/organizations/*/fields/*/boundaries/*
PUT    /platform/organizations/*/fields/*/boundaries/*
POST   /platform/organizations/*/farms
GET    /platform/organizations/*/farms/*/clients
GET    /platform/organizations
GET    /platform/organizations/*/workPlans
DELETE /platform/organizations/*/fields
PUT    /platform/organizations/*/farms/*
GET    /platform/organizations/*/workPlans/*/workPlanSequence
POST   /platform/partnerships
GET    /platform/partnerships/*/permissions
PUT    /isg/partnerships/*
PUT    /isg/organizations/*/partnerPermissions
GET    /platform/organizations/*/settings
```

**Rotas-chave pro objetivo do projeto:**
- `guidanceLines` (GET/POST/PUT) — objeto de linha de trajetória/AB line que o piloto automático segue. Substitui o export manual do AgroCAD.
- `workPlans` + `workPlanSequence` — estruturação da operação (o quê, em que ordem).
- `fields`, `boundaries`, `farms`, `clients` — estrutura de dados de suporte (talhão, organização).

**Rotas que faltam (a pedir se necessário):**
- `Files` / `File Transfer` — envio de arquivo binário direto pra máquina.
- `Prescriptions` (ALPHA) — aplicação a taxa variável (não é o foco atual, mas pode ser útil no futuro).
- **Setup File Builder API** — gera automaticamente o ZIP no formato GS3_2630 a partir dos objetos já criados (fields/guidanceLines). Aparenta ser paga/só sob aprovação especial — usina provavelmente não vai investir nisso agora.

## Divisão do fluxo por conectividade

### Frentes conectadas (JDLink + WDT ativo)
Fluxo 100% via API:
1. Pipeline cria/atualiza `fields` e `guidanceLines` via API (dado vindo do Civil 3D, já classificado e padronizado).
2. Se WDT estiver habilitado no trator, o Operations Center sincroniza automaticamente pro display — sem intervenção manual.

### Frentes sem conectividade (~metade)
Ainda dependem do arquivo físico (USB) no formato GS3_2630. Como não vamos pagar pela API de Setup Builder, o caminho gratuito é:
1. Mesma criação de dados via API (fields/guidanceLines) — pipeline único, sem duplicar trabalho de classificação.
2. Geração do ZIP GS3_2630: via automação da própria interface web do Operations Center (Files Manager → filtro "Setup" → download), usando um script de navegador (Playwright/Selenium) autenticado com a conta da usina. **Isso não é engenharia reversa nem quebra EULA** — é automatizar o mesmo clique que um humano faria.
3. ZIP resultante sobe automaticamente no portal próprio (já existente) pra o operador baixar onde estiver.

## Limite de processamento por monitor (conhecimento tácito do projetista — formalizar!)

O limite **não é do formato de arquivo**, é do **processamento do firmware do display**. Cada fabricante mede diferente:

| Monitor | Critério de limite | Valor validado empiricamente |
|---|---|---|
| John Deere GS3 2630 | Tamanho de arquivo (processamento) | ~2 MB por bloco |
| Trimble FM1000 / PTx | Quantidade de linhas | Até 1000 linhas |
| *(outros a mapear)* | — | — |

Esse valor de 2MB/1000 linhas foi validado ao longo de 11 projetos reais, sem falha de carregamento — não está documentado oficialmente em specs públicas da JD/Trimble, é conhecimento de campo do projetista.

**Estrutura de referência sugerida pro pipeline novo:**
```python
MONITOR_LIMITS = {
    "GS3_2630": {"tipo": "tamanho_arquivo", "limite": 2 * 1024 * 1024},  # 2MB
    "FM1000_PTX": {"tipo": "quantidade_linhas", "limite": 1000},
    # adicionar outros monitores conforme mapeamento
}
```
A função de chunking deve decidir a estratégia de corte (tamanho estimado do payload vs. contagem de linhas) conforme o tipo de monitor de destino.

**Equivalente ao comando "classificador" do AgroCAD** (nome exato ainda não identificado — só lembrete "KLA" ou similar): dividir as linhas do canavial em blocos/glebas que respeitem o limite de cada monitor. Repor essa lógica no pipeline próprio usando técnica de simplificação de geometria (ex: Douglas-Peucker) + corte por limite (tamanho ou contagem).

## Pontos em aberto / a verificar antes ou durante o desenvolvimento
1. Confirmar quais frentes têm JDLink Connect (WDT) realmente ativo — não é só hardware, é assinatura.
2. Testar empiricamente no sandbox da API o limite de payload/vértices por objeto `guidanceLine` (enviar linhas crescentes até a API rejeitar).
3. Confirmar com a Tecgraf se eles têm a referência oficial de onde tiraram o valor de 2MB pro comando de classificação do AgroCAD (documentação interna deles via parceria JD).
4. Mapear limites de outros monitores usados nas frentes (Trimble/PTx confirmado em 1000 linhas — outros a validar).
5. Verificar se vale abrir novo ticket pedindo acesso à Setup Builder API (perguntar custo antes de decidir).
6. Definir schema exato do payload `guidanceLines` (tipo de linha: AB reta, curva, pivô; sistema de coordenadas — provavelmente WGS84).

## Próximos passos técnicos (arquitetura sugerida)
1. Pipeline Python lendo saída do Civil 3D/restituição de drone.
2. Etapa de classificação/padronização das linhas (portada da lógica do AgroCAD pro código próprio).
3. Etapa de chunking por limite de monitor (tabela `MONITOR_LIMITS`).
4. Roteamento por conectividade: API direta (guidanceLines/workPlans) para frentes conectadas; geração de ZIP GS3_2630 via automação de navegador para frentes offline.
5. Publicação automática no portal já existente pra download do operador.
