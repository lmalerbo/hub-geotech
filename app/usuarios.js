// Regras da tela Usuários, sem DOM (testadas em tests/app/usuarios_puro.test.js).
// Nível por módulo: leitura | solicitante (só Drone) | editor; sem chave = sem acesso.
// GeoMap: o acesso individual por mapa soma ao dos grupos e só acrescenta.
const USR_MODULOS_HUB = [['plantio', 'Plantio'], ['preparo', 'Preparo'], ['colheita', 'Colheita'], ['drone', 'Drone']];
const USR_NIVEIS = { leitura: 'Leitura', solicitante: 'Solicitante', editor: 'Editor' };
const USR_FILTROS = [['todos', 'Todos'], ['plantio', 'Plantio'], ['preparo', 'Preparo'], ['colheita', 'Colheita'],
  ['drone', 'Drone'], ['geomap', 'GeoMap'], ['provisoria', 'Senha provisória']];
const USR_MAPA_ORDEM = { nada: 0, ver: 1, editar: 2 };
const USR_MAPA_ROTULO = { nada: '—', ver: 'Ver', editar: 'Ver e editar' };

function usrPelosGrupos(mapa, grupoIds) {
  let n = 'nada';
  for (const g of mapa.grupos || []) {
    if (!grupoIds.includes(g.grupoId)) continue;
    const v = g.podeEditar ? 'editar' : 'ver';
    if (USR_MAPA_ORDEM[v] > USR_MAPA_ORDEM[n]) n = v;
  }
  return n;
}
function usrNivelFinal(pelosGrupos, individual) {
  return USR_MAPA_ORDEM[individual] > USR_MAPA_ORDEM[pelosGrupos] ? individual : pelosGrupos;
}
function usrProximoIndividual(n) { return { nada: 'ver', ver: 'editar', editar: 'nada' }[n] || 'ver'; }
function usrMapasDoBanco(mapas) {
  const r = {};
  for (const m of mapas || []) r[m.mapa_id] = m.pode_editar ? 'editar' : 'ver';
  return r;
}
function usrMapasParaBanco(tela) {
  return Object.entries(tela || {}).filter(([, n]) => n !== 'nada')
    .map(([id, n]) => ({ mapa_id: Number(id), pode_editar: n === 'editar' }));
}
function usrPlural(n, um, varios) { return n + ' ' + (n === 1 ? um : varios); }
function usrResumo(a) {
  if (a.bloqueado) return 'Sem acesso — bloqueado';
  const niveis = a.niveis || {}, partes = [];
  if (a.admin) partes.push('Admin do Hub');
  for (const [id, nome] of USR_MODULOS_HUB) {
    const n = niveis[id];
    if (n) partes.push(n === 'leitura' ? nome : `${nome} (${USR_NIVEIS[n].toLowerCase()})`);
  }
  if (a.geomap_ativo) {
    const g = (a.geomap_grupos || []).length, m = (a.geomap_mapas || []).length;
    const det = [g ? usrPlural(g, 'grupo', 'grupos') : '', m ? usrPlural(m, 'mapa', 'mapas') : ''].filter(Boolean).join(' + ');
    partes.push('GeoMap' + (a.geomap_admin ? ' (admin)' : '') + (det ? ': ' + det : ''));
  }
  if (niveis.corretivos) partes.push('Mapas de aplicação');
  return partes.join(' · ') || 'Sem acesso';
}
function usrSituacao(a) {
  if (!a.conta_criada) return ['espera', 'Sem conta'];
  if (a.bloqueado) return ['erro', 'Bloqueado'];
  if (a.precisa_trocar_senha) return ['espera', 'Senha provisória'];
  if (!a.ultimo_login) return ['espera', 'Ainda não entrou'];
  return ['ok', 'Acesso ativo'];
}
function usrFiltrar(lista, filtro, busca) {
  const q = String(busca || '').trim().toLowerCase();
  return lista.filter((a) => {
    if (q && !(String(a.nome || '').toLowerCase().includes(q) || String(a.email || '').toLowerCase().includes(q))) return false;
    if (filtro === 'geomap') return !!a.geomap_ativo;
    if (filtro === 'provisoria') return !!a.precisa_trocar_senha;
    if (filtro && filtro !== 'todos') return !!(a.niveis || {})[filtro];
    return true;
  });
}
