// Apresentação semanal: dados fictícios do modo demonstração (file:// ou ?demo). Mesma fixture dos testes
// (tests/app/apresentacao/dados). Não há dado real aqui.
// Gerado por tests/app/apresentacao/gerar_demo.js. Não editar à mão.
var AP_DEMO_HUB = {
  talhoes: [
    {"cod_faz":9001,"talhao_num":1,"layer":1,"area_ha":10,"estagio":"Planta","data_ultimo_corte":null,"ciclo":null,"sist_conser":null,"sist_conser_em":null,"updated_at":"2026-10-28T12:00:00Z","propriedade":"Fazenda Sintetica A"},
    {"cod_faz":9001,"talhao_num":2,"layer":2,"area_ha":20,"estagio":"Planta","data_ultimo_corte":null,"ciclo":null,"sist_conser":null,"sist_conser_em":null,"updated_at":"2026-10-28T12:00:00Z","propriedade":"Fazenda Sintetica A"},
    {"cod_faz":9001,"talhao_num":3,"layer":3,"area_ha":15,"estagio":"Planta","data_ultimo_corte":null,"ciclo":null,"sist_conser":null,"sist_conser_em":null,"updated_at":"2026-10-28T12:00:00Z","propriedade":"Fazenda Sintetica A"},
    {"cod_faz":9002,"talhao_num":1,"layer":4,"area_ha":30,"estagio":"Soca","data_ultimo_corte":null,"ciclo":null,"sist_conser":null,"sist_conser_em":null,"updated_at":"2026-10-28T12:00:00Z","propriedade":"Fazenda Sintetica B"},
    {"cod_faz":9002,"talhao_num":2,"layer":5,"area_ha":5,"estagio":"Soca","data_ultimo_corte":null,"ciclo":null,"sist_conser":null,"sist_conser_em":null,"updated_at":"2026-10-28T12:00:00Z","propriedade":"Fazenda Sintetica B"},
    {"cod_faz":9003,"talhao_num":1,"layer":6,"area_ha":12,"estagio":"Soca","data_ultimo_corte":null,"ciclo":null,"sist_conser":null,"sist_conser_em":null,"updated_at":"2026-10-28T12:00:00Z","propriedade":"Fazenda Sintetica C"},
    {"cod_faz":9003,"talhao_num":2,"layer":7,"area_ha":8,"estagio":"Soca","data_ultimo_corte":null,"ciclo":null,"sist_conser":null,"sist_conser_em":null,"updated_at":"2026-10-28T12:00:00Z","propriedade":"Fazenda Sintetica C"}
  ],
  colheita_talhoes: [
    {"layer":1,"cod_faz":9001,"talhao_num":1,"area_ha":10,"estagio":"Planta","data_ultimo_corte":null,"frente":"3","periodo_op":3,"cortado":true,"tipo_linha":"Linha","ciclo":"26/27","projeto_desatualizado":false,"updated_at":"2026-10-28T12:00:00Z","status":"CONCLUIDO","voo_id":null,"voo_tipo":null,"voo_status":null,"voo_liberar_em":null},
    {"layer":2,"cod_faz":9001,"talhao_num":2,"area_ha":20,"estagio":"Planta","data_ultimo_corte":null,"frente":"BIS - 3","periodo_op":4,"cortado":true,"tipo_linha":"Linha","ciclo":"26/27","projeto_desatualizado":false,"updated_at":"2026-10-28T12:00:00Z","status":"CONCLUIDO","voo_id":null,"voo_tipo":null,"voo_status":null,"voo_liberar_em":null},
    {"layer":3,"cod_faz":9001,"talhao_num":3,"area_ha":15,"estagio":"Planta","data_ultimo_corte":null,"frente":"FOCA 1","periodo_op":4,"cortado":true,"tipo_linha":"Linha","ciclo":"26/27","projeto_desatualizado":false,"updated_at":"2026-10-28T12:00:00Z","status":"CONCLUIDO","voo_id":null,"voo_tipo":null,"voo_status":null,"voo_liberar_em":null},
    {"layer":4,"cod_faz":9002,"talhao_num":1,"area_ha":30,"estagio":"Soca","data_ultimo_corte":null,"frente":"5","periodo_op":5,"cortado":false,"tipo_linha":"Linha","ciclo":"26/27","projeto_desatualizado":false,"updated_at":"2026-10-28T12:00:00Z","status":"A FAZER","voo_id":null,"voo_tipo":null,"voo_status":null,"voo_liberar_em":null},
    {"layer":5,"cod_faz":9002,"talhao_num":2,"area_ha":5,"estagio":"Soca","data_ultimo_corte":null,"frente":"Expansão 2","periodo_op":null,"cortado":false,"tipo_linha":"Linha","ciclo":"25/26","projeto_desatualizado":true,"updated_at":"2026-10-28T12:00:00Z","status":"REAVALIAR","voo_id":null,"voo_tipo":null,"voo_status":null,"voo_liberar_em":null},
    {"layer":6,"cod_faz":9003,"talhao_num":1,"area_ha":12,"estagio":"Soca","data_ultimo_corte":null,"frente":"3","periodo_op":6,"cortado":false,"tipo_linha":"Linha","ciclo":"26/27","projeto_desatualizado":false,"updated_at":"2026-10-28T12:00:00Z","status":"SEM LINHAS","voo_id":null,"voo_tipo":null,"voo_status":null,"voo_liberar_em":null},
    {"layer":7,"cod_faz":9003,"talhao_num":2,"area_ha":8,"estagio":"Soca","data_ultimo_corte":null,"frente":"BIS - 5","periodo_op":7,"cortado":false,"tipo_linha":"Linha","ciclo":"26/27","projeto_desatualizado":false,"updated_at":"2026-10-28T12:00:00Z","status":"A FAZER","voo_id":null,"voo_tipo":null,"voo_status":null,"voo_liberar_em":null}
  ],
  talhao_plantio: [
    {"layer":1,"mes_plantio":"2026-05-10","seq_plantio":1,"ambiente":"A","mapeamento":"Concluido","projeto":"Ok","updated_at":"2026-10-28T12:00:00Z","plantio_realizado_em":"2026-05-12T12:00:00Z"},
    {"layer":2,"mes_plantio":"2026-05-20","seq_plantio":2,"ambiente":"A","mapeamento":"Concluido","projeto":"Ok","updated_at":"2026-10-28T12:00:00Z","plantio_realizado_em":"2026-05-22T12:00:00Z"},
    {"layer":3,"mes_plantio":"2026-08-20","seq_plantio":3,"ambiente":"B","mapeamento":"Em andamento","projeto":"Andamento","updated_at":"2026-10-28T12:00:00Z","plantio_realizado_em":null},
    {"layer":4,"mes_plantio":"2026-07-01","seq_plantio":4,"ambiente":"B","mapeamento":"Pendente","projeto":"Pendente","updated_at":"2026-10-28T12:00:00Z","plantio_realizado_em":null},
    {"layer":5,"mes_plantio":"2026-07-15","seq_plantio":5,"ambiente":"B","mapeamento":"Aguardando","projeto":"Aguard. Map.","updated_at":"2026-10-28T12:00:00Z","plantio_realizado_em":null},
    {"layer":6,"mes_plantio":null,"seq_plantio":null,"ambiente":null,"mapeamento":"Aguardando mapa","projeto":"Ag. Mapa","updated_at":"2026-10-28T12:00:00Z","plantio_realizado_em":null},
    {"layer":7,"mes_plantio":"2026-08-05","seq_plantio":6,"ambiente":"A","mapeamento":"Concluido","projeto":"Ok","updated_at":"2026-10-28T12:00:00Z","plantio_realizado_em":"2026-08-07T12:00:00Z"}
  ],
  talhao_preparo: [
    {"layer":1,"status":null,"tipo_linha":null,"updated_at":"2026-10-28T12:00:00Z","etapa":"Ok","conservacao_em":null},
    {"layer":2,"status":null,"tipo_linha":null,"updated_at":"2026-10-28T12:00:00Z","etapa":"Preparo","conservacao_em":null},
    {"layer":3,"status":null,"tipo_linha":null,"updated_at":"2026-10-28T12:00:00Z","etapa":"Ok","conservacao_em":null},
    {"layer":4,"status":null,"tipo_linha":null,"updated_at":"2026-10-28T12:00:00Z","etapa":"Escoamento","conservacao_em":null},
    {"layer":5,"status":null,"tipo_linha":null,"updated_at":"2026-10-28T12:00:00Z","etapa":"Ok","conservacao_em":null},
    {"layer":6,"status":null,"tipo_linha":null,"updated_at":"2026-10-28T12:00:00Z","etapa":"Identificação","conservacao_em":null},
    {"layer":7,"status":null,"tipo_linha":null,"updated_at":"2026-10-28T12:00:00Z","etapa":"Ok","conservacao_em":null}
  ],
  etapas: [
    {"id":1,"modulo_id":"preparo","ordem":1,"nome":"Identificação","escopo":"talhao"},
    {"id":2,"modulo_id":"preparo","ordem":2,"nome":"Escoamento","escopo":"talhao"},
    {"id":3,"modulo_id":"preparo","ordem":3,"nome":"Observações","escopo":"talhao"},
    {"id":4,"modulo_id":"preparo","ordem":4,"nome":"Preparo","escopo":"talhao"}
  ],
  preparo_entregas: [
    {"layer":1,"cod_faz":9001,"entregue_em":"2026-06-10T14:00:00Z","origem":"hub"},
    {"layer":3,"cod_faz":9001,"entregue_em":"2026-08-01T02:00:00Z","origem":"hub"},
    {"layer":5,"cod_faz":9002,"entregue_em":"2026-06-02T12:00:00Z","origem":"lancamento_inicial"},
    {"layer":7,"cod_faz":9003,"entregue_em":"2026-03-15T12:00:00Z","origem":"ciclo_25_26"}
  ]
};
var AP_DEMO_DRONE = [
  {"cod_faz":9001,"documento":"normal","revisao_id":1101,"area_aplicacao_ha":10.4,"safra":"26/27"},
  {"cod_faz":9003,"documento":"normal","revisao_id":1102,"area_aplicacao_ha":5.3,"safra":"26/27"},
  {"cod_faz":9002,"documento":"catacao","revisao_id":1103,"area_aplicacao_ha":6.2,"safra":"25/26"},
  {"cod_faz":9003,"documento":"catacao","revisao_id":1104,"area_aplicacao_ha":3.6,"safra":null}
];
var AP_DEMO_VOOS = {
 "resumo": {
  "realizadoHa": 1000,
  "aVoarHa": 400,
  "realizadoTalhoes": 12,
  "aVoarTalhoes": 5
 },
 "ultimos15DiasUteis": {
  "de": "2026-10-08",
  "ate": "2026-10-28",
  "diasComVoo": 11,
  "talhoes": 9,
  "ha": 180
 },
 "porTipo": [
  {
   "tipo": "Ervas Daninhas",
   "realizadoHa": 600,
   "aVoarHa": 300
  },
  {
   "tipo": "Falhas Plantio Forn.",
   "realizadoHa": 200,
   "aVoarHa": 100
  },
  {
   "tipo": "Expansões",
   "realizadoHa": 200,
   "aVoarHa": 0
  }
 ],
 "atualizadoEm": "2026-10-28",
 "desatualizado": false
};
var AP_DEMO_METAS = { meta_ervas_ha: 20863, meta_fornecedor_ha: 3500, meta_ha_dia: 250, drone_pendente_ha: 2000, safra_atual: '26/27', inicio_safra: '2026-04-01' };
