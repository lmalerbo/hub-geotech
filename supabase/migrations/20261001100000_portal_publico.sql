-- Portal de download (app/portal.html): leitura PÚBLICA, sem login.
--
-- O pessoal de campo (gestores/operadores) não tem conta no Hub, como já não
-- tinha nos portais antigos, que liam as GitHub Releases públicas direto.
-- Esta função devolve SÓ o que o portal precisa: os arquivos das revisões
-- vigentes, por fazenda. Nada de status, usuários ou histórico. Os arquivos
-- em si já são públicos (releases de repositórios públicos).
--
-- Projeto personalizado (bloco) aparece em cada fazenda que o compõe, com o
-- nome do bloco em "bloco".
--
-- Fica no schema public (já exposto e com acesso anon) e NÃO no hub: dar
-- acesso anon ao schema hub deixaria chamáveis as funções que o Postgres
-- libera pra PUBLIC por padrão. O hub continua fechado pra quem não tem login.

begin;

create or replace function public.portal_arquivos()
returns table (
  modulo         text,
  cod_faz        int,
  fazenda        text,
  bloco          text,
  documento      text,
  documento_nome text,
  revisao        int,
  marcador       text,
  nome_arquivo   text,
  url            text,
  tamanho_bytes  bigint,
  publicado_em   timestamptz
)
language sql
stable
security definer
set search_path = hub
as $$
  select p.modulo_id,
         fz.cod_faz,
         fz.nome,
         case when p.tipo = 'personalizado' then p.nome end,
         r.documento,
         dt.nome,
         r.numero,
         dt.marcador,
         a.nome_arquivo,
         a.release_url,
         a.tamanho_bytes,
         a.publicado_em
    from projetos p
    join projeto_revisoes r  on r.projeto_id = p.id and r.vigente
    join revisao_arquivos a  on a.revisao_id = r.id
    join documento_tipos dt  on dt.modulo_id = p.modulo_id and dt.codigo = r.documento
    cross join lateral (
      select p.cod_faz as cod where p.tipo = 'individual'
      union
      select po.cod_faz
        from revisao_origens o
        join projeto_revisoes ro on ro.id = o.origem_revisao_id
        join projetos po on po.id = ro.projeto_id
       where o.revisao_id = r.id
    ) f
    join fazendas fz on fz.cod_faz = f.cod
   order by fz.nome, dt.ordem, a.nome_arquivo;
$$;

revoke all on function public.portal_arquivos() from public;
grant execute on function public.portal_arquivos() to anon, authenticated, service_role;

commit;
