// Gerador do PDF no navegador: Pyodide + mapas/corretivo_pdf.py (mesmo layout do Drone).
// `var` (não const): a página confere `window.crGerador`, e const de topo não vira propriedade de window.
var crGerador = (() => {
  const VERSAO = '0.27.7';
  let py = null, promessa = null;
  const g = { estado: 'parado', erro: null, passo: 0, passoTxt: '', aoMudar: () => {} };
  const mudar = (estado, erro = null) => { g.estado = estado; g.erro = erro; g.aoMudar(estado); };
  // passo de 0 a 4 durante a preparação, para a tela mostrar o progresso
  const passo = (n, txt) => { g.passo = n; g.passoTxt = txt; g.aoMudar(g.estado); };
  function script(src) {
    return new Promise((ok, falha) => {
      const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = () => falha(new Error('não carregou ' + src));
      document.head.appendChild(s);
    });
  }
  async function preparar() {
    if (promessa) return promessa;
    mudar('preparando');
    promessa = (async () => {
      passo(0, 'Baixando o Python…');
      await script(`https://cdn.jsdelivr.net/pyodide/v${VERSAO}/full/pyodide.js`);
      passo(1, 'Iniciando o Python…');
      py = await loadPyodide();
      passo(2, 'Baixando bibliotecas de mapa…');
      await py.loadPackage(['matplotlib', 'shapely', 'pandas', 'pyproj', 'geopandas']);
      passo(3, 'Carregando o modelo do PDF…');
      const { arquivos } = await (await fetch('py/manifest.json')).json();
      for (const rel of arquivos) {
        const dados = new Uint8Array(await (await fetch('py/' + rel)).arrayBuffer());
        py.FS.mkdirTree('/home/pyodide/' + rel.split('/').slice(0, -1).join('/'));
        py.FS.writeFile('/home/pyodide/' + rel, dados);
      }
      passo(4, 'Quase pronto…');
      py.runPython(`
import sys; sys.path.insert(0, '/home/pyodide')
from matplotlib import font_manager
import glob
for f in glob.glob('/home/pyodide/mapas/fontes/*.ttf'):
    font_manager.fontManager.addfont(f)
from mapas.corretivo_pdf import gerar_bytes`);
      mudar('pronto');
    })().catch(e => { promessa = null; mudar('erro', e); throw e; });
    return promessa;
  }
  async function gerar(dados) {
    await preparar();
    py.globals.set('ENTRADA', JSON.stringify(dados));
    const bytes = py.runPython('gerar_bytes(ENTRADA)').toJs();
    return new Blob([bytes], { type: 'application/pdf' });
  }
  return Object.assign(g, { preparar, gerar });
})();
