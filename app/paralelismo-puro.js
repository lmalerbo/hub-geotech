// Paralelismo: regras puras da página (sem DOM). Testes: tests/app/paralelismo_puro.test.js

function parIdentificarJdl(nomeRel, bytes) {
  const path = nomeRel.replace(/\\/g, '/');
  const parts = path.split('/');
  const fileName = parts.pop() || '';
  const dirName = parts.join('/');

  let serie = null;
  let maxCount = 0;
  let firstIndex = -1;
  const seenSeries = new Map();

  for (let i = 0; i <= bytes.length - 13; i++) {
    if (bytes[i] === 0x42 && bytes[i + 1] === 0x4D) {
      let isValid = true;
      for (let d = 0; d < 4; d++) {
        const b = bytes[i + 2 + d];
        if (b < 0x30 || b > 0x39) { isValid = false; break; }
      }
      if (!isValid) continue;
      const letter = bytes[i + 6];
      if (letter < 0x41 || letter > 0x5A) continue;
      for (let d = 0; d < 6; d++) {
        const b = bytes[i + 7 + d];
        if (b < 0x30 || b > 0x39) { isValid = false; break; }
      }
      if (!isValid) continue;

      const s = String.fromCharCode(
        bytes[i], bytes[i + 1], bytes[i + 2], bytes[i + 3], bytes[i + 4], bytes[i + 5],
        bytes[i + 6], bytes[i + 7], bytes[i + 8], bytes[i + 9], bytes[i + 10], bytes[i + 11], bytes[i + 12]
      );
      if (!seenSeries.has(s)) {
        seenSeries.set(s, { count: 0, firstIdx: i });
      }
      const info = seenSeries.get(s);
      info.count++;
      if (info.count > maxCount || (info.count === maxCount && info.firstIdx < firstIndex)) {
        maxCount = info.count;
        serie = s;
        firstIndex = info.firstIdx;
      }
    }
  }

  const revRegex = /(?<!\d)([1-9]\d{4})Rev(\d+)/i;
  let cod_faz = null;
  let revisao = null;
  let fazenda_monitor = '';

  const dirParts = dirName.split('/').filter(Boolean);
  for (let i = dirParts.length - 1; i >= 0; i--) {
    const m = dirParts[i].match(revRegex);
    if (m) {
      cod_faz = parseInt(m[1], 10);
      revisao = parseInt(m[2], 10);
      fazenda_monitor = dirParts[i];
      break;
    }
  }

  if (cod_faz === null) {
    const singleRegex = /(?<!\d)[1-9]\d{4}(?!\d)/;
    const m = dirParts[dirParts.length - 1]?.match(singleRegex);
    if (m) {
      cod_faz = parseInt(m[0], 10);
      revisao = null;
    }
    fazenda_monitor = dirParts[dirParts.length - 1] || '';
  }

  let data = null;
  const dateMatch = fileName.match(/^(\d{4})_(\d{2})_(\d{2})_/);
  if (dateMatch) {
    const year = parseInt(dateMatch[1], 10);
    const month = parseInt(dateMatch[2], 10);
    const day = parseInt(dateMatch[3], 10);
    const d = new Date(year, month - 1, day);
    if (d.getFullYear() === year && d.getMonth() === month - 1 && d.getDate() === day) {
      data = `${year.toString().padStart(4, '0')}-${month.toString().padStart(2, '0')}-${day.toString().padStart(2, '0')}`;
    }
  }

  return { tipo: 'jdl', serie, cod_faz, revisao, fazenda_monitor, data };
}

function parIdentificarFdl(nomeRel, textoXml) {
  const parseAttrs = (tag) => {
    const attrs = {};
    const attrRegex = /(\w+)\s*=\s*"([^"]*)"/g;
    let m;
    while ((m = attrRegex.exec(tag)) !== null) {
      attrs[m[1]] = m[2];
    }
    return attrs;
  };

  const farmTags = [];
  const fieldTags = [];
  const fieldRefTags = [];
  let timeStamp = null;
  let temFdd = false;

  const tagRegex = /<(\w+:?\w+)\b([^>]*)>/g;
  let m;
  while ((m = tagRegex.exec(textoXml)) !== null) {
    const tagName = m[1];
    const attrsStr = m[2];
    const fullTag = m[0];
    const attrs = parseAttrs(fullTag);

    if (tagName === 'rcdsetup:Farm') {
      farmTags.push({ erid: attrs.erid, name: attrs.name });
    } else if (tagName === 'rcdsetup:Field') {
      fieldTags.push({ erid: attrs.erid, farmRef: attrs.farmRef });
    } else if (tagName === 'FieldRef') {
      fieldRefTags.push({ eridRef: attrs.eridRef });
    } else if (tagName === 'LogTaskRegion' && timeStamp === null) {
      timeStamp = attrs.timeStamp;
    } else if (tagName === 'EvenByteDelta') {
      if (attrs.filePosition && /^\d+$/.test(attrs.filePosition)) {
        temFdd = true;
      }
    }
  }

  let farmName = '';
  for (const ref of fieldRefTags) {
    const field = fieldTags.find(f => f.erid === ref.eridRef);
    if (field) {
      const farm = farmTags.find(f => f.erid === field.farmRef);
      if (farm) {
        farmName = farm.name;
        break;
      }
    }
  }

  let cod_faz = null;
  let revisao = null;
  let fazenda_monitor = farmName || '';

  if (farmName) {
    const revMatch = farmName.match(/(?<!\d)([1-9]\d{4})Rev(\d+)/i);
    if (revMatch) {
      cod_faz = parseInt(revMatch[1], 10);
      revisao = parseInt(revMatch[2], 10);
    } else {
      const singleMatch = farmName.match(/(?<!\d)[1-9]\d{4}(?!\d)/);
      if (singleMatch) {
        cod_faz = parseInt(singleMatch[0], 10);
        revisao = null;
      }
    }
  }

  let data = null;
  if (timeStamp && /^\d{4}-\d{2}-\d{2}/.test(timeStamp)) {
    const dateStr = timeStamp.slice(0, 10);
    const [y, m, d] = dateStr.split('-').map(Number);
    const dt = new Date(y, m - 1, d);
    if (dt.getFullYear() === y && dt.getMonth() === m - 1 && dt.getDate() === d) {
      data = dateStr;
    }
  }

  return { tipo: 'gs3', serie: null, cod_faz, revisao, fazenda_monitor, data, temFdd };
}

