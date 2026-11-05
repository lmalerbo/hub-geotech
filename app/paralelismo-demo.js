// Paralelismo: modo demonstração (file:// ou ?demo). Tudo fictício: usuário editor, frotas, talhões, Worker e envio.
// Nada sai do navegador e nada é gravado. A cópia no OPFS e a conferência rodam de verdade quando o navegador deixa.

const PAR_DEMO_FROTAS = [
  { serie: 'BM0000X000001', frota: '90001', operacao: 'cana', tipo: 'propria' },
  { serie: 'BM0000X000002', frota: '90002', operacao: 'torta', tipo: 'prestador' },
  { serie: 'GS3:90003', frota: '90003', operacao: 'cana', tipo: 'propria' },
];

// Grade 3 x 2 de talhões de ~25 ha, em graus (a tela só precisa do formato GeoJSON do banco).
function parTalhoesDemo(codFaz) {
  const lon0 = -48 + (codFaz % 50) / 1000, lat0 = -21 - (codFaz % 30) / 1000, l = 0.0024;
  const features = [];
  for (let n = 0; n < 6; n++) {
    const x = lon0 + (n % 3) * (l + 0.0003), y = lat0 - Math.floor(n / 3) * (l + 0.0003);
    features.push({
      type: 'Feature', properties: { talhao: n + 1, area_ha: 20 + n * 3, declividade: 2 + n },
      geometry: { type: 'Polygon', coordinates: [[[x, y], [x + l, y], [x + l, y - l], [x, y - l], [x, y]]] },
    });
  }
  return { type: 'FeatureCollection', features };
}

// Números determinísticos por fazenda e talhão: amostras = aderentes + acima + abaixo, como o banco exige.
function parAnaliseDemo(fazenda) {
  const cod = fazenda.cod_faz;
  const talhoes = fazenda.talhoes.features.map((f, i) => {
    const n = f.properties.talhao;
    const amostras = i === 5 ? 18 : 40 + ((n * 13 + cod) % 50);
    const aderentes = Math.round(amostras * (0.5 + ((n * 7 + cod) % 40) / 100));
    const acima = Math.floor((amostras - aderentes) * 0.6);
    return {
      talhao_num: n, amostras, aderentes, acima, abaixo: amostras - aderentes - acima,
      media_m: 3 + ((n + cod) % 9) / 100, frotas: fazenda.grupos.map((g) => g.frota), insuficiente: amostras < 25,
    };
  });
  const soma = (k) => talhoes.reduce((s, t) => s + t[k], 0);
  const fora = 7;
  return {
    pll_total: soma('amostras') + fora, pll_aderentes: soma('aderentes') + 3,
    amostras: soma('amostras'), aderentes: soma('aderentes'), acima: soma('acima'), abaixo: soma('abaixo'),
    fora_talhao: fora, mes: '2026-10-01', talhoes,
    frotas: fazenda.grupos.map((g) => ({ frota: g.frota, amostras: Math.round(soma('amostras') / fazenda.grupos.length), aderentes: Math.round(soma('aderentes') / fazenda.grupos.length) })),
    linhas_usadas: 4, pontos: [],
  };
}

// Faz o papel do Web Worker: mesmas mensagens, resultado sintético, em ~1,5 s.
class ParWorkerDemo {
  constructor() { this.onmessage = null; this.onerror = null; this.onmessageerror = null; this.parado = false; }
  terminate() { this.parado = true; }
  postMessage(m) {
    if (m.tipo !== 'processar') return;
    this.processar(m.item);
  }
  async processar(item) {
    const emitir = (d) => { if (!this.parado && this.onmessage) this.onmessage({ data: d }); };
    const passo = (ms) => new Promise((ok) => setTimeout(ok, ms));
    const fases = ['preparando', 'lendo', 'linhas', 'analise'];
    for (const [i, fase] of fases.entries()) {
      const fazenda = item.fazendas[0] ? item.fazendas[0].cod_faz : null;
      emitir({ tipo: 'progresso', id: item.id, fazenda, pct: i * 25, pct_item: i * 25, fase });
      await passo(window.PAR_DEMO_PASSO ?? 350);
    }
    if (window.PAR_DEMO_FALHA_PREPARO) { emitir({ tipo: 'erro', id: item.id, msg: PAR_ERRO_PREPARO }); return; }
    const fazendas = item.fazendas.map((f) => ({
      operacao: f.operacao, cod_faz: f.cod_faz, base_analise_id: f.base_analise_id,
      linhas_novas: f.grupos.map((g) => ({ frota: g.frota, data: '2026-10-26', coords: [[0, 0], [0, 100]] })),
      frotas_leitura: f.grupos.map((g) => ({ frota: g.frota, duracao_total_s: 7200, duracao_trabalho_s: window.PAR_DEMO_SEM_TRABALHO ? 100 : 6000, sem_trabalho: !!window.PAR_DEMO_SEM_TRABALHO })),
      analise: parAnaliseDemo(f), shapefile: new Uint8Array([80, 75]),
    }));
    emitir({ tipo: 'pronto', id: item.id, resultado: { id: item.id, pulados: item.pulados, parciais: [], fazendas } });
  }
}

const PAR_API_DEMO = {
  vigentes: { 'cana|10001': { amostras: 300, aderentes: 195 } },
  async sessao() { return { id: 'demo' }; },
  async entrar() {},
  async sair() {},
  async eu() { return { id: 'demo', nome: 'Demonstração', admin: false, nivel: window.PAR_DEMO_NIVEL || 'editor', pode: true }; },
  async frotas() { return PAR_DEMO_FROTAS.map((f) => ({ ...f })); },
  async salvarFrota(f) {
    const i = PAR_DEMO_FROTAS.findIndex((x) => x.serie === f.serie);
    if (i >= 0) PAR_DEMO_FROTAS[i] = { ...f }; else PAR_DEMO_FROTAS.push({ ...f });
  },
  async jaAnalisados() {
    if (window.PAR_DEMO_FALHA_JA) { window.PAR_DEMO_FALHA_JA--; throw new Error('Failed to fetch'); }
    return [];
  },
  async buscarBase(operacao, codFaz) {
    return { analise_id: operacao === 'cana' && codFaz === 10001 ? 1 : null, linhas: [], talhoes: parTalhoesDemo(codFaz),
             vigente: PAR_API_DEMO.vigentes[`${operacao}|${codFaz}`] || null };
  },
  async pendentes() { return 2; },
  async preparar(id) {
    if (window.PAR_DEMO_JA_ENVIADO) throw new Error(`rodada_ja_enviada:${id ?? 9001}`);   // gravou, mas a resposta se perdeu
    return id ?? 9001;
  },
  async subir(nome, conteudo, id) {
    if (window.PAR_DEMO_FALHA_ENVIO) { window.PAR_DEMO_FALHA_ENVIO--; throw new Error('Failed to fetch'); }
    return { rodada_id: id, url: `https://exemplo.invalid/${nome}`, bytes: conteudo.size || conteudo.length || 0 };
  },
  async enviar(carga) { window.PAR_DEMO_ENVIADOS = (window.PAR_DEMO_ENVIADOS || []).concat([carga]); return carga.rodada_id; },
};
