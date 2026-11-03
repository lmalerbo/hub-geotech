// Regras da Apresentação semanal, sem DOM (testadas em tests/app/apresentacao_calculo.test.js).
// Porte de agregar() do gerar.py de 28/10/2026.
// Regras portadas:
// - semana pela quinta-feira (a mais recente, incluindo hoje); corte = quinta - 1 dia
// - safra vira em 1º de abril (início vem de metas.inicio_safra, não da data de hoje)
// - BIS soma na frente
// - Sem Linhas não é concluído
// - preparo entregue = Ok; ciclo 25-26 fora
// - mês pela data de São Paulo (UTC-3)
// - drone sem área fica fora da soma e é listado em sem_dado
// - fornecedor fora da programação usa a meta
// `function` (não const) para ficar visível no contexto vm dos testes.

// Arredondamento igual ao round() do Python: meia vai para o par, sobre o valor exato do double.
function apRound(x, d) {
  d = d || 0;
  const neg = x < 0;
  const [ip, fp] = Math.abs(x).toFixed(60).split('.');
  let q = BigInt(ip + fp.slice(0, d));
  const resto = fp.slice(d);
  const primeiro = resto[0];
  const cauda = resto.slice(1);
  const exato = !/[1-9]/.test(cauda);
  if (primeiro > '5' || (primeiro === '5' && !exato) || (primeiro === '5' && exato && q % 2n === 1n)) q += 1n;
  const v = Number(q) / Math.pow(10, d);
  return neg ? -v : v;
}

// Igual a f"{x:g}" do Python (6 algarismos significativos, sem zeros à direita).
function apG(x) {
  if (x === 0) return '0';
  const ex = Math.abs(x).toExponential(5);
  const X = Number(ex.split('e')[1]);
  let s;
  if (X < -4 || X >= 6) {
    const [m, e] = ex.split('e');
    const mant = m.includes('.') ? m.replace(/\.?0+$/, '') : m;
    s = mant + 'e' + (Number(e) < 0 ? '-' : '+') + String(Math.abs(Number(e))).padStart(2, '0');
  } else {
    s = Math.abs(x).toFixed(5 - X);
    if (s.includes('.')) s = s.replace(/\.?0+$/, '');
  }
  return (x < 0 ? '-' : '') + s;
}

// n() do gerar.py: inteiro com ponto de milhar ('20.863').
function apN(x) {
  const r = apRound(x, 0);
  const s = String(Math.abs(r)).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return (r < 0 ? '-' : '') + s;
}

// pct() do gerar.py: percentual inteiro, 0 quando não há base.
function apPct(a, b) { return b ? apRound(100 * a / b, 0) : 0; }

// p1() do gerar.py: uma casa, sem zeros à direita ('12.5').
function apP1(x) { return apG(apRound(x, 1)); }

// Data local em YYYY-MM-DD (sem toISOString, que vira UTC).
function apIso(d) {
  const p = (v) => String(v).padStart(2, '0');
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate());
}

// Data de São Paulo (UTC-3, sem horário de verão) de um timestamp ISO, em YYYY-MM-DD.
function apDataSP(iso) {
  return new Date(Date.parse(iso) - 3 * 3600e3).toISOString().slice(0, 10);
}

// Semana da Apresentação: a quinta mais recente (incluindo hoje).
// Devolve { semana: 'S5M10', corte: '2026-10-28', quinta: '2026-10-29' }.
// N = quinta do mês ceil(dia/7); M = mês da quinta, sem zero à esquerda.
function apSemana(hoje) {
  const d = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
  const q = new Date(d.getFullYear(), d.getMonth(), d.getDate() - ((d.getDay() - 4 + 7) % 7));
  const c = new Date(q.getFullYear(), q.getMonth(), q.getDate() - 1);
  return {
    semana: 'S' + Math.ceil(q.getDate() / 7) + 'M' + (q.getMonth() + 1),
    corte: apIso(c),
    quinta: apIso(q),
  };
}

