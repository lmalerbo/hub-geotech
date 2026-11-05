// Paralelismo: Pendentes, Rodadas e Frotas — lógica sem DOM (testada com node --test).
// Usa parFormatarPct (paralelismo-puro.js) e PAR_FORA_TALHAO_MAX (paralelismo-previa.js).

const PAR_AMOSTRA_MIN = 25;
const PAR_RECALCULOS_MAX = 2;

// partes[].url e amostras_url vêm do banco, gravados por quem envia: são dado não confiável. Só vira link o que é
// https do GitHub, sem credenciais, espaço, aspas ou sinais de marcação; o resto aparece como texto.
function parUrlSegura(url) {
  if (typeof url !== 'string' || !url || /[\s"'<>`\\]/.test(url)) return null;
  let u;
  try { u = new URL(url); } catch (e) { return null; }
  if (u.protocol !== 'https:' || u.hostname !== 'github.com' || u.username || u.password) return null;
  return url;
}

// Erro do banco "recalculo_necessario:cana/10001,torta/10002" -> [{operacao, cod_faz}]
function parRecalculoNecessario(erro) {
  const m = /recalculo_necessario:([\w/,]+)/.exec(String((erro && erro.message) || ''));
  if (!m) return null;
  return m[1].split(',').filter(Boolean).map((x) => {
    const [operacao, cod] = x.split('/');
    return { operacao, cod_faz: Number(cod) };
  });
}

function parPreviaDoBanco(analises, vigentes) {
  let amostras = 0, aderentes = 0;
  const fazendas = analises.map((a) => {
    const vig = vigentes[`${a.operacao}|${a.cod_faz}`] || null;
    const talhoes = (a.paralelismo_talhoes || []).slice().sort((x, y) => x.talhao_num - y.talhao_num).map((t) => ({
      ...t, insuficiente: t.amostras < PAR_AMOSTRA_MIN, pctTxt: parFormatarPct(t.aderentes, t.amostras),
    }));
    const avisos = [];
    if (a.pll_total && a.fora_talhao / a.pll_total > PAR_FORA_TALHAO_MAX) {
      avisos.push({ codigo: 'fora_talhao_alto', texto: `${parFormatarPct(a.fora_talhao, a.pll_total)} das amostras caíram fora de qualquer talhão; confira a base de talhões.` });
    }
    const insuf = talhoes.filter((t) => t.insuficiente).map((t) => t.talhao_num);
    if (insuf.length) avisos.push({ codigo: 'insuficiente', texto: `Amostra insuficiente nos talhões ${insuf.join(', ')} (menos de ${PAR_AMOSTRA_MIN}).` });
    amostras += a.amostras;
    aderentes += a.aderentes;
    const novo = a.amostras ? a.aderentes / a.amostras : 0;
    let deltaTxt = null;
    if (vig && vig.amostras && a.amostras) {
      const d = Math.round((novo - vig.aderentes / vig.amostras) * 10000) / 100;
      deltaTxt = `${d >= 0 ? '+' : '−'}${Math.abs(d).toFixed(2).replace('.', ',')} p.p.`;
    }
    return {
      operacao: a.operacao, cod_faz: a.cod_faz, avisos, amostras: a.amostras, aderentes: a.aderentes, acima: a.acima, abaixo: a.abaixo,
      foraTalhao: a.fora_talhao, pllTotal: a.pll_total, mes: a.mes, pctTxt: parFormatarPct(a.aderentes, a.amostras),
      vigentePctTxt: vig ? parFormatarPct(vig.aderentes, vig.amostras) : null, deltaTxt, talhoes,
      frotas: [...new Set(talhoes.flatMap((t) => t.frotas || []))],
      amostrasUrl: parUrlSegura(a.amostras_url),
    };
  });
  return { fazendas, total: { amostras, aderentes, pctTxt: parFormatarPct(aderentes, amostras) } };
}

// linha = rodada do PostgREST com paralelismo_analises(paralelismo_talhoes) e paralelismo_arquivos; nomes = {id: nome}.
function parRodadaDoBanco(linha, nomes, vigentes) {
  const nome = (id) => (id && nomes[id]) || '—';
  const analises = (linha.paralelismo_analises || []).slice().sort((a, b) => a.operacao.localeCompare(b.operacao) || a.cod_faz - b.cod_faz);
  const previa = parPreviaDoBanco(analises, vigentes || {});
  return {
    id: linha.id, descricao: linha.descricao || '', status: linha.status, tag: linha.release_tag || null,
    criadoPor: nome(linha.criado_por), validadoPor: nome(linha.validado_por), criadoEm: linha.criado_em, validadoEm: linha.validado_em,
    motivo: linha.motivo_recusa || '',
    partes: (linha.partes || []).map((p) => {
      const url = parUrlSegura(p.url);
      return { nome: String(p.nome ?? ''), bytes: Number(p.bytes) || 0, url, urlInvalida: !url };
    }),
    fazendas: previa.fazendas.map((f) => ({ operacao: f.operacao, cod_faz: f.cod_faz, amostrasUrl: f.amostrasUrl })),
    tratores: new Set((linha.paralelismo_arquivos || []).map((a) => a.serie).filter(Boolean)).size,
    previa,
  };
}

// results = fazendas do Worker (operacao, cod_faz, analise); baseIds = {'<op>|<cod>': id da vigente usada}.
// amostras_url vai nulo: o shapefile antigo ficaria desatualizado e o Worker não aceita parte nova de rodada já enviada.
function parMontarRecalculo(results, baseIds) {
  return results.map((r) => {
    const a = r.analise;
    return {
      operacao: r.operacao, cod_faz: r.cod_faz, base_analise_id: baseIds[`${r.operacao}|${r.cod_faz}`] ?? null, mes: a.mes ?? null,
      amostras: a.amostras, aderentes: a.aderentes, acima: a.acima, abaixo: a.abaixo, fora_talhao: a.fora_talhao,
      pll_total: a.pll_total, pll_aderentes: a.pll_aderentes, amostras_url: null,
      talhoes: a.talhoes.map(({ talhao_num, amostras, aderentes, acima, abaixo, media_m, frotas }) => ({ talhao_num, amostras, aderentes, acima, abaixo, media_m, frotas })),
    };
  });
}

// deps: publicar(id, recalculo|null), buscarBase(op, cod, rodadaId) -> {analise_id, linhas, talhoes},
// recalcular(entrada[]) -> fazendas do Worker, confirmar(fazendas) -> Promise<boolean>.
async function parPublicarComRecalculo(rodadaId, deps) {
  try {
    await deps.publicar(rodadaId, null);
    return { publicada: true, recalculou: false };
  } catch (e) {
    let lista = parRecalculoNecessario(e);
    if (!lista) throw e;
    for (let tentativa = 1; ; tentativa++) {
      const bases = [];
      for (const f of lista) bases.push({ f, base: await deps.buscarBase(f.operacao, f.cod_faz, rodadaId) });
      const entrada = bases.map(({ f, base }) => ({
        operacao: f.operacao, cod_faz: f.cod_faz, base_analise_id: base.analise_id ?? null, vigentes: base.linhas || [], talhoes: base.talhoes, grupos: [],
      }));
      const results = await deps.recalcular(entrada);
      if (!(await deps.confirmar(results))) return { cancelado: true };
      const baseIds = Object.fromEntries(entrada.map((x) => [`${x.operacao}|${x.cod_faz}`, x.base_analise_id]));
      try {
        await deps.publicar(rodadaId, parMontarRecalculo(results, baseIds));
        return { publicada: true, recalculou: true };
      } catch (e2) {
        lista = parRecalculoNecessario(e2);   // outra publicação mudou a vigente no meio do caminho
        if (!lista || tentativa >= PAR_RECALCULOS_MAX) throw e2;
      }
    }
  }
}

function parTextoErroGestao(e) {
  const m = String((e && e.message) || e || '');
  let x;
  if ((x = /exclua_antes_rodada_mais_nova:([\d,]+)/.exec(m))) return `Exclua antes a rodada mais nova da(s) fazenda(s) ${x[1].split(',').join(', ')}.`;
  if ((x = /rodada_pendente_depende:([\d,]+)/.exec(m))) return `A(s) rodada(s) pendente(s) ${x[1].split(',').join(', ')} dependem desta; publique ou recuse antes.`;
  if (/rodada_nao_pendente/.test(m)) return 'Esta rodada já foi decidida por outra pessoa. Atualize a lista.';
  if (/rodada_nao_publicada/.test(m)) return 'Só rodadas publicadas podem ser excluídas.';
  if (/recalculo_necessario|recalculo_sem_analise/.test(m)) return 'Os dados das fazendas mudaram durante a publicação. Tente de novo.';
  if (/informe o motivo/i.test(m)) return 'Informe o motivo da recusa.';
  if (/Sem permissão|Só o editor|Só administradores|permission denied|403/.test(m)) return 'Seu nível não permite esta ação.';
  if (/Sessão expirada|JWT expired|jwt/i.test(m)) return 'Sua sessão expirou. Entre de novo no Hub e tente de novo.';
  if (/Failed to fetch|NetworkError|Load failed/i.test(m)) return 'Sem conexão com o Hub. Nada foi alterado; tente de novo.';
  return 'Não foi possível concluir. Tente de novo.';
}

function parValidarFrota(f) {
  const t = (v) => String(v ?? '').trim();
  const valor = {
    serie: t(f.serie), frota: t(f.frota), operacao: t(f.operacao), tipo: t(f.tipo),
    nomes_antigos: t(f.nomes_antigos) || null, observacao: t(f.observacao) || null,
  };
  let erro = null;
  if (!valor.serie) erro = 'Informe a série do trator.';
  else if (!valor.frota) erro = 'Informe a frota.';
  else if (!['cana', 'torta'].includes(valor.operacao)) erro = 'Escolha a operação: cana ou torta.';
  else if (!['propria', 'prestador'].includes(valor.tipo)) erro = 'Escolha o tipo: própria ou prestador.';
  return { erro, valor };
}
