// Paralelismo: cópia do pen-drive no OPFS e fila de processamento (sem DOM). Precisa de paralelismo-puro.js.
// Usado pela página e pelo Web Worker. Testes: tests/app/paralelismo_fila.test.js e tests/app/teste_paralelismo_worker.py

const PAR_OPFS_PASTA = 'paralelismo';
const PAR_ERRO_PREPARO = 'Não foi possível preparar a análise; recarregue a página';
const PAR_ERRO_CONCLUIR = 'Não foi possível concluir a análise; tente de novo';
const PAR_ERRO_COPIA = 'A cópia do pen-drive não está mais no navegador; escolha a pasta de novo';
const PAR_ERRO_ESPACO = 'Não há espaço no navegador para copiar o pen-drive; descarte cópias antigas ou libere espaço no disco';
const PAR_TRAVAS = new Map();

async function parOpfsRaiz(criar) {
  const raiz = await navigator.storage.getDirectory();
  try {
    return await raiz.getDirectoryHandle(PAR_OPFS_PASTA, { create: criar });
  } catch (e) {
    if (e.name === 'NotFoundError') return null;
    throw e;
  }
}

// O lock vive enquanto a aba vive: cópia sem lock é sobra de uma sessão fechada, e outra aba não oferece apagar a cópia em uso.
function parOpfsTravar(id) {
  return new Promise((pronto) => {
    navigator.locks.request(`par-opfs-${id}`, () => new Promise((soltar) => {
      PAR_TRAVAS.set(id, soltar);
      pronto();
    }));
  });
}

