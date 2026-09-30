-- Administração pelo Hub (tela de Configurações/Usuários), no lugar do
-- arquivo usuarios_hub.json e dos campos de protótipo:
--
--   hub.acessos      quem pode entrar no Hub (e-mail, nome, papel, módulos).
--                    A sincronização (ingestao/sincronizar_usuarios.py) lê
--                    daqui: cria a conta, copia a senha do GeoMap e bloqueia
--                    quem saiu da lista. A senha continua sendo do GeoMap.
--   ferramentas      lista de ferramentas (nome, descrição, URL) em
--                    hub.parametros, editável pelo admin.
--   parâmetros       safra da colheita e dias de porte, editáveis pelo admin.
--
-- Tudo escrito só por admin (funções security definer que conferem).

begin;

-- Registros de administração (acessos, parâmetros) no log, sem fazenda/talhão.
alter table hub.log_auditoria drop constraint log_auditoria_entidade_tipo_check;
alter table hub.log_auditoria add constraint log_auditoria_entidade_tipo_check
  check (entidade_tipo in ('fazenda', 'talhao', 'sistema'));

create or replace function hub.eh_admin()
returns boolean language sql stable security definer set search_path = hub as $$
  select exists (select 1 from hub.usuarios u where u.id = auth.uid() and u.admin);
$$;

-- ── Acessos ─────────────────────────────────────────────────────────────
create table hub.acessos (
  email         text primary key check (email = lower(trim(email)) and email like '%@%'),
  nome          text not null,
  papel         text not null default 'leitura' check (papel in ('editor', 'leitura', 'solicitante')),
  admin         boolean not null default false,
  modulos       text[] not null default '{}',
  atualizado_por uuid references hub.usuarios (id),
  atualizado_em timestamptz not null default now()
);

-- Situação de cada acesso pra tela: a conta já existe? está bloqueada?
create or replace function hub.acessos_situacao()
returns table (email text, nome text, papel text, admin boolean, modulos text[], atualizado_em timestamptz,
               usuario_id uuid, conta_criada boolean, bloqueado boolean, ultimo_login timestamptz)
language sql stable security definer set search_path = hub, auth as $$
  select a.email, a.nome, a.papel, a.admin, a.modulos, a.atualizado_em,
         u.id, u.id is not null, coalesce(u.banned_until > now(), false), u.last_sign_in_at
    from hub.acessos a
    left join auth.users u on lower(u.email) = a.email
   where hub.eh_admin()
   order by a.nome;
$$;

-- Salva (cria ou altera) um acesso. Se a conta já existe, aplica na hora o
-- papel e os módulos; conta nova é criada pela sincronização (até 1 hora).
create or replace function hub.acesso_salvar(p_email text, p_nome text, p_papel text, p_admin boolean, p_modulos text[])
returns void language plpgsql security definer set search_path = hub, auth as $$
declare
  v_email text := lower(trim(p_email));
  v_uid   uuid;
begin
  if not hub.eh_admin() then raise exception 'Só administradores alteram acessos'; end if;
  if v_email !~ '^[^@\s]+@[^@\s]+$' then raise exception 'E-mail inválido: %', p_email; end if;
  if length(trim(coalesce(p_nome, ''))) = 0 then raise exception 'Informe o nome'; end if;
  if exists (select 1 from unnest(p_modulos) m where m not in (select id from hub.modulos)) then
    raise exception 'Módulo inválido';
  end if;
  insert into hub.acessos (email, nome, papel, admin, modulos, atualizado_por, atualizado_em)
  values (v_email, trim(p_nome), p_papel, coalesce(p_admin, false), coalesce(p_modulos, '{}'), auth.uid(), now())
  on conflict (email) do update
    set nome = excluded.nome, papel = excluded.papel, admin = excluded.admin, modulos = excluded.modulos,
        atualizado_por = excluded.atualizado_por, atualizado_em = now();

  select id into v_uid from auth.users where lower(email) = v_email;
  if v_uid is not null and exists (select 1 from hub.usuarios where id = v_uid) then
    update hub.usuarios set nome = trim(p_nome), papel = p_papel, admin = coalesce(p_admin, false) where id = v_uid;
    delete from hub.usuario_modulos where usuario_id = v_uid;
    insert into hub.usuario_modulos (usuario_id, modulo_id) select v_uid, unnest(coalesce(p_modulos, '{}'));
  end if;
  insert into hub.log_auditoria (entidade_tipo, entidade_id, campo, valor_novo, usuario_id, origem)
  values ('sistema', 0, 'acesso', v_email || ' · ' || p_papel || case when p_admin then ' + admin' else '' end
          || ' · ' || array_to_string(p_modulos, ', '), auth.uid(), 'usuario');
