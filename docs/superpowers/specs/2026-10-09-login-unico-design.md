# Login único: o Hub como dono das contas (Hub + GeoMap)

**Data:** 09/10/2026 · **Decisões do Leo:** conversa de 09/10 (memória `project_hub_acesso_central`).

## 1. Objetivo

Hoje o GeoMap é o dono das senhas e o Hub copia o hash uma vez por hora (`ingestao/sincronizar_usuarios.py`). Cada sistema tem um cadastro próprio, e a tela Usuários do Hub só controla os módulos do Hub.

Depois desta entrega:

1. **O Hub é o dono das contas e das senhas.** Criar acesso, redefinir senha e bloquear são feitos na tela Usuários do Hub, com efeito imediato, sem esperar sincronização.
2. **O GeoMap usa o login do Hub.** A pessoa entra no GeoMap com o mesmo e-mail e senha do Hub, e o GeoMap não guarda mais senha.
3. **A tela Usuários controla o acesso a tudo.** Ela cobre os módulos do Hub e as ferramentas. Nesta entrega entra o GeoMap: se a pessoa tem acesso, em quais **grupos** está e se é admin. A definição de quais mapas cada grupo vê continua no GeoMap.
4. **Senha provisória** gerada pelo Hub, aleatória, mostrada uma vez ao admin, com troca obrigatória no primeiro login. É o mesmo fluxo para pessoa nova e para "esqueci a senha". O link por e-mail fica para depois.
5. **Virada num dia só, Hub e GeoMap juntos.** Ninguém troca de senha: o hash atual de cada pessoa vem do GeoMap uma última vez.

Fora desta entrega:
- portal com login;
- Kronos no login do Hub;
- recuperação de senha por e-mail;
- edição dos grupos e mapas do GeoMap pelo Hub.

## 2. Regras de acesso

- Só admin do Hub concede acessos, inclusive admin e acesso ao GeoMap.
- Ninguém tira o próprio admin nem remove o próprio acesso.
- O último admin do Hub não pode perder o admin.
- No GeoMap continua valendo que não se tira o admin do último admin ativo. O GeoMap recusa a mudança e o Hub mostra o erro.
- **Uma pessoa pode ter só o GeoMap,** sem nenhum módulo do Hub. Ela entra no Hub e vê só Ferramentas e a própria conta.
- **Remover acesso:**
  - a conta do Hub é bloqueada, sem ser apagada, para o histórico continuar com o nome;
  - a pessoa fica inativa no GeoMap.
- **Bloqueio tem efeito imediato:**
  - no Hub, porque a conta é bloqueada;
  - no GeoMap, porque o backend confere a cada pedido se a pessoa ainda está ativa, com cache de 60 s.

## 3. Componentes

### 3.1 Banco do Hub (schema `hub`)
- `hub.usuarios.precisa_trocar_senha boolean`: liga quando a senha é provisória.
- `hub.acessos` ganha `geomap_ativo`, `geomap_admin` e `geomap_grupos int[]`. Continua sendo a lista de quem acessa o quê.
- `hub.acesso_salvar(...)` passa a receber também os campos do GeoMap.
  - Grava o acesso e, se a conta já existe, aplica na hora: nome, papel, admin e módulos em `hub.usuarios` e `hub.usuario_modulos`, criando a linha de `hub.usuarios` se faltar.
  - Faz as checagens de admin da seção 2.
- `hub.acessos_situacao()` devolve também os campos do GeoMap e `precisa_trocar_senha`.
- `hub.senha_definida()`: a própria pessoa desliga o próprio `precisa_trocar_senha` depois de trocar a senha.

### 3.2 Função `contas` (Supabase Edge Function)
- Única peça com a chave de serviço, que o Supabase injeta sozinho; nada fica no navegador nem no Worker de arquivos.
- O chamador manda o próprio login, e a função confere `hub.eh_admin()` com esse login.
- **Ações:**
  - `salvar`: grava o acesso e, se a conta não existe, cria com senha provisória. Ajusta o bloqueio (bloqueia se não tem Hub nem GeoMap, desbloqueia se tem) e envia ao GeoMap nome, ativo, admin e grupos. Devolve a senha provisória quando criou.
  - `redefinir_senha`: gera uma senha provisória nova e liga `precisa_trocar_senha`.
  - `remover`: remove o acesso, bloqueia a conta e deixa a pessoa inativa no GeoMap.
  - `grupos_geomap`: lista os grupos do GeoMap para a tela.