function parHex(buffer) {
  return [...new Uint8Array(buffer)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

function parIdentificar(caminho, ext, bytes) {
  if (ext === 'jdl') return parIdentificarJdl(caminho, bytes);
  if (ext === 'fdl') return parIdentificarFdl(caminho, new TextDecoder('latin1').decode(bytes));
  return {};
}

// A escrita só vale no close(): arquivo cortado no meio não fica no OPFS.
async function parOpfsGravar(pasta, nome, bytes) {
  const saida = await (await pasta.getFileHandle(nome, { create: true })).createWritable();
  try {
    await saida.write(bytes);
    await saida.close();
  } catch (e) {
    await saida.abort().catch(() => {});
    throw e;
  }
}

// files = FileList do <input webkitdirectory>. Um arquivo de cada vez na memória. Só .jdl/.fdl/.fdd vão para o banco
// e por isso são copiados; .pth/.pvf entram pelo nome, para o aviso de pasta GS3 sem documentação.
async function parOpfsCopiar(id, files, { aoProgresso } = {}) {
  // A numeração recomeçaria e sobrescreveria arquivos, com o SHA-256 antigo valendo para o conteúdo novo.
  // Copiar de novo (pen-drive recolocado) é com outro id.
  if (PAR_TRAVAS.has(id)) throw new Error(`cópia ${id} já existe`);
  PAR_TRAVAS.set(id, null);
  let pasta;
  try {
    await parOpfsTravar(id);
    pasta = await (await parOpfsRaiz(true)).getDirectoryHandle(id, { create: true });
  } catch (e) {
    await parOpfsDescartar(id).catch(() => {});
    throw e.name === 'QuotaExceededError' ? new Error(PAR_ERRO_ESPACO) : e;
  }
  const arquivos = [], mapas = [], falhas = [];
  const lista = [...files].map((f) => {
    const caminho = parNormalizar(f.webkitRelativePath || f.name);
    return { f, caminho, ext: parExtensao(caminho) };
  });
  const paraCopiar = lista.filter((a) => ['jdl', 'fdl', 'fdd'].includes(a.ext));
  const total = paraCopiar.reduce((soma, a) => soma + a.f.size, 0);
  for (const a of lista) if (['pth', 'pvf'].includes(a.ext)) mapas.push({ caminho: a.caminho, bytes: a.f.size });
  let feitos = 0, n = 0;
  for (const { f, caminho, ext } of paraCopiar) {
    const opfs = `f${String(++n).padStart(6, '0')}.${ext}`;
    try {
      const bytes = new Uint8Array(await f.arrayBuffer());
      const sha256 = parHex(await crypto.subtle.digest('SHA-256', bytes));
      const identificacao = parIdentificar(caminho, ext, bytes);
      await parOpfsGravar(pasta, opfs, bytes);
      arquivos.push({ caminho, bytes: bytes.length, sha256, opfs, ...identificacao });
    } catch (e) {
      if (e.name === 'QuotaExceededError') {
        await parOpfsDescartar(id);
        throw new Error(PAR_ERRO_ESPACO);
      }
      falhas.push({ caminho, motivo: 'nao_copiado' });
    }
    feitos += f.size;
    if (aoProgresso) aoProgresso({ feitos, total, caminho });
  }
  return { arquivos, mapas, falhas };
}

async function parOpfsLer(id, nome) {
  const raiz = await parOpfsRaiz(false);
  if (!raiz) throw Object.assign(new Error(`cópia ${id} não existe`), { name: 'NotFoundError' });
  const pasta = await raiz.getDirectoryHandle(id);
  return new Uint8Array(await (await (await pasta.getFileHandle(nome)).getFile()).arrayBuffer());
}

// Cópias de uma sessão que acabou (foco 5 da revisão): quem abre a página pode descartá-las.
async function parOpfsSobras() {
  const raiz = await parOpfsRaiz(false);
  if (!raiz) return [];
  const { held = [] } = await navigator.locks.query();
  const emUso = new Set(held.map((l) => l.name));
  const sobras = [];
  for await (const [id, pasta] of raiz.entries()) {
    if (pasta.kind !== 'directory' || emUso.has(`par-opfs-${id}`)) continue;
    const sobra = { id, arquivos: 0, bytes: 0, modificado_em: 0 };
    for await (const [, entrada] of pasta.entries()) {
      if (entrada.kind !== 'file') continue;
      const f = await entrada.getFile();
      sobra.arquivos++;
      sobra.bytes += f.size;
      sobra.modificado_em = Math.max(sobra.modificado_em, f.lastModified);
    }
    sobras.push(sobra);
  }
  return sobras;
}

async function parOpfsDescartar(id) {
  try {
    const raiz = await parOpfsRaiz(false);
    if (raiz) await raiz.removeEntry(id, { recursive: true });
  } catch (e) {
    if (e.name !== 'NotFoundError') throw e;
  } finally {
    const soltar = PAR_TRAVAS.get(id);
    PAR_TRAVAS.delete(id);
    if (soltar) soltar();
  }
}

// Um item por vez num único Web Worker. buscarBase(operacao, cod_faz) -> {analise_id, linhas, talhoes} vem da página,
// que tem o login. item = {id, plano (de parPlanoDoItem), ...o que a tela quiser guardar}.
function parCriarFila({ criarWorker, buscarBase, aoMudar = () => {} }) {
  const itens = [];
  let worker = null, atual = null;
  const copia = () => itens.map((i) => ({ ...i }));
  const mudou = () => aoMudar(copia());

  function encerrarWorker() {
    if (worker) worker.terminate();
    worker = null;
  }

  function terminar(item, estado, campos) {
    Object.assign(item, { estado, ...campos });
    atual = null;
    mudou();
    proximo();
  }

  // O Pyodide pode ter ficado inconsistente: o item seguinte começa num Worker novo.
  function falhar(item, msg) {
    encerrarWorker();
    terminar(item, 'erro', { erro: msg });
  }

  function aoMensagem(m) {
    if (!atual || m.id !== atual.id) return;
    if (m.tipo === 'progresso') {
      Object.assign(atual, { fazenda: m.fazenda, pct: m.pct, pct_item: m.pct_item, fase: m.fase });
      mudou();
    } else if (m.tipo === 'pronto') terminar(atual, 'pronto', { resultado: m.resultado, pct: 100, pct_item: 100 });
    else if (m.tipo === 'erro') falhar(atual, m.msg);
  }

  function obterWorker() {
    if (!worker) {
      worker = criarWorker();
      worker.onmessage = (e) => aoMensagem(e.data);
      worker.onerror = () => { if (atual) falhar(atual, PAR_ERRO_PREPARO); };
      // Em geral é o `pronto` que não chegou: a análise rodou, e tentar de novo resolve sem perder a fila.
      worker.onmessageerror = () => { if (atual) falhar(atual, PAR_ERRO_CONCLUIR); };
    }
    return worker;
  }

  async function proximo() {
    if (atual) return;
    const item = itens.find((i) => i.estado === 'na_fila');
    if (!item) return;
    atual = item;
    Object.assign(item, { estado: 'processando', pct: 0, pct_item: 0, fase: 'preparando', fazenda: null, erro: null });
    mudou();
    if (atual !== item) return;
    if (!item.plano.fazendas.length) {
      terminar(item, 'pronto', { resultado: { id: item.id, pulados: item.plano.pulados, parciais: [], fazendas: [] }, pct: 100, pct_item: 100 });
      return;
    }
    const fazendas = [];
    for (const f of item.plano.fazendas) {
      try {
        const base = await buscarBase(f.operacao, f.cod_faz);
        fazendas.push({ ...f, base_analise_id: base.analise_id ?? null, vigentes: base.linhas || [], talhoes: base.talhoes });
      } catch (e) {
        if (atual === item) falhar(item, `Não foi possível buscar os dados da fazenda ${f.cod_faz}; tente de novo`);
        return;
      }
      if (atual !== item) return;
    }
    try {
      obterWorker().postMessage({ tipo: 'processar', item: { id: item.id, pulados: item.plano.pulados, fazendas } });
    } catch (e) {
      falhar(item, PAR_ERRO_PREPARO);
    }
  }

  function adicionar(item) {
    itens.push({ ...item, estado: 'na_fila', pct: 0, pct_item: 0, fase: null, fazenda: null, erro: null, resultado: null });
    mudou();
    proximo();
  }

  function tentarDeNovo(id) {
    const item = itens.find((i) => i.id === id);
    if (!item || item.estado !== 'erro') return;
    item.estado = 'na_fila';
    mudou();
    proximo();
  }

  // Serve também para depois do envio: a cópia no OPFS some junto com o item.
  async function remover(id) {
    const i = itens.findIndex((x) => x.id === id);
    if (i < 0) return;
    if (atual === itens[i]) {
      encerrarWorker();
      atual = null;
    }
    itens.splice(i, 1);
    mudou();
    proximo();
    await parOpfsDescartar(id);
  }

  return { adicionar, tentarDeNovo, remover, itens: copia };
}
