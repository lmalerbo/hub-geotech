// Paralelismo: regras puras da página (sem DOM). Testes: tests/app/paralelismo_puro.test.js

const PAR_PARTE_MAX = 90 * 1024 * 1024;
const PAR_REV = /(?<!\d)([1-9]\d{4})Rev(\d+)/i;
const PAR_COD_ISOLADO = /(?<!\d)[1-9]\d{4}(?!\d)/;

function parNormalizar(caminho) {
  return String(caminho ?? '').replace(/\\/g, '/');
}

function parExtensao(caminho) {
  const m = /\.([^./]+)$/.exec(parNormalizar(caminho));
  return m ? m[1].toLowerCase() : '';
}

function parDataValida(a, m, d) {
  const dt = new Date(Date.UTC(+a, +m - 1, +d));
  return dt.getUTCFullYear() === +a && dt.getUTCMonth() === +m - 1 && dt.getUTCDate() === +d ? `${a}-${m}-${d}` : null;
}

function parEhDigito(b) {
  return b >= 0x30 && b <= 0x39;
}

// O arquivo tem centenas de MB: procura BM\d{4}[A-Z]\d{6} nos bytes, sem virar string.
function parSerieMaisFrequente(bytes) {
  const contagem = new Map();
  for (let i = 0; i + 13 <= bytes.length; i++) {
    if (bytes[i] !== 0x42 || bytes[i + 1] !== 0x4D) continue;
    let ok = bytes[i + 6] >= 0x41 && bytes[i + 6] <= 0x5A;
    for (let j = 2; ok && j < 13; j++) if (j !== 6) ok = parEhDigito(bytes[i + j]);
    if (!ok) continue;
    const serie = String.fromCharCode(...bytes.subarray(i, i + 13));
    contagem.set(serie, (contagem.get(serie) || 0) + 1);
  }
  let melhor = null, maior = 0;
  for (const [serie, n] of contagem) if (n > maior) { melhor = serie; maior = n; }
  return melhor;
}

// Só o número isolado; o par número+RevN é procurado antes por quem chama.
function parCodIsolado(nome) {
  const m = PAR_COD_ISOLADO.exec(nome);
  return m ? Number(m[0]) : null;
}

function parIdentificarJdl(nomeRel, bytes) {
  const segmentos = parNormalizar(nomeRel).split('/');
  const arquivo = segmentos.pop();
  const pastas = segmentos.filter(Boolean);
  let cod_faz = null, revisao = null, fazenda_monitor = pastas[pastas.length - 1] || '';
  let achou = false;
  for (let i = pastas.length - 1; i >= 0 && !achou; i--) {
    const m = PAR_REV.exec(pastas[i]);
    if (m) {
      cod_faz = Number(m[1]);
      revisao = Number(m[2]);
      fazenda_monitor = pastas[i];
      achou = true;
    }
  }
  // Pasta acima da imediata pode ser o número da frota: sem RevN, só a imediata vale.
  if (!achou) cod_faz = parCodIsolado(fazenda_monitor);
  const d = /^(\d{4})_(\d{2})_(\d{2})_/.exec(arquivo);
  return { tipo: 'jdl', serie: parSerieMaisFrequente(bytes), cod_faz, revisao, fazenda_monitor, data: d ? parDataValida(d[1], d[2], d[3]) : null };
}

function parAtributo(tag, nome) {
  const m = new RegExp(`\\s${nome}="([^"]*)"`).exec(tag);
  return m ? m[1] : null;
}

function parTags(xml, nome) {
  return xml.match(new RegExp(`<${nome}\\s[^>]*>`, 'g')) || [];
}