// agregar() do gerar.py. D = tabelas (mesmos nomes de L(nome)), com drone = linhas de hub.drone_projetos_v.
// metas = { meta_ervas_ha, meta_fornecedor_ha, meta_ha_dia, drone_pendente_ha, safra_atual, inicio_safra }.
// inicio_safra é 'YYYY-MM-DD' (comparado como texto). O gerar.py usava constantes e a data de hoje; aqui vêm de metas.
function apAgregar(D, metas) {
  const talhoes = new Map(D.talhoes.map((t) => [t.layer, t]));
  const A = {};

  // colheita
  const ct = D.colheita_talhoes;
  const st = {};
  const mes = {};
  const frente = {};
  const faz = new Map();
  const nomeFrente = (f) => {
    if (!f) return 'Indefinida';
    const m = /^(?:BIS - )?(\d+)$/.exec(f);
    if (m) return 'Frente ' + m[1];
    return f.startsWith('FOCA') ? 'FOCA' : 'Outras';
  };
  const soma = (obj, k, v) => { obj[k] = (obj[k] || 0) + v; };
  for (const r of ct) {
    const ha = r.area_ha || 0;
    soma(st, r.status, ha);
    const m = r.periodo_op == null ? 'None' : String(r.periodo_op);
    mes[m] = mes[m] || {};
    soma(mes[m], r.status, ha);
    const fr = nomeFrente(r.frente);
    frente[fr] = frente[fr] || {};
    soma(frente[fr], r.status, ha);
    if (!faz.has(r.cod_faz)) faz.set(r.cod_faz, []);
    faz.get(r.cod_faz).push(r.status);
  }
  const outras = [...new Set(ct.filter((r) => r.frente && nomeFrente(r.frente) === 'Outras').map((r) => r.frente))].sort();
  A.colheita = {
    total: Object.values(st).reduce((a, b) => a + b, 0),
    status: st, mes, frente,
    n_tal: ct.length,
    faz_tot: faz.size,
    faz_conc: [...faz.values()].filter((v) => v.every((s) => s === 'CONCLUIDO')).length,
    outras,
  };

  // plantio
  const pl = D.talhao_plantio.map((r) => {
    const t = talhoes.get(r.layer) || {};
    return Object.assign({}, r, { area_ha: t.area_ha || 0, cod_faz: t.cod_faz ?? null });
  });
  const pst = {};
  const pmes = {};
  for (const r of pl) {
    soma(pst, r.projeto, r.area_ha);
    const m = (r.mes_plantio || 'Indef').slice(0, 7);
    pmes[m] = pmes[m] || {};
    soma(pmes[m], r.projeto, r.area_ha);
  }
  const chavesMes = Object.keys(pmes).sort((a, b) => (a === 'Indef') - (b === 'Indef') || (a < b ? -1 : a > b ? 1 : 0));
  const mesPlantio = {};
  for (const k of chavesMes) mesPlantio[k] = pmes[k];
  A.plantio = {
    total: Object.values(pst).reduce((a, b) => a + b, 0),
    status: pst,
    mes: mesPlantio,
    n_tal: pl.length,
    n_faz: new Set(pl.map((r) => r.cod_faz)).size,
  };

  // preparo
  const etapas = D.etapas.filter((e) => e.modulo_id === 'preparo').sort((a, b) => a.ordem - b.ordem);
  const entregas = new Map(D.preparo_entregas.map((r) => [r.layer, r]));
  // O ciclo 25-26 (lançamento único pelo PLANAGRI) não entra no slide: estamos no ciclo 26-27.
  const prep = D.talhao_preparo.filter((r) => ((entregas.get(r.layer) || {}).origem) !== 'ciclo_25_26');
  let fora2526 = 0;
  for (const [l, r] of entregas) {
    if (r.origem === 'ciclo_25_26') fora2526 += (talhoes.get(l) || {}).area_ha || 0;
  }
  const porEtapa = {};
  for (const e of etapas) porEtapa[e.nome] = [new Set(), 0];
  porEtapa.Entregue = [new Set(), 0];
  const prmes = {};
  let total = 0;
  for (const r of prep) {
    const t = talhoes.get(r.layer);
    if (!t) continue;
    const ha = t.area_ha || 0;
    total += ha;
    const nome = r.etapa === 'Ok' ? 'Entregue' : r.etapa;
    porEtapa[nome][0].add(t.cod_faz);
    porEtapa[nome][1] += ha;
    const en = entregas.get(r.layer);
    if (en && en.entregue_em) {   // entregue_em nulo fica fora do gráfico mensal
      const dataSP = apDataSP(en.entregue_em);   // mês pelo calendário de São Paulo, não pela data UTC
      if (en.origem === 'lancamento_inicial') {
        soma(prmes, 'Lançamento inicial (jun/26)', ha);
      } else if (dataSP >= metas.inicio_safra) {   // gráfico mensal só mostra o ciclo atual
        soma(prmes, dataSP.slice(0, 7), ha);
      }
    }
  }
  const etapaObj = {};
  for (const k of Object.keys(porEtapa)) etapaObj[k] = [porEtapa[k][0].size, porEtapa[k][1]];
  const nFaz = new Set(prep.filter((r) => talhoes.has(r.layer)).map((r) => talhoes.get(r.layer).cod_faz)).size;
  const chavesPrep = Object.keys(prmes).sort((a, b) => {
    const la = a.startsWith('Lan') ? 0 : 1;
    const lb = b.startsWith('Lan') ? 0 : 1;
    if (la !== lb) return la - lb;
    return a < b ? -1 : a > b ? 1 : 0;
  });
  const mesPrep = {};
  for (const k of chavesPrep) mesPrep[k] = prmes[k];
  A.preparo = { total, n_faz: nFaz, n_tal: prep.length, etapa: etapaObj, fora_25_26: fora2526, mes: mesPrep };

  // drone: uma linha por projeto (view hub.drone_projetos_v). Safra sem dado vira '?'.
  // Linhas com área null vão para sem_dado e não somam; o arredondamento é por (documento, safra).
  const porDocSafra = new Map();
  const nProj = {};
  const fazSafra = new Map();
  const fazBase = new Set();
  const semDado = [];
  for (const r of D.drone) {
    const s = r.safra ?? '?';
    nProj[s] = (nProj[s] || 0) + 1;
    if (!fazSafra.has(s)) fazSafra.set(s, new Set());
    fazSafra.get(s).add(r.cod_faz);
    fazBase.add(r.cod_faz);
    if (r.area_aplicacao_ha == null) {
      semDado.push({ cod_faz: r.cod_faz, documento: r.documento, revisao_id: r.revisao_id });
      continue;
    }
    const chave = JSON.stringify([r.documento, s]);
    porDocSafra.set(chave, { s, v: (porDocSafra.get(chave) || { v: 0 }).v + r.area_aplicacao_ha });
  }
  const porSafra = {};
  for (const { s, v } of porDocSafra.values()) {
    soma(porSafra, s, apRound(v, 0));
  }
  A.drone = {
    por_safra: porSafra,
    n_proj: nProj,
    faz_safra: Object.fromEntries([...fazSafra].map(([k, v]) => [k, v.size])),
    n_base: D.drone.length,
    faz_base: fazBase.size,
  };
  A.drone.sem_dado = semDado;

  A.voos = D.voos;
  return A;
}

// voos_numeros() do gerar.py: [realizado, previsto, fora, fornecedor].
function apVoosNumeros(A, metas) {
  const V = A.voos;
  const r = V.resumo;
  const forn = V.porTipo.find((t) => t.tipo === 'Falhas Plantio Forn.') || { realizadoHa: 0, aVoarHa: 0 };
  const fora = Math.max(0, metas.meta_fornecedor_ha - forn.realizadoHa - forn.aVoarHa);
  return [r.realizadoHa, r.aVoarHa + fora, fora, forn];
}
