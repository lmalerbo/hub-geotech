// Worker de envio de arquivos do Hub Geotech (Cloudflare Workers).
//
// Recebe o arquivo do app, com o login (JWT) do próprio usuário, e:
//   1) pede ao banco a revisão certa (hub.preparar_envio). A chamada vai com
//      o login do usuário: quem decide se ele pode enviar é o banco;
//   2) sobe o arquivo no GitHub Releases do repositório de arquivos, com o
//      nome no padrão (ex: 10728_VISCONDE.DO.PARNAIBA.3_Rev1.dwg);
//   3) registra no banco (hub.registrar_arquivo).
//
// Também serve GET /ver?url=...: devolve um .pdf das releases com
// "Content-Disposition: inline", pro portal de download mostrar o mapa num
// <iframe> (o GitHub força download e não tem CORS). Só aceita .pdf dos
// repositórios de arquivos do Hub e dos sistemas antigos (Plantio, Preparo e
// Expo_safra/Colheita).
//
// Guarda só o token do GitHub (secret GH_TOKEN) — nenhuma chave do banco com
// poder especial. Variáveis: SUPABASE_URL, SUPABASE_ANON_KEY (pública),
// GH_REPO (ex: lmalerbo/hub-geotech-arquivos), ORIGENS (sites que podem
// chamar, separados por vírgula).

export default {
  async fetch(req, env) {
    const cors = corsHeaders(req, env);
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors });
    const url = new URL(req.url);
    if (req.method === 'GET' && url.pathname === '/ver') return ver(url, env);
    if (req.method !== 'POST' || url.pathname !== '/enviar') return json({ erro: 'Não encontrado' }, 404, cors);
    try {
      return json(await enviar(req, env), 200, cors);
    } catch (e) {
      return json({ erro: e.message }, e.status || 400, cors);
    }
  },
};

function corsHeaders(req, env) {
  const origem = req.headers.get('Origin') || '';
  const permitidas = (env.ORIGENS || '').split(',').map(s => s.trim()).filter(Boolean);
  return {
    'Access-Control-Allow-Origin': permitidas.includes(origem) ? origem : (permitidas[0] || ''),
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Authorization, Content-Type',
    'Vary': 'Origin',
  };
}

async function ver(url, env) {
  const alvo = url.searchParams.get('url') || '';
  const repos = [env.GH_REPO, 'lmalerbo/project-plantio', 'lmalerbo/project-preparo', 'lmalerbo/Expo_safra'];
  const permitido = repos.some(r => alvo.startsWith(`https://github.com/${r}/releases/download/`))
    && /\.pdf$/i.test(alvo) && !alvo.includes('..');
  if (!permitido) return new Response('Endereço não permitido', { status: 400 });
  const r = await fetch(alvo);
  if (!r.ok) return new Response(`Arquivo não encontrado (${r.status})`, { status: r.status });
  const nome = decodeURIComponent(alvo.split('/').pop()).replace(/"/g, '');
  return new Response(r.body, {
    headers: {
      'Content-Type': 'application/pdf',
      'Content-Disposition': `inline; filename="${nome}"`,
      'Cache-Control': 'public, max-age=300',
    },
  });
}

// Sobe um arquivo pra release em fluxo (sem uma segunda cópia na memória: os
// .dwg/.zip da Colheita passam de 50 MB). Tenta de novo uma vez se o GitHub
// devolver erro 5xx; o erro final traz o que o GitHub respondeu.
async function subirAsset(env, releaseId, nome, arq) {
  const url = `https://uploads.github.com/repos/${env.GH_REPO}/releases/${releaseId}/assets?name=${encodeURIComponent(nome)}`;
  let ultimo = '';
  for (let tentativa = 1; tentativa <= 2; tentativa++) {
    const { readable, writable } = new FixedLengthStream(arq.size);
    arq.stream().pipeTo(writable);
    const up = await github(env, url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/octet-stream', 'Content-Length': String(arq.size) },
      body: readable,
    });
    if (up.ok) return up.json();
    ultimo = `${up.status} ${(await up.text()).slice(0, 160)}`;
    if (up.status < 500) break;
    await new Promise(r => setTimeout(r, 2000));
  }
  const mb = (arq.size / 1048576).toFixed(1);
  throw falha(`GitHub: falha ao subir ${nome} (${mb} MB): ${ultimo}`, 502);
}

function json(obj, status, headers) {
  return new Response(JSON.stringify(obj), { status, headers: { ...headers, 'Content-Type': 'application/json' } });
}

function falha(msg, status = 400) {
  const e = new Error(msg);
  e.status = status;
  return e;
}