function parIdentificarFdl(nomeRel, textoXml) {
  const xml = String(textoXml ?? '');
  const ref = parAtributo(parTags(xml, 'FieldRef')[0] || '', 'eridRef');
  const talhao = parTags(xml, 'rcdsetup:Field').find((t) => parAtributo(t, 'erid') === ref);
  const farmRef = talhao ? parAtributo(talhao, 'farmRef') : null;
  const fazenda = parTags(xml, 'rcdsetup:Farm').find((t) => parAtributo(t, 'erid') === farmRef);
  const fazenda_monitor = (ref && fazenda && parAtributo(fazenda, 'name')) || '';
  const rev = PAR_REV.exec(fazenda_monitor);
  const inicio = parAtributo(parTags(xml, 'LogTaskRegion')[0] || '', 'timeStamp') || '';
  const d = /^(\d{4})-(\d{2})-(\d{2})/.exec(inicio);
  return {
    tipo: 'gs3', serie: null,
    cod_faz: rev ? Number(rev[1]) : parCodIsolado(fazenda_monitor),
    revisao: rev ? Number(rev[2]) : null,
    fazenda_monitor,
    data: d ? parDataValida(d[1], d[2], d[3]) : null,
    temFdd: /\sfilePosition="\d+"/.test(xml),
  };
}

function parFrotaSugeridaGs3(caminhoPasta) {
  const limpo = parNormalizar(caminhoPasta).replace(/GS3(?:[_ -]?\d+)?/gi, '').replace(/\d{5}Rev\d+/gi, '');
  const numeros = (limpo.match(/(?<!\d)\d{4,6}(?!\d)/g) || []).filter((n) => !/^20\d{2}$/.test(n));
  return numeros.length ? numeros[numeros.length - 1] : null;
}

function parSepararJaAnalisados(arquivos, shaRegistrados) {
  const vistos = new Set();
  for (const s of shaRegistrados || []) if (s) vistos.add(s.toLowerCase());
  const novos = [], repetidos = [];
  for (const a of arquivos) {
    const sha = a.sha256 ? a.sha256.toLowerCase() : null;
    if (sha && vistos.has(sha)) repetidos.push(a);
    else {
      if (sha) vistos.add(sha);
      novos.push(a);
    }
  }
  return { novos, repetidos };
}

// Estrutura do monitor: <raiz>/GS3_2630/<org>/RCD/EIC/...
function parPastaGs3(caminho) {
  const s = parNormalizar(caminho).split('/');
  const gs3 = s.findIndex((p) => /^GS3/i.test(p));
  if (gs3 >= 0) return s.slice(0, gs3 + 1).join('/');
  const rcd = s.findIndex((p) => /^RCD$/i.test(p));
  return s.slice(0, rcd >= 0 ? rcd : -1).join('/');
}

function parSemExtensao(caminho) {
  return parNormalizar(caminho).replace(/\.[^./]+$/, '').toLowerCase();
}

// Documentação = um .fdl com blocos e o .fdd ao lado. Olha todos os arquivos da pasta, inclusive os já analisados.
function parTemDocumentacao(arquivosDaPasta) {
  const fdds = new Set(arquivosDaPasta.filter((a) => parExtensao(a.caminho) === 'fdd').map((a) => parSemExtensao(a.caminho)));
  return arquivosDaPasta.some((a) => parExtensao(a.caminho) === 'fdl' && a.temFdd && fdds.has(parSemExtensao(a.caminho)));
}

