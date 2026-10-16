# Virada do login único (Hub + GeoMap)

Duração: ~1 h, fora do horário de pico. Ninguém troca de senha (o hash atual de cada pessoa vem do GeoMap).
O Leo acompanha todos os passos. Spec: `docs/superpowers/specs/2026-10-09-login-unico-design.md`.

Branches: Hub `login-unico` (hub-geotech); GeoMap `feat/login-hub` (backend) + `feat/login-hub-front` (frontend), juntas antes do passo 5.

## Antes (pode ser na véspera)

**Atenção:** o passo 1 troca a função `acesso_salvar` usada pela tela Usuários publicada hoje. Entre o passo 1 e o passo 7 a tela Usuários do Hub fica fora (o resto do Hub funciona). Por isso, faça o passo 1 no mesmo dia, logo antes da virada.

1. SQL Editor do Hub (nova query): `supabase/migrations/20261012090000_login_unico.sql`.
2. Função `contas` (no PC do Leo, pasta do hub-geotech):
   ```powershell
   supabase login        # só na primeira vez (abre o navegador)
   supabase functions deploy contas --project-ref dpvsivypabmvmrrpgmhc
   supabase secrets set --project-ref dpvsivypabmvmrrpgmhc GEOMAP_URL=https://geomap-docker.onrender.com
   supabase secrets set --project-ref dpvsivypabmvmrrpgmhc HUB_INTEGRACAO_TOKEN=<o Leo cola o valor do hub-geotech-supabase.env>
   ```
   O token é digitado pelo Leo no terminal dele, nunca passado pelo chat.
3. Render do GeoMap (painel → Environment): `HUB_SUPABASE_URL=https://dpvsivypabmvmrrpgmhc.supabase.co` e `HUB_SUPABASE_ANON_KEY=<chave publicável do Hub, a mesma que está em app/index.html>`. **Não** publicar o código ainda.
4. Simulação (só leitura): `python migracao/trazer_usuarios_geomap.py --simular` e conferir a lista com o Leo. Na simulação de 16/10/2026 apareceram:
   - **4 pessoas com a senha provisória do GeoMap** (arthur.lopes, bruno.soares, karen.martins, lucas.campos): não recebem o hash; o Leo entrega uma provisória do Hub no passo 11;
   - **2 contas técnicas do GeoMap** (`automacao@geoportal.local`, admin no GeoMap, e `__teste_vigiar__@geoportal.local`): decidir com o Leo se entram no Hub; se não, desativá-las no GeoMap antes do passo 6.

## Virada

5. GeoMap backend: juntar `feat/login-hub-front` em `feat/login-hub`, merge em `master` → deploy no Render. A partir daqui o login antigo do GeoMap responde 410: seguir direto para os passos 6–8.
6. Migração de verdade: `python migracao/trazer_usuarios_geomap.py`.
7. Publicar o frontend do GeoMap (workflow `deploy-frontend`) e o app do Hub (merge de `login-unico` em `main` + push; o Pages publica sozinho).
8. Servidor Geo: `cd $HOME\hub-geotech; git pull; schtasks /delete /tn "Hub Geotech - Sincronizar usuarios" /f`.

## Conferência

9. Testes contra o que foi publicado:
   ```powershell
   $env:HUB_CONTA_TESTE="<caminho da conta de teste>"
   python -m pytest tests/contas -m banco -q          # função contas: 2 passed
   python tests/app/teste_usuarios_tela.py           # tela Usuários: FALHAS: nenhuma
   ```
10. O Leo entra no GeoMap com a senha de sempre e vê os mesmos mapas; entra no Hub direto (mesma sessão).
11. Tela Usuários: as pessoas do GeoMap aparecem com o GeoMap marcado e os grupos certos. Para cada pessoa da lista "precisa senha provisória do Hub": **Redefinir senha** e entregar a provisória (ela troca no primeiro acesso).

## Voltar atrás

- GeoMap: `LOGIN_LOCAL=1` no Render (religa o login e as telas antigas; os hashes antigos continuam no banco) e reverter o commit do frontend.
- Hub: reverter o merge da `login-unico`; `agendamento/instalar_tarefas.cmd` de uma versão anterior recria a sincronização. As colunas novas do banco não atrapalham, mas a função `acesso_salvar` antiga (5 parâmetros) precisa ser recriada a partir de `supabase/migrations/20261005090000_admin_acessos_ferramentas.sql` para a tela Usuários antiga voltar.
