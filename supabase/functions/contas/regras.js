// Regras puras da função "contas" — JavaScript sem dependências, para o Deno da
// função e o Node dos testes (tests/contas/regras_contas.test.mjs) usarem o mesmo código.

/** A conta fica liberada? (algum nível em módulo do Hub, GeoMap ativo ou admin). Sem acesso = conta bloqueada. */
export function temAcesso(a) {
  return Object.keys(a?.niveis || {}).length > 0 || !!a?.geomap_ativo || !!a?.admin;
}

/** hub.acessos.geomap_mapas ([{mapa_id, pode_editar}]) → corpo do GeoMap ([{mapaId, podeEditar}]). */
export function mapasParaGeomap(mapas) {
  return (mapas || []).map((m) => ({ mapaId: Number(m.mapa_id), podeEditar: m.pode_editar === true }));
}