function parConferencia(arquivos, frotas, jaAnalisados) {
  const porSerie = new Map((frotas || []).map((f) => [f.serie, f]));
  const grupos = new Map();
  for (const a of arquivos) {
    const ext = parExtensao(a.caminho);
    if (!['jdl', 'fdl', 'fdd', 'pth', 'pvf'].includes(ext)) continue;
    const tipo = ext === 'jdl' ? 'jdl' : 'gs3';
    const trator = tipo === 'jdl' ? (a.serie || null) : parPastaGs3(a.caminho);
    const chave = `${tipo}|${trator}`;
    if (!grupos.has(chave)) grupos.set(chave, { tipo, trator, todos: [] });
    grupos.get(chave).todos.push(a);
  }
  // Separa no pen-drive inteiro: a mesma sessão em duas pastas seria recusada no envio.
  const analisaveis = arquivos.filter((a) => ['jdl', 'fdl', 'fdd'].includes(parExtensao(a.caminho)));
  const novos = new Set(parSepararJaAnalisados(analisaveis, jaAnalisados).novos);

  return [...grupos.values()].map(({ tipo, trator, todos }) => {
    const frotaSugerida = tipo === 'gs3' ? parFrotaSugeridaGs3(trator) : null;
    const cadastro = porSerie.get(tipo === 'gs3' ? `GS3:${frotaSugerida}` : trator);
    const doGrupo = todos.filter((a) => ['jdl', 'fdl', 'fdd'].includes(parExtensao(a.caminho)));
    const lista = doGrupo.filter((a) => novos.has(a));
    const nJaAnalisados = doGrupo.length - lista.length;
    const temMapa = todos.some((a) => ['pth', 'pvf'].includes(parExtensao(a.caminho)));
    const avisos = [];
    if (!cadastro) avisos.push('serie_desconhecida');
    if (tipo === 'gs3' && temMapa && !parTemDocumentacao(todos)) avisos.push('gs3_sem_documentacao');
    if (nJaAnalisados) avisos.push('ja_analisados');
    return {
      tipo, trator,
      frota: cadastro ? cadastro.frota : null,
      frotaSugerida,
      operacao: cadastro ? cadastro.operacao : null,
      fazendas: [...new Set(lista.map((a) => a.cod_faz).filter((c) => c != null))].sort((x, y) => x - y),
      nArquivos: lista.length,
      nJaAnalisados,
      avisos,
      arquivos: lista,
    };
  });
}

function parPartes(arquivos, limite = PAR_PARTE_MAX) {
  const partes = [];
  let atual = [], soma = 0;
  const fechar = () => {
    if (atual.length) partes.push(atual);
    atual = [];
    soma = 0;
  };
  for (const a of arquivos) {
    if (a.bytes > limite) {
      fechar();
      partes.push([{ ...a, aviso: 'maior_que_limite' }]);
      continue;
    }
    if (soma + a.bytes > limite) fechar();
    atual.push(a);
    soma += a.bytes;
  }
  fechar();
  return partes;
}

// Em milímetros: o ST_AsGeoJSON devolve até 9 decimais e a linha em memória tem mais.
function parChaveLinha(l) {
  return `${l.frota ?? ''}|${l.data ?? ''}|${(l.coords || []).map((c) => `${c[0].toFixed(3)},${c[1].toFixed(3)}`).join(' ')}`;
}

function parMesclarComVigente(linhasVigentes, linhasNovas) {
  const vistas = new Set();
  return [...(linhasVigentes || []), ...(linhasNovas || [])].filter((l) => {
    const k = parChaveLinha(l);
    if (vistas.has(k)) return false;
    vistas.add(k);
    return true;
  });
}

// Mesma regra de mes_execucao em paralelismo/analise.py.
function parMesExecucao(contagemPorData) {
  const porMes = new Map();
  for (const [data, n] of Object.entries(contagemPorData || {})) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(data)) continue;
    const mes = data.slice(0, 7);
    porMes.set(mes, (porMes.get(mes) || 0) + n);
  }
  let melhor = null, maior = -Infinity;
  for (const [mes, n] of porMes) if (n > maior) { melhor = mes; maior = n; }
  return melhor ? `${melhor}-01` : null;
}

function parFormatarPct(n, total) {
  if (!total) return '—';
  return `${(Math.round(n * 10000 / total) / 100).toFixed(2).replace('.', ',')}%`;
}

function parCampoCsv(v) {
  const s = String(v ?? '');
  return /[;"\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function parManifestoCsv(arquivos) {
  const linhas = arquivos.map((a) => [a.caminho, a.bytes, a.sha256, a.frota, a.cod_faz].map(parCampoCsv).join(';'));
  return ['caminho;bytes;sha256;frota;fazenda', ...linhas].join('\n') + '\n';
}