function parFrotaSugeridaGs3(caminhoPasta) {
  if (!caminhoPasta) return null;
  let path = caminhoPasta.replace(/\\/g, '/');
  path = path.replace(/GS3[_ -]?\d*/gi, '');
  path = path.replace(/\d{5}Rev\d+/gi, '');
  const parts = path.split('/').filter(Boolean);
  const nums = [];
  for (const part of parts) {
    const matches = part.match(/(?<!\d)\d{4,6}(?!\d)/g);
    if (matches) {
      for (const n of matches) {
        const num = parseInt(n, 10);
        if (!(n.length === 4 && num >= 2000 && num <= 2099)) {
          nums.push(num);
        }
      }
    }
  }
  return nums.length > 0 ? String(nums[nums.length - 1]) : null;
}

function parSepararJaAnalisados(arquivos, shaRegistrados) {
  const registrados = new Set();
  if (shaRegistrados) {
    for (const s of shaRegistrados) {
      if (s) registrados.add(s.toLowerCase());
    }
  }
  const vistos = new Set();
  const novos = [];
  const repetidos = [];
  for (const a of arquivos) {
    const sha = a.sha256?.toLowerCase();
    if (!sha) {
      novos.push(a);
      continue;
    }
    if (registrados.has(sha) || vistos.has(sha)) {
      repetidos.push(a);
    } else {
      vistos.add(sha);
      novos.push(a);
    }
  }
  return { novos, repetidos };
}

function parPastaGs3(caminho) {
  const path = caminho.replace(/\\/g, '/');
  const parts = path.split('/');
  for (let i = 0; i < parts.length; i++) {
    if (/^GS3/i.test(parts[i])) {
      return parts.slice(0, i + 1).join('/');
    }
  }
  for (let i = 0; i < parts.length; i++) {
    if (/^RCD$/i.test(parts[i])) {
      return parts.slice(0, i).join('/');
    }
  }
  return parts.slice(0, -1).join('/');
}

