// Paralelismo: Web Worker da análise (Pyodide). Lê um arquivo por vez do OPFS; por frota numa fazenda, os pontos viram
// linhas e são descartados (spec §8). Python: paralelismo/navegador.py. Prova: tests/app/teste_paralelismo_worker.py
// Entra {tipo:'processar', item}, com item = {id, pulados, fazendas:[{operacao, cod_faz, base_analise_id, vigentes, talhoes, grupos}]}.
// Saem {tipo:'progresso', id, fazenda, pct, pct_item, fase}, {tipo:'pronto', id, resultado} e {tipo:'erro', id, msg}.
importScripts('paralelismo-puro.js', 'paralelismo-fila.js');

const PAR_PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/';
const PAR_PYSHP = 'pyshp==2.3.1';
const PAR_DIR = '/tmp/par';
let parPy = null;

async function parBaixar(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`não carregou ${url}`);
  return r;
}

async function parPreparar() {
  if (parPy) return parPy;
  importScripts(`${PAR_PYODIDE}pyodide.js`);
  const py = await loadPyodide({ indexURL: PAR_PYODIDE });
  await py.loadPackage(['numpy', 'shapely', 'pyproj', 'micropip'], { messageCallback: () => {} });
  await py.runPythonAsync(`import micropip\nawait micropip.install('${PAR_PYSHP}')`);
  const { modulos } = await (await parBaixar('py/manifest.json')).json();
  for (const rel of modulos.paralelismo) {
    const dados = new Uint8Array(await (await parBaixar(`py/${rel}`)).arrayBuffer());
    py.FS.mkdirTree(`/home/pyodide/${rel.split('/').slice(0, -1).join('/')}`);
    py.FS.writeFile(`/home/pyodide/${rel}`, dados);
  }
  py.FS.mkdirTree(PAR_DIR);
  py.runPython(`import sys; sys.path.insert(0, '/home/pyodide')\nfrom paralelismo.navegador import Grupo, analisar`);
  parPy = py;
  return py;
}

// Copia do OPFS para o sistema de arquivos do Pyodide. O Python apaga depois de ler. Sem o arquivo = pulado.
async function parTrazerArquivo(py, id, arq) {
  const fdl = `${PAR_DIR}/atual.${arq.tipo === 'jdl' ? 'jdl' : 'fdl'}`;
  py.FS.writeFile(fdl, await parOpfsLer(id, arq.opfs));
  if (arq.tipo === 'gs3') py.FS.writeFile(`${PAR_DIR}/atual.fdd`, await parOpfsLer(id, arq.opfs_fdd));
  return fdl;
}

async function parLerGrupo(py, item, grupo, avisar, pulados) {
  const g = py.globals.get('Grupo')(grupo.frota);
  try {
    for (const arq of grupo.arquivos) {
      let caminho;
      try {
        caminho = await parTrazerArquivo(py, item.id, arq);
      } catch (e) {
        pulados.push({ caminho: arq.caminho, motivo: 'nao_lido' });
        continue;
      }
      const lido = g.ler(arq.tipo, caminho, arq.data);
      if (!lido.get('legivel')) pulados.push({ caminho: arq.caminho, motivo: 'ilegivel' });
      lido.destroy();
      avisar(arq.bytes);
    }
    return JSON.parse(g.fechar_json());
  } finally {
    g.destroy();
  }
}

async function parAnalisarFazenda(py, item, faz, avisar, pulados) {
  const total = faz.grupos.reduce((s, g) => s + g.arquivos.reduce((t, a) => t + a.bytes, 0), 0);
  let lidos = 0;
  const linhas_novas = [], frotas_leitura = [];
  avisar(0, 'lendo');
  for (const grupo of faz.grupos) {
    const fechado = await parLerGrupo(py, item, grupo, (bytes) => {
      lidos += bytes;
      avisar(Math.floor(70 * lidos / total), 'lendo');
    }, pulados);
    for (const l of fechado.linhas) linhas_novas.push(l);
    const { frota, duracao_total_s, duracao_trabalho_s, sem_trabalho } = fechado;
    frotas_leitura.push({ frota, duracao_total_s, duracao_trabalho_s, sem_trabalho });
    avisar(Math.floor(70 * lidos / total), 'linhas');
  }
  avisar(70, 'analise');
  const linhas = parMesclarComVigente(faz.vigentes, linhas_novas);
  const r = py.globals.get('analisar')(JSON.stringify(linhas), JSON.stringify(faz.talhoes), `${faz.operacao}_${faz.cod_faz}`);
  try {
    const bytes = r.get(1);
    const shapefile = bytes.toJs();
    bytes.destroy();
    return {
      operacao: faz.operacao, cod_faz: faz.cod_faz, base_analise_id: faz.base_analise_id,
      linhas_novas, frotas_leitura, analise: JSON.parse(r.get(0)), shapefile,
    };
  } finally {
    r.destroy();
  }
}

async function parProcessar(item) {
  const progresso = (fazenda, pct, pct_item, fase) => postMessage({ tipo: 'progresso', id: item.id, fazenda, pct, pct_item, fase });
  progresso(null, 0, 0, 'preparando');
  let py;
  try {
    py = await parPreparar();
  } catch (e) {
    console.error(e);
    postMessage({ tipo: 'erro', id: item.id, msg: PAR_ERRO_PREPARO });
    return;
  }
  const pulados = [...item.pulados];
  const fazendas = [];
  for (const [i, faz] of item.fazendas.entries()) {
    const avisar = (pct, fase) => progresso(faz.cod_faz, pct, Math.floor((i + pct / 100) / item.fazendas.length * 100), fase);
    try {
      fazendas.push(await parAnalisarFazenda(py, item, faz, avisar, pulados));
    } catch (e) {
      console.error(e);
      postMessage({ tipo: 'erro', id: item.id, msg: `Não foi possível analisar a fazenda ${faz.cod_faz}; tente de novo` });
      return;
    }
    avisar(100, 'analise');
  }
  postMessage({ tipo: 'pronto', id: item.id, resultado: { id: item.id, pulados, fazendas } }, fazendas.map((f) => f.shapefile.buffer));
}

onmessage = (e) => {
  if (e.data.tipo === 'processar') parProcessar(e.data.item);
};
