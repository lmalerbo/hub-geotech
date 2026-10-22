# Tela de Usuários: nível por módulo e acesso por mapa no GeoMap

**Data:** 22/10/2026 · **Decisões do Leo:** sessões de 22/10 (memória `project_passagem_2026_10_22`, item 1) · **Maquete:** https://claude.ai/artifact/LDm98phg3ttmT82hL4DJmd (particular, nomes fictícios).

## 1. Objetivo

Hoje cada pessoa tem **um papel só** (`editor`, `leitura` ou `solicitante`), que vale para todos os módulos marcados. Não dá para ser editor no Plantio e leitura na Colheita. No GeoMap, o acesso aos mapas vem apenas dos grupos. A tela é um formulário único, com papel, módulos em caixinhas e uma seção do GeoMap.

Depois desta entrega:

1. **Nível por módulo.** Plantio, Preparo e Colheita têm Sem acesso, Leitura ou Editor. O Drone tem também Solicitante. O papel único deixa de existir.
2. **Admin do Hub à parte.** Continua sendo uma chave própria, separada dos níveis.
3. **Mapas de aplicação** (módulo `corretivos`: Corretivos e Aplicação aérea) só ligam e desligam.
4. **GeoMap por mapa.** Continuam o admin e os grupos. Entra o acesso individual por mapa (Ver / Ver e editar), que **soma** ao dos grupos e **só acrescenta**: nunca rebaixa o que um grupo dá.
5. **Tela reorganizada como na maquete:**
   - lista à esquerda, com o resumo do acesso de cada pessoa, busca e filtros;
   - painel com as abas **Conta**, **Módulos do Hub** e **Ferramentas**;
   - um único Salvar para as três abas.

Fora desta entrega:
- **Kronos e Portal de downloads:** só um aviso reservado na aba Ferramentas.
- **Perfis prontos:** não haverá, por decisão do Leo.
- **Grupos do GeoMap:** criar e editar continua sendo feito no GeoMap.
- **Tela de usuários do admin do GeoMap:** continua só leitura e não passa a mostrar os mapas individuais.

## 2. Regras de acesso

- **Valores de nível:**
  - um módulo sem linha em `hub.usuario_modulos` fica **Sem acesso**;
  - com linha, o nível é `leitura`, `solicitante` (só no Drone) ou `editor`.
- **Mapas de aplicação:**
  - ligado = linha com nível `editor`;
  - `hub.pode_usar_corretivos()` não muda (admin ou ter a linha).
- **Editar:**
  - **`hub.pode_editar(modulo)`:** admin, ou nível `editor` naquele módulo.
  - **`nova_revisao`:** passa a usar a própria `hub.pode_editar`. A exceção de `service_role` continua.
- **Abrir solicitação de Drone (normal):**
  - quem pode editar o Drone;
  - ou quem tem nível `solicitante` no Drone.
  - A catação continua só para quem edita.
- **Ver um módulo:** ter qualquer nível nele. O admin vê todos, como hoje.
- **Admin:** continuam valendo as travas do login único:
  - só admin concede acessos;
  - ninguém tira o próprio admin;
  - o último admin não perde o admin.
- **Bloqueio da conta** (função `contas`): bloqueia quem fica sem nenhum módulo, sem GeoMap e sem admin, como hoje.
- **GeoMap, acesso a um mapa:**
  - **Nível final:** o maior entre o que os grupos dão e o que a pessoa tem individualmente (nada < Ver < Ver e editar).
  - **Admin do GeoMap:** vê e edita tudo, como hoje.
  - **Remover o mapa individual:** a pessoa volta a ter só o que os grupos dão.
  - **Sem "Acessa o GeoMap":** não manda grupos nem mapas, como hoje com os grupos.

## 3. Componentes

### 3.1 Banco do Hub (schema `hub`)

- **`hub.usuario_modulos.nivel`:**
  - `text not null default 'leitura'`, com check em `leitura | solicitante | editor`;
  - um segundo check impede `solicitante` fora do Drone.
