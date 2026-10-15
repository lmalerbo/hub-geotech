// Corretivos: dados fictícios para o modo demonstração (file:// ou ?demo). Não há dado real aqui.
// Mesma forma que crApi.mapas() devolve (ver crResumoMapa em corretivos.js).
const CR_DEMO_FAZENDAS = [
  { cod_faz: 10231, nome: 'Fazenda Demo Alfa' },
  { cod_faz: 10455, nome: 'Fazenda Demo Beta' },
  { cod_faz: 10780, nome: 'Fazenda Demo Gama' },
];
const CR_DEMO_MAPAS = [
  { id: 1, cod_faz: 10231, operacao: 'subsolagem', data: '2026-10-08', os: ['4520', '4521'], talhoes: 6,
    toneladas: 84.5, alterado_por_nome: 'Carla Mendes', alterado_em: '2026-10-09T14:20:00' },
  { id: 2, cod_faz: 10231, operacao: 'arado', data: '2026-09-02', os: ['4498'], talhoes: 4,
    toneladas: 31.25, alterado_por_nome: 'Rafael Souza', alterado_em: '2026-09-03T09:10:00' },
  { id: 3, cod_faz: 10231, operacao: 'supergrade', data: '2026-06-20', os: ['4410', '4411', '4412'], talhoes: 9,
    toneladas: 112.04, alterado_por_nome: 'Carla Mendes', alterado_em: '2026-06-22T16:45:00' },
  { id: 4, cod_faz: 10455, operacao: 'supergrade', data: '2026-10-12', os: ['4530'], talhoes: 3,
    toneladas: 18.6, alterado_por_nome: 'Rafael Souza', alterado_em: '2026-10-12T11:05:00' },
];

// Mesma superfície de crApiReal (corretivos.js). Operações ainda não feitas lançam 'a fazer'.
const CR_API_DEMO = (() => {
  let mapas = CR_DEMO_MAPAS.map(m => ({ ...m, os: [...m.os] }));
  let proximoId = 100;
  const copia = v => JSON.parse(JSON.stringify(v));
  const aFazer = async () => { throw new Error('a fazer'); };
  return {
    sessao: async () => ({ id: 'demo' }),
    entrar: async () => {},
    sair: async () => {},
    eu: async () => ({ id: 'demo', nome: 'Usuário demonstração', admin: false, pode: true }),
    fazendas: async () => copia(CR_DEMO_FAZENDAS),
    mapas: async codFaz => copia(mapas.filter(m => m.cod_faz === Number(codFaz))),
    criarMapa: async (codFaz, operacao) => {
      const id = proximoId++;
      const hoje = new Date();
      const pad = n => String(n).padStart(2, '0');
      mapas.push({ id, cod_faz: Number(codFaz), operacao, data: `${hoje.getFullYear()}-${pad(hoje.getMonth() + 1)}-${pad(hoje.getDate())}`,
                   os: [], talhoes: 0, toneladas: 0, alterado_por_nome: 'Usuário demonstração', alterado_em: hoje.toISOString() });
      return id;
    },
    excluirMapa: async id => { mapas = mapas.filter(m => m.id !== Number(id)); },
    carregarMapa: aFazer,
    salvarAplicacao: aFazer,
    excluirAplicacao: aFazer,
    talhoesFazenda: aFazer,
  };
})();