end $$;

-- Remove o acesso: tira os módulos na hora; a sincronização bloqueia a conta.
create or replace function hub.acesso_remover(p_email text)
returns void language plpgsql security definer set search_path = hub, auth as $$
declare
  v_email text := lower(trim(p_email));
  v_uid   uuid;
begin
  if not hub.eh_admin() then raise exception 'Só administradores alteram acessos'; end if;
  select id into v_uid from auth.users where lower(email) = v_email;
  if v_uid = auth.uid() then raise exception 'Você não pode remover o seu próprio acesso'; end if;
  delete from hub.acessos where email = v_email;
  if v_uid is not null then
    delete from hub.usuario_modulos where usuario_id = v_uid;
    update hub.usuarios set admin = false, papel = 'leitura' where id = v_uid;
  end if;
  insert into hub.log_auditoria (entidade_tipo, entidade_id, campo, valor_novo, usuario_id, origem)
  values ('sistema', 0, 'acesso', v_email || ' · removido', auth.uid(), 'usuario');
end $$;

-- ── Parâmetros e ferramentas ───────────────────────────────────────────
insert into hub.parametros (chave, valor, descricao) values
  ('ferramentas', '[{"id":"geomap","nome":"GeoMap","descricao":"Mapas, polígonos e ortomosaicos processados de todas as fazendas.","url":"https://lmalerbo.github.io/geomap/","icone":"map","cor":"#2566e8"},{"id":"kronos","nome":"Kronos","descricao":"Gestão de frota e hardware agrícola: monitores, receptores e bordos por máquina.","url":"","icone":"memory","cor":"#5b6ee8"}]',
   'Ferramentas mostradas no Hub (JSON: id, nome, descricao, url, icone, cor)')
on conflict (chave) do nothing;

create or replace function hub.salvar_parametro(p_chave text, p_valor text)
returns void language plpgsql security definer set search_path = hub as $$
begin
  if not hub.eh_admin() then raise exception 'Só administradores alteram parâmetros'; end if;
  if p_chave not in ('colheita_safra', 'colheita_dias_porte', 'ferramentas') then
    raise exception 'Parâmetro não editável: %', p_chave;
  end if;
  if p_chave = 'colheita_safra' and p_valor !~ '^\d{2}-\d{2}$' then
    raise exception 'Safra no formato 26-27';
  end if;
  if p_chave = 'colheita_dias_porte' and (p_valor !~ '^\d+$' or p_valor::int not between 30 and 400) then
    raise exception 'Dias de porte entre 30 e 400';
  end if;
  if p_chave = 'ferramentas' then
    perform p_valor::jsonb;   -- precisa ser JSON válido
  end if;
  update hub.parametros set valor = p_valor, atualizado_em = now() where chave = p_chave;
  insert into hub.log_auditoria (entidade_tipo, entidade_id, campo, valor_novo, usuario_id, origem)
  values ('sistema', 0, 'parametro ' || p_chave, left(p_valor, 500), auth.uid(), 'usuario');
end $$;

-- ── Segurança ──────────────────────────────────────────────────────────
alter table hub.acessos enable row level security;
-- sem policy de leitura: a tela usa hub.acessos_situacao() (só admin).
grant all on hub.acessos to service_role;

revoke all on function hub.eh_admin()                                      from public, anon;
revoke all on function hub.acessos_situacao()                              from public, anon;
revoke all on function hub.acesso_salvar(text, text, text, boolean, text[]) from public, anon;
revoke all on function hub.acesso_remover(text)                            from public, anon;
revoke all on function hub.salvar_parametro(text, text)                    from public, anon;
grant execute on function hub.eh_admin()                                      to authenticated, service_role;
grant execute on function hub.acessos_situacao()                              to authenticated, service_role;
grant execute on function hub.acesso_salvar(text, text, text, boolean, text[]) to authenticated, service_role;
grant execute on function hub.acesso_remover(text)                            to authenticated, service_role;
grant execute on function hub.salvar_parametro(text, text)                    to authenticated, service_role;

commit;