- **Migração dos dados**, a partir do papel atual de cada pessoa:

  | Papel hoje | Módulo | Nível novo |
  |---|---|---|
  | qualquer | `corretivos` | `editor` |
  | `editor` | qualquer outro | `editor` |
  | `solicitante` | `drone` | `solicitante` |
  | demais casos | | `leitura` |

  Ninguém ganha nem perde nada na virada.
- **`hub.acessos`:**
  - ganha `niveis jsonb` (`{"plantio":"editor","drone":"solicitante",...}`), preenchida pela mesma regra;
  - ganha `geomap_mapas jsonb` (`[{"mapa_id":12,"pode_editar":false},...]`, padrão `[]`).
- **`hub.acesso_salvar(p_email, p_nome, p_admin, p_niveis jsonb, p_geomap_ativo, p_geomap_admin, p_geomap_grupos int[], p_geomap_mapas jsonb)`** substitui a de hoje:
  - **Valida:**
    - módulo existe;
    - nível é um dos três;
    - `solicitante` só no Drone;
    - `corretivos` só `editor`;
    - cada mapa tem `mapa_id` inteiro e `pode_editar` booleano.
  - **Grava** `hub.usuarios` e `hub.usuario_modulos(modulo_id, nivel)`.
  - **Para poder voltar atrás**, continua gravando `papel` e `modulos`, que nada mais lê:
    - `modulos` são as chaves de `niveis`;
    - `papel` vira `editor` se há algum Editor, `solicitante` se o Drone é Solicitante, senão `leitura`.
  - **Auditoria** com os níveis, os grupos e os mapas.
- **`hub.acessos_situacao()`:** devolve também `niveis` e `geomap_mapas`.
- **`hub.acesso_remover`:** não muda. Ele já apaga a linha de `hub.acessos` e as de `hub.usuario_modulos`, e com elas os níveis.
- **Funções reescritas sem `papel`:** `hub.pode_editar`, `hub.nova_revisao` (4 argumentos) e `hub.drone_solicitar`.
- **`hub.usuarios.papel` e `hub.acessos.papel`/`modulos`:** ficam congelados, servem só para voltar atrás. Saem numa limpeza depois de algumas semanas.

### 3.2 Função `contas`

- **`salvar`** recebe `niveis` e `geomap_mapas`, em vez de `papel` e `modulos`, e os repassa para `acesso_salvar`.
  - Ao GeoMap, envia `mapas: [{mapaId, podeEditar}]` junto com os grupos.
- **`temAcesso`** (`regras.js`) passa a olhar `niveis`: tem acesso quem tem alguma chave, ou GeoMap, ou admin.
- **Ação nova `mapas_geomap`:** devolve os mapas do GeoMap e o que cada grupo dá em cada um, para a coluna "Pelos grupos".
- **`remover`:** envia `mapas: []` ao GeoMap.

### 3.3 GeoMap (backend)

- **Migração `020_permissoes_usuario.sql`** (idempotente, porque `migrate.js` roda tudo sempre):
  - **Tabela `permissoes_usuario`:**
    - colunas `usuario_id` e `mapa_id`, ambas `ON DELETE CASCADE`, mais `pode_editar boolean`;
    - chave primária `(usuario_id, mapa_id)`.
  - **View `permissoes_efetivas(usuario_id, mapa_id, pode_editar)`:**
    - junta a permissão de grupo (`permissoes` × `usuarios_grupos`) e a individual;
    - quem consulta faz `bool_or(pode_editar)`, então o individual só acrescenta.
- **Todo lugar que hoje junta `permissoes` com `usuarios_grupos` passa a usar a view:**
  - `lib/permissoes.js`: `usuarioTemPermissaoMapa` e `usuarioPodeEditarMapa`;
  - `routes/mapas.js`: o catálogo `GET /mapas` e o download `/camadas/:id/download`.
  - Pins, planejamentos e voos já usam `lib/permissoes.js` e herdam a mudança.
- **Integração do Hub:**
  - `PUT /integracao/contas/usuario` aceita `mapas` (opcional):
    - se vem, substitui os mapas individuais da pessoa;
    - se não vem, não mexe, o que mantém compatível um Hub antigo durante a publicação;
    - com `ativo: false`, apaga os mapas individuais.
  - `GET /integracao/contas/usuarios` devolve também `mapas`.
  - **Rota nova `GET /integracao/contas/mapas`:** `[{id, nome, grupos: [{grupoId, podeEditar}]}]`.

