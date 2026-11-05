// Paralelismo: prévia, avisos, carga do envio e envio em partes. Sem DOM (testado com node --test).
// Usa parRegistrosDoGrupo, parPartes, parManifestoCsv, parFormatarPct e parExtensao de paralelismo-puro.js.

const PAR_FORA_TALHAO_MAX = 0.05;

const PAR_MOTIVOS_PULADO = {
  ilegivel: 'arquivo corrompido ou cortado; foi pulado',
  sem_frota: 'série sem frota cadastrada; foi pulado',
  sem_fazenda: 'sem fazenda identificada no nome gravado no monitor; foi pulado',
  sem_fdd: '.fdl sem o .fdd ao lado; foi pulado',
  fdd_sem_fdl: '.fdd sem o .fdl novo ao lado; foi pulado',
};

// Só o que foi de fato analisado vira "já analisado" para as próximas rodadas: arquivo pulado não pode ser
// registrado, e o .fdd par de um .fdl pulado sai junto.
function parRegistrosAceitos(grupos, resultado) {
  const pulados = new Set((resultado.pulados || []).map((p) => p.caminho));
  const semExt = (c) => parNormalizar(c).replace(/\.[^./]+$/, '').toLowerCase();
  const fdlsPulados = new Set((resultado.pulados || []).filter((p) => parExtensao(p.caminho) === 'fdl').map((p) => semExt(p.caminho)));
  return grupos.flatMap((g) => parRegistrosDoGrupo({
    ...g,
    arquivos: g.arquivos.filter((a) => !pulados.has(a.caminho) && !(parExtensao(a.caminho) === 'fdd' && fdlsPulados.has(semExt(a.caminho)))),
  }));
}

const parPct = (n, total) => (total ? n / total : 0);

function parDelta(novo, antigo) {
  const d = Math.round((novo - antigo) * 10000) / 100;
  return `${d >= 0 ? '+' : '−'}${Math.abs(d).toFixed(2).replace('.', ',')} p.p.`;
}

// vigentes: {'<operacao>|<cod_faz>': {amostras, aderentes}} da análise vigente de cada fazenda (ou ausente se nova).
function parPrevia(resultado, vigentes) {
  let amostras = 0, aderentes = 0;
  const fazendas = resultado.fazendas.map((f) => {
    const a = f.analise;
    const vig = vigentes[`${f.operacao}|${f.cod_faz}`] || null;
    const avisos = [];
    const enviavel = f.linhas_novas.length > 0;
    if (!enviavel) avisos.push({ codigo: 'sem_linhas_novas', texto: 'Nenhuma linha nova nesta fazenda; ela não será enviada.' });
    if (a.pll_total && a.fora_talhao / a.pll_total > PAR_FORA_TALHAO_MAX) {
      avisos.push({ codigo: 'fora_talhao_alto', texto: `${parFormatarPct(a.fora_talhao, a.pll_total)} das amostras caíram fora de qualquer talhão; confira a base de talhões.` });
    }
    const insuf = a.talhoes.filter((t) => t.insuficiente).map((t) => t.talhao_num);
    if (insuf.length) avisos.push({ codigo: 'insuficiente', texto: `Amostra insuficiente nos talhões ${insuf.join(', ')} (menos de 25).` });
    const semTrab = (f.frotas_leitura || []).filter((x) => x.sem_trabalho).map((x) => x.frota);
    if (semTrab.length) avisos.push({ codigo: 'sem_trabalho', texto: `Frota ${semTrab.join(', ')}: trilha longa com o implemento quase sempre desligado; pode faltar trabalho registrado.` });
    if (enviavel) { amostras += a.amostras; aderentes += a.aderentes; }
    return {
      operacao: f.operacao, cod_faz: f.cod_faz, enviavel, avisos,
      amostras: a.amostras, aderentes: a.aderentes, acima: a.acima, abaixo: a.abaixo,
      foraTalhao: a.fora_talhao, pllTotal: a.pll_total, mes: a.mes,
      pctTxt: parFormatarPct(a.aderentes, a.amostras),
      vigentePctTxt: vig ? parFormatarPct(vig.aderentes, vig.amostras) : null,
      deltaTxt: vig && vig.amostras && a.amostras ? parDelta(parPct(a.aderentes, a.amostras), parPct(vig.aderentes, vig.amostras)) : null,
      talhoes: a.talhoes.map((t) => ({ ...t, pctTxt: parFormatarPct(t.aderentes, t.amostras) })),
      frotas: a.frotas.map((x) => ({ ...x, pctTxt: parFormatarPct(x.aderentes, x.amostras) })),
    };
  });
  return {
    fazendas, enviaveis: fazendas.filter((f) => f.enviavel).length,
    total: { amostras, aderentes, pctTxt: parFormatarPct(aderentes, amostras) },
  };
}

function parAvisosItem(resultado, falhasCopia) {
  const avisos = [];
  const porMotivo = new Map();
  for (const p of resultado.pulados || []) {
    if (!porMotivo.has(p.motivo)) porMotivo.set(p.motivo, []);
    porMotivo.get(p.motivo).push(p.caminho);
  }
  for (const [motivo, arquivos] of porMotivo) {
    avisos.push({ codigo: `pulados_${motivo}`, texto: `${arquivos.length} ${arquivos.length === 1 ? 'arquivo' : 'arquivos'}: ${PAR_MOTIVOS_PULADO[motivo] || 'foi pulado'}.`, arquivos });
  }
  const parciais = (resultado.parciais || []).map((p) => p.caminho);
  if (parciais.length) avisos.push({ codigo: 'parciais', texto: `${parciais.length} ${parciais.length === 1 ? 'arquivo termina cortado' : 'arquivos terminam cortados'}; os pontos legíveis foram usados.`, arquivos: parciais });
  const falhas = (falhasCopia || []).map((f) => f.caminho);
  if (falhas.length) avisos.push({ codigo: 'nao_copiado', texto: `${falhas.length} ${falhas.length === 1 ? 'arquivo não pôde' : 'arquivos não puderam'} ser copiado(s) do pen-drive e ficaram de fora.`, arquivos: falhas });
  return avisos;
}

