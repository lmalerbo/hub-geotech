# Virada do login único (Hub + GeoMap)

Duração: ~1 h, fora do horário de pico. Ninguém troca de senha (o hash atual de cada pessoa vem do GeoMap).
O Leo acompanha todos os passos. Spec: `docs/superpowers/specs/2026-10-09-login-unico-design.md`.

Branches: Hub `login-unico` (hub-geotech); GeoMap `feat/login-hub` (backend + frontend já juntos).

**A ordem importa.** O merge do GeoMap em `master` publica o backend (Render) **e** o frontend (Pages) de uma vez: a partir dali o GeoMap só aceita o login do Hub. Por isso as contas precisam estar no Hub (passo 6) **antes** do merge (passo 7).

## Antes (pode ser na véspera)

1. **Servidor Geo: apagar a sincronização antiga primeiro.** Ela recria/bloqueia contas a partir do GeoMap e, durante a virada, bloquearia de novo quem recebe senha provisória do Hub:
   ```powershell
   schtasks /delete /tn "Hub Geotech - Sincronizar usuarios" /f
   ```
   Até a virada, conta nova no GeoMap não aparece sozinha no Hub (combinar com o Leo para não criar ninguém nesse intervalo).
2. Render do GeoMap (painel → Environment), **sem** publicar código:
   - `HUB_SUPABASE_URL=https://dpvsivypabmvmrrpgmhc.supabase.co`
   - `HUB_SUPABASE_ANON_KEY=<chave publicável do Hub, a mesma que está em app/index.html>`
   - `CONTAS_LOGIN_LOCAL=automacao@geoportal.local` — a automação diária continua entrando pelo login próprio do GeoMap. **Não** desativar essa conta.
3. Simulação (só leitura): `python migracao/trazer_usuarios_geomap.py --simular` e conferir a lista com o Leo. Na simulação de 16/10/2026:
   - **4 pessoas com a senha provisória do GeoMap** (arthur.lopes, bruno.soares, karen.martins, lucas.campos): não recebem o hash; o Leo entrega uma provisória do Hub no passo 11;
   - as contas `@geoportal.local` (`automacao`, `__teste_vigiar__`) ficam de fora automaticamente: continuam só no GeoMap.

## Virada (tudo no mesmo dia, em sequência)

**Atenção:** o passo 4 troca a função `acesso_salvar` usada pela tela Usuários publicada hoje. Entre o passo 4 e o passo 8 a tela Usuários do Hub fica fora (o resto do Hub funciona).

4. SQL Editor do Hub (nova query): `supabase/migrations/20261012090000_login_unico.sql`.
5. Função `contas` (no PC do Leo, pasta do hub-geotech):
   ```powershell
   supabase login        # só na primeira vez (abre o navegador)
   supabase functions deploy contas --project-ref dpvsivypabmvmrrpgmhc
   supabase secrets set --project-ref dpvsivypabmvmrrpgmhc GEOMAP_URL=https://geomap-docker.onrender.com
   supabase secrets set --project-ref dpvsivypabmvmrrpgmhc HUB_INTEGRACAO_TOKEN=<o Leo cola o valor do hub-geotech-supabase.env>
   ```
   O token é digitado pelo Leo no terminal dele, nunca passado pelo chat. **Conferir a função logo em seguida**, com a conta de teste:
   ```powershell
   $env:HUB_CONTA_TESTE="<caminho da conta de teste>"
   python -m pytest tests/contas -m banco -q          # esperado: 2 passed
   ```
   Se falhar com `401 Invalid JWT` (vem do portão do Supabase, não da função), publicar de novo com `--no-verify-jwt` — é seguro: a própria função confere se quem chama é admin (`eh_admin`) antes de usar a chave de serviço.
6. Migração de verdade: `python migracao/trazer_usuarios_geomap.py`. Rodar uma vez só: uma segunda execução desfaria senhas já trocadas no Hub, e o script recusa (só passa com `--forcar`).
7. GeoMap: merge de `feat/login-hub` em `master` + push → Render publica o backend e o Pages publica o frontend. Conferir em seguida que a automação ainda entra (login de `automacao@geoportal.local` responde 200, não 410).
8. Hub: merge de `login-unico` em `main` + push (o Pages publica sozinho). Servidor Geo: `cd $HOME\hub-geotech; git pull`.

## Conferência

9. O Leo entra no GeoMap com a senha de sempre e vê os mesmos mapas; entra no Hub direto (mesma sessão).
10. Tela Usuários do Hub (manual, no site publicado):
    - as pessoas do GeoMap aparecem com o GeoMap marcado e os grupos certos;
    - abrir uma pessoa, trocar um grupo do GeoMap, salvar → sem aviso de erro; no GeoMap, a pessoa vê os mapas do grupo novo;
    - criar uma pessoa de teste → aparece a senha provisória; entrar com ela → tela "Defina sua senha"; depois **Remover acesso** dessa pessoa de teste.
11. Para cada pessoa da lista "precisa senha provisória do Hub": **Redefinir senha** e entregar a provisória (ela troca no primeiro acesso).
12. No dia seguinte: conferir que a automação diária do GeoMap rodou.

## Voltar atrás

- GeoMap: `LOGIN_LOCAL=1` no Render (religa o login e as telas antigas; os hashes antigos continuam no banco) e reverter o merge em `master`.
- Hub: reverter o merge da `login-unico`; `agendamento/instalar_tarefas.cmd` de uma versão anterior recria a sincronização. As colunas novas do banco não atrapalham, mas a função `acesso_salvar` antiga (5 parâmetros) precisa ser recriada a partir de `supabase/migrations/20261005090000_admin_acessos_ferramentas.sql` para a tela Usuários antiga voltar.
