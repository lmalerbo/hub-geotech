-- Drone: o painel passa a alimentar o Início novo (redesenho das telas, S3).
-- Muda só hub.drone_painel(): a geração traz pedido_em/iniciado_em/concluido_em,
-- entra publicadas_7d, e obstaculos_antigos/fora_da_base viram [{cod_faz, fazenda}].
-- Para voltar atrás: rodar de novo a definição de 20261009090000_drone_melhorias.sql.
begin;

create or replace function hub.drone_painel()
returns jsonb language sql stable security definer set search_path = hub as $$
select jsonb_build_object(
  'solicitacoes', coalesce((select jsonb_agg(x order by x->>'criado_em') from (
      select jsonb_build_object('id', s.id, 'cod_faz', s.cod_faz, 'fazenda', f.nome, 'tipo', s.tipo, 'status', s.status,
               'observacao', s.observacao, 'data_desejada', s.data_desejada, 'criado_em', s.criado_em,
               'solicitante', u.nome, 'solicitante_id', s.solicitante_id,
               'geracao', (select jsonb_build_object('id', g.id, 'status', g.status,
                                    'alertas', coalesce(jsonb_array_length(g.alertas), 0),
                                    'publicar_pedido_em', g.publicar_pedido_em, 'publicacao_erro', g.publicacao_erro,
                                    'erro', g.erro, 'pedido_em', g.pedido_em, 'iniciado_em', g.iniciado_em,
                                    'concluido_em', g.concluido_em)
                             from hub.drone_geracoes g where g.solicitacao_id = s.id and g.status <> 'descartada'
                            order by g.id desc limit 1)) x
        from hub.drone_solicitacoes s
        join hub.fazendas f on f.cod_faz = s.cod_faz
        left join hub.usuarios u on u.id = s.solicitante_id
       where s.origem <> 'legado' and s.status not in ('ok', 'cancelado')) q), '[]'::jsonb),
  'publicadas_7d', (select count(*) from hub.drone_geracoes
                     where status = 'publicada' and concluido_em > now() - interval '7 days'),
  'incompletas', coalesce((select jsonb_agg(jsonb_build_object('cod_faz', v.cod_faz, 'fazenda', f.nome,
                                                               'pct', v.cobertura_pct) order by v.cobertura_pct)
                             from hub.drone_cobertura_v v join hub.fazendas f on f.cod_faz = v.cod_faz
                            where v.cobertura_pct < 100), '[]'::jsonb),
  'obstaculos_antigos', coalesce((select jsonb_agg(jsonb_build_object('cod_faz', x.cod_faz, 'fazenda', f.nome) order by f.nome)
                             from (select distinct v.cod_faz
                                     from hub.drone_obstaculo_versoes v
                                    where v.vigente and v.enviado_em < now() - make_interval(
                                            months => (select valor::int from hub.drone_parametros
                                                        where chave = 'alerta_obstaculos_meses'))) x
                             join hub.fazendas f on f.cod_faz = x.cod_faz), '[]'::jsonb),
  'fora_da_base', coalesce((select jsonb_agg(jsonb_build_object('cod_faz', x.cod_faz, 'fazenda', f.nome) order by f.nome)
                             from (select distinct p.cod_faz
                                     from hub.projetos p
                                     join hub.projeto_revisoes r on r.projeto_id = p.id and r.vigente and r.documento = 'normal'
                                     join hub.drone_revisao_talhoes t on t.revisao_id = r.id
                                    where p.modulo_id = 'drone' and p.tipo = 'individual'
                                      and not exists (select 1 from hub.talhao_geom g
                                                       where g.cod_faz = p.cod_faz and g.talhao_num = t.talhao_num)) x
                             join hub.fazendas f on f.cod_faz = x.cod_faz), '[]'::jsonb));
$$;

commit;
