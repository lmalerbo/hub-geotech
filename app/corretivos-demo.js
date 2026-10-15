// Corretivos: dados fictícios para o modo demonstração (file:// ou ?demo). Não há dado real aqui.
// Mesma forma que crApiReal devolve (ver crResumoMapa e crDetalheMapa em corretivos.js).
const CR_DEMO_FAZENDAS = [
  { cod_faz: 10231, nome: 'Fazenda Demo Alfa' },
  { cod_faz: 10455, nome: 'Fazenda Demo Beta' },
  { cod_faz: 10780, nome: 'Fazenda Demo Gama' },
];
const CR_DEMO_MAPAS = [
  { id: 1, cod_faz: 10231, operacao: 'subsolagem', data: '2026-10-08', os: ['4520', '4521', '4530'], talhoes: 6,
    toneladas: 135.85, alterado_por_nome: 'Carla Mendes', alterado_em: '2026-10-09T14:20:00' },
  { id: 2, cod_faz: 10231, operacao: 'arado', data: '2026-09-02', os: ['4498'], talhoes: 4,
    toneladas: 31.25, alterado_por_nome: 'Rafael Souza', alterado_em: '2026-09-03T09:10:00' },
  { id: 3, cod_faz: 10231, operacao: 'supergrade', data: '2026-06-20', os: ['4410', '4411', '4412'], talhoes: 9,
    toneladas: 112.04, alterado_por_nome: 'Carla Mendes', alterado_em: '2026-06-22T16:45:00' },
  { id: 4, cod_faz: 10455, operacao: 'supergrade', data: '2026-10-12', os: ['4530'], talhoes: 3,
    toneladas: 18.6, alterado_por_nome: 'Rafael Souza', alterado_em: '2026-10-12T11:05:00' },
];
// Geometria fictícia: grade de 2 x 3 talhões (1 a 6). O talhão 9 não tem geometria (fora da Base).
const CR_DEMO_GEO = (() => {
  const areas = [23, 23, 21.4, 5.24, 4.7, 12];
  const features = areas.map((area, i) => {
    const x0 = -47.9 + (i % 3) * 0.0042, y0 = -15.8 - Math.floor(i / 3) * 0.0034;
    const x1 = x0 + 0.004, y1 = y0 - 0.003;
    return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]] },
             properties: { talhao: i + 1, area_prod: area } };
  });
  return { type: 'FeatureCollection', features };
})();
// Mapa 1: 3 aplicações (Dolomítico em 1 e 3; Fosfato em 2 e 3; Blend em 4 e 5) e o talhão 9 só em areas.
const CR_DEMO_DETALHE = {
  1: {
    areas: { 1: { area_ha: 23, editada: false }, 2: { area_ha: 23, editada: false }, 3: { area_ha: 21.4, editada: false },
             4: { area_ha: 5.24, editada: true }, 5: { area_ha: 4.7, editada: false }, 9: { area_ha: 4.2, editada: false } },
    apls: [
      { id: 11, tipo: 'calcario', calcario: 'dolomitico', dose: 2, dose_gesso: null, os: '4520', ordem: 1, talhoes: [1, 3] },
      { id: 12, tipo: 'fosfato', calcario: null, dose: 0.5, dose_gesso: null, os: '4521', ordem: 2, talhoes: [2, 3] },
      { id: 13, tipo: 'blend', calcario: 'dolomitico', dose: 1.5, dose_gesso: 1, os: '4530', ordem: 3, talhoes: [4, 5] },
    ],
  },
};

// Mesma superfície de crApiReal (corretivos.js), em memória.
const CR_API_DEMO = (() => {
  const copia = v => JSON.parse(JSON.stringify(v));
  let mapas = copia(CR_DEMO_MAPAS);
  const detalhes = copia(CR_DEMO_DETALHE);
  let proximoId = 100, proximaAplicacao = 100;
  const det = id => (detalhes[id] = detalhes[id] || { areas: {}, apls: [] });
  // Remove do mapa os talhões de 'candidatos' que ficaram sem aplicação.
  const limparOrfaos = (d, candidatos) => {
    const usados = new Set(d.apls.flatMap(a => a.talhoes));
    for (const t of candidatos) if (!usados.has(t)) delete d.areas[t];
  };
  const resumo = m => {
    const d = detalhes[m.id];
    const total = d.apls.reduce((s, a) => s + crTotalApl(a, d.areas), 0);
    return { ...m, talhoes: Object.keys(d.areas).length, toneladas: Math.round(total * 100) / 100,
             os: [...new Set(d.apls.map(a => a.os))].sort() };
  };
  return {
    sessao: async () => ({ id: 'demo' }),
    entrar: async () => {},
    sair: async () => {},
    eu: async () => ({ id: 'demo', nome: 'Usuário demonstração', admin: false, pode: true }),
    fazendas: async () => copia(CR_DEMO_FAZENDAS),
    mapas: async codFaz => copia(mapas.filter(m => m.cod_faz === Number(codFaz)).map(m => detalhes[m.id] ? resumo(m) : m)),
    criarMapa: async (codFaz, operacao) => {
      const id = proximoId++;
      const hoje = new Date();
      const pad = n => String(n).padStart(2, '0');
      mapas.push({ id, cod_faz: Number(codFaz), operacao, data: `${hoje.getFullYear()}-${pad(hoje.getMonth() + 1)}-${pad(hoje.getDate())}`,
                   os: [], talhoes: 0, toneladas: 0, alterado_por_nome: 'Usuário demonstração', alterado_em: hoje.toISOString() });
      return id;
    },
    excluirMapa: async id => { mapas = mapas.filter(m => m.id !== Number(id)); },
    talhoesFazenda: async () => copia(CR_DEMO_GEO),
    carregarMapa: async id => {
      const m = mapas.find(x => x.id === Number(id));
      const d = det(Number(id));
      return copia({ id: Number(id), cod_faz: m.cod_faz, operacao: m.operacao, data: m.data, areas: d.areas, apls: d.apls });
    },
    salvarArea: async (id, talhao, area) => {
      const d = det(Number(id));
      if (d.areas[talhao]) d.areas[talhao] = { area_ha: area, editada: true };
    },
    aplicar: async (id, p) => {
      const d = det(Number(id));
      for (const t of p.talhoes) if (!d.areas[t]) d.areas[t] = { area_ha: p.areas[t].area_ha, editada: !!p.areas[t].editada };
      const ordem = Math.max(0, ...d.apls.map(a => a.ordem)) + 1;
      d.apls.push({ id: proximaAplicacao++, tipo: p.tipo, calcario: p.calcario, dose: p.dose, dose_gesso: p.dose_gesso,
                    os: p.os, ordem, talhoes: [...p.talhoes] });
    },
    editarAplicacao: async (id, aplId, p) => {
      const d = det(Number(id));
      const a = d.apls.find(x => x.id === Number(aplId));
      const antes = [...a.talhoes];
      for (const t of p.talhoes) if (!d.areas[t]) d.areas[t] = { area_ha: p.areas[t].area_ha, editada: !!p.areas[t].editada };
      Object.assign(a, { dose: p.dose, dose_gesso: p.dose_gesso, os: p.os, talhoes: [...p.talhoes] });
      limparOrfaos(d, antes.filter(t => !p.talhoes.includes(t)));
    },
    excluirAplicacao: async (id, aplId) => {
      const d = det(Number(id));
      const a = d.apls.find(x => x.id === Number(aplId));
      d.apls = d.apls.filter(x => x.id !== Number(aplId));
      limparOrfaos(d, a ? a.talhoes : []);
    },
  };
})();