function parConferencia(arquivos, frotas, jaAnalisados) {
  const validExt = ['.jdl', '.fdl', '.fdd', '.pth', '.pvf'];
  const grupos = [];
  const gruposMap = new Map();

  const frotaMap = new Map();
  for (const f of frotas) {
    frotaMap.set(f.serie, { frota: f.frota, operacao: f.operacao });
  }

  const jaSet = new Set((jaAnalisados || []).map(s => s.toLowerCase()));
  const vistosNoGrupo = new Map();

  for (const arq of arquivos) {
    const ext = (arq.caminho?.match(/\.([^.]+)$/) || [])[1]?.toLowerCase();
    if (!ext || !validExt.includes('.' + ext)) continue;

    let grupoKey;
    let tipo;
    let trator;
    let frotaSugerida = null;

    if (ext === 'jdl') {
      tipo = 'jdl';
      trator = arq.serie || null;
      grupoKey = `jdl|${trator || 'sem_serie'}`;
    } else {
      tipo = 'gs3';
      trator = parPastaGs3(arq.caminho);
      frotaSugerida = parFrotaSugeridaGs3(trator);
      grupoKey = `gs3|${trator}`;
    }

    if (!gruposMap.has(grupoKey)) {
      const frotaInfo = frotaMap.get(tipo === 'jdl' ? trator : 'GS3:' + frotaSugerida);
      const grupo = {
        tipo,
        trator,
        frota: frotaInfo?.frota ?? null,
        frotaSugerida: tipo === 'jdl' ? null : frotaSugerida,
        operacao: frotaInfo?.operacao ?? null,
        fazendas: [],
        nArquivos: 0,
        nJaAnalisados: 0,
        avisos: [],
        arquivos: []
      };
      gruposMap.set(grupoKey, grupo);
      grupos.push(grupo);
      vistosNoGrupo.set(grupoKey, new Set());
    }
    const grupo = gruposMap.get(grupoKey);
    const vistos = vistosNoGrupo.get(grupoKey);

    if (['jdl', 'fdl', 'fdd'].includes(ext)) {
      const sha = arq.sha256?.toLowerCase();
      const isJa = sha && (jaSet.has(sha) || vistos.has(sha));
      if (isJa) {
        grupo.nJaAnalisados++;
      } else {
        grupo.nArquivos++;
        grupo.arquivos.push(arq);
        if (sha) vistos.add(sha);
        if (arq.cod_faz != null) {
          if (!grupo.fazendas.includes(arq.cod_faz)) {
            grupo.fazendas.push(arq.cod_faz);
          }
        }
      }
    }
  }

  for (const grupo of grupos) {
    grupo.fazendas.sort((a, b) => a - b);
    const avisos = [];
    if (grupo.frota === null) avisos.push('serie_desconhecida');

    if (grupo.tipo === 'gs3') {
      const temPthPvf = arquivos.some(a => {
        const ext = (a.caminho?.match(/\.([^.]+)$/) || [])[1]?.toLowerCase();
        return ['pth', 'pvf'].includes(ext) && a.caminho.startsWith(grupo.trator + '/');
      });
      const temFdlComFdd = arquivos.some(a => {
        const ext = (a.caminho?.match(/\.([^.]+)$/) || [])[1]?.toLowerCase();
        if (ext !== 'fdl') return false;
        if (!a.temFdd) return false;
        const base = a.caminho.replace(/\.fdl$/i, '');
        return arquivos.some(b => b.caminho === base + '.fdd');
      });
      if (temPthPvf && !temFdlComFdd) {
        avisos.push('gs3_sem_documentacao');
      }
    }

    if (grupo.nJaAnalisados > 0) avisos.push('ja_analisados');
    grupo.avisos = avisos;
  }

  return grupos;
}

function parPartes(arquivos, limite = 90 * 1024 * 1024) {
  const partes = [];
  let atual = [];
  let atualBytes = 0;
  for (const arq of arquivos) {
    if (arq.bytes > limite) {
      if (atual.length > 0) {
        partes.push(atual);
        atual = [];
        atualBytes = 0;
      }
      partes.push([{ caminho: arq.caminho, bytes: arq.bytes, aviso: 'maior_que_limite' }]);
    } else if (atualBytes + arq.bytes > limite) {
      partes.push(atual);
      atual = [arq];
      atualBytes = arq.bytes;
    } else {
      atual.push(arq);
      atualBytes += arq.bytes;
    }
  }
  if (atual.length > 0) partes.push(atual);
  return partes;
}

function parMesclarComVigente(linhasVigentes, linhasNovas) {
  const vigentes = linhasVigentes || [];
  const novas = linhasNovas || [];
  const resultado = [];
  const chaves = new Set();

  for (const l of vigentes) {
    const coords = (l.coords || []).map(c => [c[0].toFixed(3), c[1].toFixed(3)]);
    const chave = `${l.frota || ''}|${l.data || ''}|${JSON.stringify(coords)}`;
    if (!chaves.has(chave)) {
      chaves.add(chave);
      resultado.push(l);
    }
  }

  for (const l of novas) {
    const coords = (l.coords || []).map(c => [c[0].toFixed(3), c[1].toFixed(3)]);
    const chave = `${l.frota || ''}|${l.data || ''}|${JSON.stringify(coords)}`;
    if (!chaves.has(chave)) {
      chaves.add(chave);
      resultado.push(l);
    }
  }

  return resultado;
}

function parMesExecucao(contagemPorData) {
  const meses = new Map();
  let firstMonthOrder = 0;
  for (const [data, count] of Object.entries(contagemPorData)) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(data)) continue;
    const mes = data.slice(0, 7) + '-01';
    if (!meses.has(mes)) {
      meses.set(mes, { total: 0, order: firstMonthOrder++ });
    }
    meses.get(mes).total += count;
  }
  let best = null;
  for (const [mes, info] of meses.entries()) {
    if (best === null || info.total > best.total || (info.total === best.total && info.order < best.order)) {
      best = { mes, total: info.total, order: info.order };
    }
  }
  return best?.mes || null;
}

function parFormatarPct(n, total) {
  if (!total || total === 0) return '—';
  const val = Math.round(n * 10000 / total) / 100;
  return val.toFixed(2).replace('.', ',') + '%';
}

function parManifestoCsv(arquivos) {
  const escape = (s) => {
    if (s == null) return '';
    const str = String(s);
    if (/[;"\n\r]/.test(str)) {
      return '"' + str.replace(/"/g, '""') + '"';
    }
    return str;
  };
  let csv = 'caminho;bytes;sha256;frota;fazenda\n';
  for (const a of arquivos) {
    csv += escape(a.caminho) + ';' +
           escape(a.bytes) + ';' +
           escape(a.sha256) + ';' +
           escape(a.frota) + ';' +
           escape(a.cod_faz) + '\n';
  }
  return csv;
}