- **Segredos da função:** `HUB_INTEGRACAO_TOKEN`, o mesmo que o GeoMap já aceita, e `GEOMAP_URL`.

### 3.3 GeoMap (backend)
- `POST /auth/hub {accessToken}`:
  - valida o login no Supabase do Hub (`GET /auth/v1/user`);
  - recusa se `precisa_trocar_senha`;
  - acha a pessoa pelo e-mail com status ativo;
  - emite o JWT do GeoMap como hoje (30 dias). O resto do GeoMap não muda.
- `exigirAutenticacao` confere a cada pedido se a pessoa está ativa, com cache de 60 s.
- Rotas novas para o Hub (chave `x-hub-token`):
  - `GET /integracao/contas/grupos`;
  - `GET /integracao/contas/usuarios`;
  - `PUT /integracao/contas/usuario`: cria ou atualiza pelo e-mail.
- Desligados enquanto `LOGIN_LOCAL` estiver vazio (é o caminho de volta se algo der errado):
  - `POST /login` e `PUT /senha`;
  - criar, editar, redefinir senha e apagar usuário no admin do GeoMap.
- O vínculo de piloto do Drone MGMT continua no GeoMap.

### 3.4 GeoMap (frontend)
- A tela de login entra com `supabase-js` no projeto do Hub e troca o token por `POST /auth/hub`.
- **Login compartilhado:** o Hub e o GeoMap estão no mesmo endereço (`lmalerbo.github.io`), então quem já está logado no Hub entra direto no GeoMap.
- "Definir senha" usa `supabase.auth.updateUser` + `hub.senha_definida()`.
- Sair do GeoMap também sai da sessão do Hub, porque o login é um só.
- A tela de usuários do admin do GeoMap fica só de leitura, com o aviso "Contas e grupos são gerenciados no Hub". O vínculo de piloto continua editável.

### 3.5 App do Hub
- **Senha provisória:** depois do login, se `precisa_trocar_senha`, aparece a tela "Defina sua senha" antes de abrir o Hub.
- **Configurações → Geral:** ganha "Trocar minha senha".
- **Usuários:**
  - seção GeoMap no cadastro (acesso, admin e grupos);
  - botão "Redefinir senha";
  - janela que mostra a senha provisória uma única vez, com botão de copiar.
  - O aviso "A senha é a do GeoMap..." é trocado por "Acesso e senha valem para o Hub e o GeoMap".
- **Quem não tem módulo do Hub** abre direto em Ferramentas.
- **Ferramentas:** o card do GeoMap só aparece para quem tem acesso a ele.

### 3.6 Migração e virada
- `migracao/trazer_usuarios_geomap.py` roda uma vez, com `--simular` antes. Para cada pessoa do GeoMap:
  - cria ou atualiza a conta do Hub com o hash atual;
  - grava `hub.usuarios`;
  - grava em `hub.acessos` os campos do GeoMap (ativo, admin e grupos), mantendo os campos do Hub.
- Quem ainda está com a senha provisória do GeoMap (a fixa, conhecida) **não** recebe esse hash. A conta fica com `precisa_trocar_senha`, e o admin usa "Redefinir senha" para entregar uma provisória do Hub. O script lista essas pessoas.
- Sai `ingestao/sincronizar_usuarios.py`, junto com a tarefa de hora em hora do servidor.
- Runbook: `docs/runbook-login-unico.md`, com ordem, conferência e como voltar atrás.

## 4. Como voltar atrás
- **GeoMap:**
  - `LOGIN_LOCAL=1` no Render religa o login próprio e as telas de usuário;
  - reverter o commit do frontend volta a tela antiga;
  - os hashes antigos continuam no banco do GeoMap.
- **Hub:**
  - reinstalar a tarefa de sincronização volta ao modelo de hoje;
  - as colunas novas não atrapalham.