function parNomeParte(rodadaId, n) { return `p${rodadaId}-${String(n).padStart(2, '0')}.zip`; }
function parNomeAmostras(operacao, codFaz) { return `amostras-${operacao}-${codFaz}.zip`; }

function parPayloadEnvio({ rodadaId, descricao, registros, partes, resultado, urlsAmostras }) {
  const fazendas = resultado.fazendas.filter((f) => f.linhas_novas.length > 0);
  return {
    rodada_id: rodadaId,
    descricao: descricao || null,
    partes: partes.map((p) => ({ nome: p.nome, url: p.url, bytes: p.bytes })),
    arquivos: registros,
    linhas: fazendas.flatMap((f) => f.linhas_novas.map((l) => ({ operacao: f.operacao, cod_faz: f.cod_faz, frota: l.frota, data: l.data, coords: l.coords }))),
    analises: fazendas.map((f) => {
      const a = f.analise;
      return {
        operacao: f.operacao, cod_faz: f.cod_faz, base_analise_id: f.base_analise_id ?? null, mes: a.mes ?? null,
        amostras: a.amostras, aderentes: a.aderentes, acima: a.acima, abaixo: a.abaixo,
        fora_talhao: a.fora_talhao, pll_total: a.pll_total, pll_aderentes: a.pll_aderentes,
        amostras_url: (urlsAmostras || {})[`${f.operacao}|${f.cod_faz}`] || null,
        talhoes: a.talhoes.map(({ talhao_num, amostras, aderentes, acima, abaixo, media_m, frotas }) => ({ talhao_num, amostras, aderentes, acima, abaixo, media_m, frotas })),
      };
    }),
  };
}

// Textos da spec §10 e dos erros do banco. Em todo erro de envio nada foi gravado.
function parTextoErro(e) {
  const m = String((e && e.message) || e || '');
  if (/arquivo_ja_analisado|arquivo_repetido_no_envio/.test(m)) return 'Alguns arquivos já foram analisados em outra rodada; escolha o pen-drive de novo. Nada foi gravado.';
  if (/rodada_ja_enviada/.test(m)) return 'Esta rodada já foi enviada. Nada mais foi gravado.';
  if (/Sessão expirada|JWT expired|jwt/i.test(m)) return 'Sua sessão expirou. Entre de novo no Hub e tente de novo; a cópia do pen-drive continua neste navegador. Nada foi gravado.';
  if (/maior que 95/.test(m)) return 'Uma parte passou do limite de 95 MB e não pôde ser enviada. Nada foi gravado.';
  if (/Sem permissão|permission denied|403/.test(m)) return 'Seu nível não permite enviar ao Paralelismo. Nada foi gravado.';
  if (/Failed to fetch|NetworkError|Load failed/i.test(m)) return 'Sem conexão com o Hub. Nada foi gravado; tente de novo.';
  if (/Nada novo/.test(m)) return m;
  return 'Não foi possível enviar para validação. Nada foi gravado; tente de novo.';
}

// deps: preparar(id|null) -> id; zip(arquivos[{caminho, opfs, bytes}]) -> Blob; subir(nome, conteudo, id) -> {url, bytes};
// enviar(carga) -> id. Falhou em qualquer ponto = nada gravado (o banco só é tocado no fim); o id fica para "Tentar de novo".
// entrada = {rodadaId, todos (copiados), grupos (conferência com a frota final), resultado, descricao}.
async function parEnviarItem(entrada, deps) {
  const { resultado } = entrada;
  if (!resultado.fazendas.some((f) => f.linhas_novas.length > 0)) throw new Error('Nada novo para enviar: nenhuma fazenda tem linhas novas.');
  let rodadaId = entrada.rodadaId ?? null;
  try {
    rodadaId = await deps.preparar(rodadaId);
    const registros = parRegistrosAceitos(entrada.grupos, resultado);
    const aceitos = new Set(registros.map((r) => r.caminho));
    const arquivos = entrada.todos.filter((a) => aceitos.has(a.caminho)).map((a) => ({ caminho: a.caminho, opfs: a.opfs, bytes: a.bytes }));
    const partes = [];
    for (const [i, parte] of parPartes(arquivos).entries()) {
      const nome = parNomeParte(rodadaId, i + 1);
      const r = await deps.subir(nome, await deps.zip(parte), rodadaId);
      partes.push({ nome, url: r.url, bytes: r.bytes });
    }
    await deps.subir('manifesto.csv', parManifestoCsv(registros), rodadaId);
    const urlsAmostras = {};
    for (const f of resultado.fazendas.filter((x) => x.linhas_novas.length > 0)) {
      const r = await deps.subir(parNomeAmostras(f.operacao, f.cod_faz), f.shapefile, rodadaId);
      urlsAmostras[`${f.operacao}|${f.cod_faz}`] = r.url;
    }
    await deps.enviar(parPayloadEnvio({ rodadaId, descricao: entrada.descricao, registros, partes, resultado, urlsAmostras }));
    return { rodadaId, partes };
  } catch (e) {
    throw Object.assign(new Error(parTextoErro(e)), { rodadaId, causa: e });
  }
}
