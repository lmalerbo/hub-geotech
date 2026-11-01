// Apresentação semanal: leitura dos dados (Supabase do hub e API de voos do GeoMap). Sem DOM.
// `function` e `var` (não const/let) para ficarem visíveis no contexto vm dos testes.
// Testado em tests/app/apresentacao_dados.test.js.

var AP_TABELAS_HUB = ['talhoes', 'colheita_talhoes', 'talhao_plantio', 'talhao_preparo', 'etapas', 'preparo_entregas'];
var AP_VOOS_LIMITE_MS = 180000;

// Lê a tabela inteira em páginas de 1000 linhas.
async function apLerTudo(cliente, tabela) {
  const tamanho = 1000;
  const linhas = [];
  for (let a = 0; ; a += tamanho) {
    let consulta = cliente.from(tabela).select('*');
    if (tabela === 'preparo_entregas') consulta = consulta.order('layer');
    const { data, error } = await consulta.range(a, a + tamanho - 1);
    if (error) throw new Error(tabela + ': ' + error.message);
    linhas.push(...data);
    if (data.length < tamanho) break;
  }
  return linhas;
}

// Converte as linhas de hub.apresentacao_metas em um objeto de metas.
function apMetasDeLinhas(linhas) {
  const valores = {};
  for (const l of linhas) valores[l.chave] = l.valor;
  return {
    meta_ervas_ha: Number(valores.meta_ervas_ha),
    meta_fornecedor_ha: Number(valores.meta_fornecedor_ha),
    meta_ha_dia: Number(valores.meta_ha_dia),
    drone_pendente_ha: Number(valores.drone_pendente_ha),
    safra_atual: valores.safra_atual,
    inicio_safra: valores.inicio_safra,
  };
}

// Pede os indicadores de voos ao worker do GeoMap, com limite de 3 minutos.
async function apBuscarVoos(cliente, corte, metas, workerUrl, buscar) {
  buscar = buscar || fetch;
  const sessao = (await cliente.auth.getSession()).data.session;
  const token = sessao.access_token;
  const controle = new AbortController();
  const timer = setTimeout(() => controle.abort(), AP_VOOS_LIMITE_MS);
  try {
    const url = workerUrl + '/voos-indicadores?de=' + metas.inicio_safra + '&ate=' + corte;
    const r = await buscar(url, { headers: { Authorization: 'Bearer ' + token }, signal: controle.signal });
    if (!r.ok) {
      let erro = null;
      try { erro = (await r.json()).erro; } catch (e) { erro = null; }
      throw new Error(erro || ('Worker respondeu ' + r.status));
    }
    return await r.json();
  } catch (e) {
    if (e && e.name === 'AbortError') throw new Error('A API de voos do GeoMap não respondeu em 3 minutos');
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

// Dispara as três leituras em paralelo e devolve as promessas.
function apFontes(cliente, corte, metas, workerUrl, buscar) {
  const hub = Promise.all(AP_TABELAS_HUB.map((t) => apLerTudo(cliente, t))).then((listas) => {
    const obj = {};
    AP_TABELAS_HUB.forEach((t, i) => { obj[t] = listas[i]; });
    return obj;
  });
  return {
    hub,
    drone: apLerTudo(cliente, 'drone_projetos_v'),
    voos: apBuscarVoos(cliente, corte, metas, workerUrl, buscar),
  };
}
