// Regras puras da função "contas" — JavaScript sem dependências, para o Deno da
// função e o Node dos testes (tests/contas/regras_contas.test.mjs) usarem o mesmo código.

/** A conta fica liberada? (algum módulo do Hub, GeoMap ativo ou admin). Sem acesso = conta bloqueada. */
export function temAcesso(a) {
  return (a?.modulos || []).length > 0 || !!a?.geomap_ativo || !!a?.admin;
}
