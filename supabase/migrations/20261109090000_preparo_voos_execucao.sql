-- Preparo, bloco S2 de 09/11/2026:
-- 1. voos_preparo.py passa a registrar cada rodada em hub.execucoes_ingestao, para o card
--    "Dados atualizados" acusar quando a leitura dos voos parar (ficou parada de 29/10 a 09/11 sem ninguém ver).
-- 2. Remove hub.preparo_aviso_sem_voo: sem uso desde 04/11, quando a etapa Voo virou calculada na tela.
--    Os avisos já gravados (log_auditoria, campo 'voo_aviso') ficam.
-- Desfazer: supabase/migrations/volta/20261109090000_preparo_voos_execucao_volta.sql
begin;

alter table hub.execucoes_ingestao drop constraint if exists execucoes_ingestao_fonte_check;
alter table hub.execucoes_ingestao add constraint execucoes_ingestao_fonte_check
  check (fonte in ('base_fazendas', 'planagri', 'icol', 'conservacao', 'dronemgmt', 'talhao_geom', 'voos_preparo'));

drop function if exists hub.preparo_aviso_sem_voo(int, int[]);

commit;