// Chamada ao banco com o login do usuário (o RLS e as funções conferem a permissão).
async function banco(env, token, caminho, { metodo = 'GET', corpo } = {}) {
  const r = await fetch(`${env.SUPABASE_URL}/rest/v1/${caminho}`, {
    method: metodo,
    headers: {
      apikey: env.SUPABASE_ANON_KEY,
      Authorization: `Bearer ${token}`,
      'Accept-Profile': 'hub',
      'Content-Profile': 'hub',
      'Content-Type': 'application/json',
    },
    body: corpo ? JSON.stringify(corpo) : undefined,
  });
  const dados = r.status === 204 ? null : await r.json().catch(() => null);
  if (!r.ok) throw falha(dados?.message || `Erro ${r.status} no banco`, r.status === 401 ? 401 : 400);
  return dados;
}

// "VISCONDE DO PARNAÍBA 3" → "VISCONDE.DO.PARNAIBA.3" (mesmo padrão dos arquivos atuais).
function nomeFazenda(nome) {
  return nome.normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase()
    .replace(/[^A-Z0-9]+/g, '.').replace(/^\.+|\.+$/g, '');
}

function github(env, caminho, opcoes = {}) {
  const url = caminho.startsWith('http') ? caminho : `https://api.github.com/repos/${env.GH_REPO}${caminho}`;
  return fetch(url, {
    ...opcoes,
    headers: {
      Authorization: `Bearer ${env.GH_TOKEN}`,
      Accept: 'application/vnd.github+json',
      'User-Agent': 'hub-geotech-arquivos',
      ...(opcoes.headers || {}),
    },
  });
}

// Uma release por módulo + fazenda (tag "plantio-10728").
async function releaseDaTag(env, tag, titulo) {
  let r = await github(env, `/releases/tags/${encodeURIComponent(tag)}`);
  if (r.status === 404) {
    r = await github(env, '/releases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tag_name: tag, name: titulo, body: 'Arquivos publicados pelo Hub Geotech.' }),
    });
  }
  if (!r.ok) throw falha(`GitHub: não foi possível abrir a release ${tag} (${r.status})`, 502);
  return r.json();
}

async function enviar(req, env) {
  const token = (req.headers.get('Authorization') || '').replace(/^Bearer\s+/i, '');
  if (!token) throw falha('Faça login no Hub para enviar arquivos', 401);

  const form = await req.formData();
  const modulo = form.get('modulo');
  const documento = form.get('documento');
  const codFaz = parseInt(form.get('cod_faz'), 10);
  const nova = form.get('nova') === '1';
  const motivo = form.get('motivo') || null;
  const arquivos = form.getAll('arquivo').filter(a => typeof a === 'object' && a.size > 0);
  if (!modulo || !documento || !codFaz || !arquivos.length) {
    throw falha('Envio incompleto: módulo, fazenda, documento e arquivo são obrigatórios');
  }

  // Confere as extensões ANTES de abrir revisão, pra não sobrar revisão vazia.
  const exts = arquivos.map(a => a.name.split('.').pop().toLowerCase());
  if (new Set(exts).size !== exts.length) throw falha('Envie um arquivo de cada tipo por vez');
  const [tipo] = await banco(env, token,
    `documento_tipos?select=extensoes&modulo_id=eq.${encodeURIComponent(modulo)}&codigo=eq.${encodeURIComponent(documento)}`);
  if (!tipo) throw falha(`Documento "${documento}" não existe no módulo ${modulo}`);
  for (const ext of exts) {
    if (!tipo.extensoes.includes(ext)) {
      throw falha(`.${ext} não é aceito aqui (aceitos: ${tipo.extensoes.map(e => '.' + e).join(', ')})`);
    }
  }

  const [prep] = await banco(env, token, 'rpc/preparar_envio', {
    metodo: 'POST',
    corpo: { p_modulo: modulo, p_cod_faz: codFaz, p_documento: documento, p_nova: nova, p_motivo: motivo },
  });

  const base = `${codFaz}_${nomeFazenda(prep.fazenda)}_${prep.marcador}${prep.numero}${prep.sufixo}`;
  const release = await releaseDaTag(env, prep.tag, `${prep.fazenda} — ${modulo}`);
  const enviados = [];
  for (const [i, arq] of arquivos.entries()) {
    const nome = `${base}.${exts[i]}`;
    // Reenvio depois de uma falha: o arquivo com esse nome já é desta revisão.
    let asset = (release.assets || []).find(a => a.name === nome);
    if (!asset) {
      asset = await subirAsset(env, release.id, nome, arq);
    }
    await banco(env, token, 'rpc/registrar_arquivo', {
      metodo: 'POST',
      corpo: { p_revisao_id: prep.revisao_id, p_nome: nome, p_url: asset.browser_download_url, p_tamanho: asset.size },
    });
    enviados.push({ nome, url: asset.browser_download_url });
  }
  return { revisao: `${prep.marcador}${prep.numero}`, arquivos: enviados };
}
