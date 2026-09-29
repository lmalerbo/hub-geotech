# Agendamento no servidor Geo

Duas tarefas do Agendador de Tarefas do Windows mantêm o Hub atualizado:

| Tarefa | Quando | O que faz |
|---|---|---|
| Hub Geotech - Rodada diaria | todo dia, 07:00 | Base Fazendas → PLANAGRI → Conservação → regras (`ingestao/rodar_diario.py`) |
| Hub Geotech - Sincronizar usuarios | a cada hora | contas e senhas do GeoMap → Hub (`ingestao/sincronizar_usuarios.py`) |

A exportação da Base Fazendas (FME) chega por volta das 06:02, então às 07:00 o arquivo do dia já está lá.

**Não precisa de admin.** As tarefas rodam sob o usuário que as criou (a conta `geotecnologia`), igual à automação Talhões/Limites do GeoMap nessa mesma máquina. O modo é "somente quando o usuário estiver conectado": se a tela estiver bloqueada, ela roda normalmente; se a máquina estiver suspensa, não roda. A energia do servidor já foi ajustada para nunca suspender.

## Instalação (uma vez só)

No PowerShell do servidor Geo, logado como `geotecnologia`. O Python e o git já estão instalados pelo Scoop, desde a automação do GeoMap.

1. Baixar o código:

   ```powershell
   cd $HOME
   git clone https://github.com/lmalerbo/hub-geotech.git
   cd hub-geotech
   pip install -r ingestao/requirements.txt
   ```

2. Copiar os dois arquivos secretos, que **não estão no GitHub**, do PC do Leo para as mesmas posições no servidor:
   - `hub-geotech-supabase.env`, na raiz do `hub-geotech`;
   - `ingestao/usuarios_hub.json`.

3. No `hub-geotech-supabase.env` do servidor, acrescentar uma linha com a conexão do banco do GeoMap. Copie o valor de `DATABASE_URL` que está em `geomap/backend/.env` no PC do Leo:

   ```text
   GEOMAP_DATABASE_URL=postgresql://...
   ```

   O arquivo precisa terminar com uma quebra de linha antes de você colar a linha nova.

4. Testar na mão:

   ```powershell
   .\agendamento\rodar_diario.cmd
   .\agendamento\sincronizar_usuarios.cmd
   Get-Content agendamento\logs\diario.log -Encoding UTF8 -Tail 25
   Get-Content agendamento\logs\usuarios.log -Encoding UTF8 -Tail 15
   ```

   As duas execuções devem terminar com `codigo de saida: 0`. Use sempre `-Encoding UTF8`: sem ele, o PowerShell 5.1 mostra os acentos quebrados, mas o arquivo está certo.

5. Criar as tarefas e rodar uma vez pelo agendador:

   ```powershell
   .\agendamento\instalar_tarefas.cmd
   schtasks /run /tn "Hub Geotech - Rodada diaria"
   ```

   Espere cerca de 1 minuto e confira o `diario.log` de novo.

## Dia a dia

- **Ver se rodou:** abra o card "Dados atualizados" no Dashboard do Hub (fica vermelho se passar de 26 h sem rodada), ou leia os logs em `agendamento/logs/`.
- **Atualizar o código** depois de mudanças no GitHub:

  ```powershell
  cd $HOME\hub-geotech
  git pull
  ```

- **Ver as tarefas:** `schtasks /query /tn "Hub Geotech - Rodada diaria" /v /fo list`
- **Remover as tarefas:**

  ```powershell
  schtasks /delete /tn "Hub Geotech - Rodada diaria" /f
  schtasks /delete /tn "Hub Geotech - Sincronizar usuarios" /f
  ```

## Problemas já conhecidos nessa rede

Esses problemas foram vistos na instalação do GeoMap:

- **Internet externa bloqueada** (erro estranho no `pip` ou no `git`): a rede exige autenticar no portal do FortiGate pelo navegador. Abra um navegador na máquina, faça o login no portal e tente de novo.
- **A pasta de rede "não existe" na primeira tentativa** (`\\lnxfs3\work3` ou `\\lnxpdc\work`): tente de novo. A primeira conexão SMB às vezes demora. O `config.json` usa os caminhos de rede completos, sem letra de unidade, então não depende de `I:` ou `N:` estarem mapeadas.
- **Erro de certificado SSL no Python:** os scripts já usam o `truststore`, que confia no certificado do FortiGate instalado no Windows. Não desligue a verificação de certificado.
