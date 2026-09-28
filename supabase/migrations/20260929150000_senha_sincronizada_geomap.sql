-- Login do Hub com a mesma senha do GeoMap.
--
-- O GeoMap é o dono das senhas; o Hub guarda uma cópia do hash bcrypt, que a
-- sincronização (ingestao/sincronizar_usuarios.py) atualiza periodicamente.
-- A senha em si nunca trafega — só o hash, que o GeoMap e o Supabase Auth
-- guardam no mesmo formato (bcrypt).
--
-- Grava direto em auth.users em vez de usar o password_hash da API de admin
-- do Supabase, que tem bug conhecido (supabase/auth#1678). Só a service_role
-- executa.

create or replace function hub.definir_senha_hash(p_usuario uuid, p_hash text)
returns void
language plpgsql
security definer
set search_path = hub
as $$
begin
  if p_hash !~ '^\$2[aby]\$\d{2}\$.{53}$' then
    raise exception 'Hash de senha em formato inesperado (esperado bcrypt)';
  end if;
  update auth.users
     set encrypted_password = p_hash,
         updated_at = now()
   where id = p_usuario
     and encrypted_password is distinct from p_hash;
end $$;

revoke all on function hub.definir_senha_hash(uuid, text) from public, anon, authenticated;
grant execute on function hub.definir_senha_hash(uuid, text) to service_role;