### 3.4 App do Hub (`app/index.html`, `app/drone.js`)

- **Quem entrou:**
  - `EU.role` dá lugar a `EU.niveis` (`{modulo: nivel}`), lido de `usuario_modulos(modulo_id, nivel)`;
  - `podeEditar(mod)` = admin ou `EU.niveis[mod] === 'editor'`;
  - `drone.js` troca `EU.role==='solicitante'` por `EU.niveis.drone==='solicitante'`;
  - na barra lateral, o rótulo do papel vira "Admin" para admin; para os demais, fica vazio.
  - Em Configurações → Geral, o selo do papel vira a lista dos módulos com o nível de cada um.
- **Tela Usuários**, conforme a maquete:
  - **Lista:**
    - busca por nome ou e-mail;
    - filtros: Todos, Plantio, Preparo, Colheita, Drone, GeoMap e Senha provisória.
    - **Cada pessoa:** iniciais, nome, ponto de situação e uma linha de resumo, por exemplo `Plantio (editor) · Preparo · Drone (solicitante) · GeoMap: 2 grupos + 1 mapa · Mapas de aplicação`.
      - Leitura aparece sem o sufixo.
      - Quem está bloqueado mostra "Sem acesso — bloqueado".
  - **Cabeçalho do painel:** iniciais, nome, e-mail, último acesso e situação (Acesso ativo, Senha provisória, Ainda não entrou, Sem conta, Bloqueado). "Acesso ativo" substitui o "Ativa"/"Ativo" da maquete, que suporia o gênero.
  - **Aba Conta:**
    - Nome e E-mail (só leitura depois de criado);
    - Senha, com "Redefinir senha";
    - Remover acesso, que some para a própria pessoa.
  - **Aba Módulos do Hub:**
    - uma linha por módulo (Plantio, Preparo, Colheita, Drone), com um seletor segmentado de nível;
    - abaixo, a chave Administrador do Hub ("Gerencia usuários e configurações. Só um admin concede admin.").
    - O módulo `voo` continua fora da tela.
  - **Aba Ferramentas:**
    - **Cartão GeoMap:**
      - liga/desliga, admin do GeoMap e grupos em chips;
      - tabela **Mapa · Pelos grupos · Individual · Resultado**;
      - a maquete diz "Só para ela", mas a tela usa "Individual" para não supor o gênero da pessoa;
      - a coluna "Individual" alterna — → Ver → Ver e editar → —;
      - o Resultado é o maior dos dois e atualiza na hora, já com os grupos marcados na tela.
    - **Cartão Mapas de aplicação:** liga/desliga.
    - **Aviso:** "Kronos e Portal de downloads entram aqui quando passarem a usar o login do Hub."
  - **Rodapé fixo:** "Vale na hora, para o Hub e as ferramentas." e **Salvar**, que grava as três abas de uma vez.
  - **Novo acesso:** o painel abre na aba Conta, e o botão vira "Adicionar".
- **Lógica sem DOM em `app/usuarios.js`**, testada com `node --test`:
  - resumo da linha;
  - filtro;
  - nível final por mapa.

## 4. Ordem de publicação

1. **GeoMap:** migração, view, rotas novas e `mapas` opcional. Não muda nada para quem não tem mapa individual.
2. **Hub:** migração, função `contas` e app, em sequência no mesmo dia.
   - Entre a migração e o push do app, o app antigo continua funcionando, porque `papel` segue preenchido.
   - Nesse intervalo, só o Salvar da tela Usuários falha, porque a assinatura mudou. São minutos.

## 5. Como voltar atrás

- **Hub:**
  - reverter o commit do app e a função `contas`;
  - um script de volta recria as versões antigas de `pode_editar`, `nova_revisao`, `drone_solicitar`, `acesso_salvar` e `acessos_situacao`;
  - `papel` e `modulos` continuam corretos, porque `acesso_salvar` os manteve;
  - as colunas novas não atrapalham.
- **GeoMap:**
  - reverter o commit volta a ler só os grupos;
  - a tabela `permissoes_usuario` fica sem uso.
