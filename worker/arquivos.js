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
// Também serve GET /voos-indicadores (Apresentação semanal): confere a
// ferramenta do usuário e repassa à API do GeoMap com o segredo
// INDICADORES_TOKEN, que nunca sai do Worker.
//
// Também serve POST /paralelismo/parte (sobe uma parte dos brutos na release
// da rodada; hub.paralelismo_preparar_parte decide quem pode) e POST
// /paralelismo/excluida (marca a release de uma rodada excluída; só admin).
//
// Guarda só o token do GitHub (secret GH_TOKEN) — nenhuma chave do banco com
// poder especial. Variáveis: SUPABASE_URL, SUPABASE_ANON_KEY (pública),
// GH_REPO (ex: lmalerbo/hub-geotech-arquivos), ORIGENS (sites que podem
// chamar, separados por vírgula), INDICADORES_TOKEN (secret).

export default {
  async fetch(req, env) {
    const cors = corsHeaders(req, env);
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors });
    const url = new URL(req.url);
    if (req.method === 'GET' && url.pathname === '/ver') return ver(url, env);
    if (req.method === 'GET' && url.pathname === '/voos-indicadores') {
      const r = await voosIndicadores(req, env);
      for (const [k, v] of Object.entries(cors)) r.headers.set(k, v);
      return r;
    }
    const rota = req.method === 'POST' && ROTAS_POST[url.pathname];
    if (!rota) return json({ erro: 'Não encontrado' }, 404, cors);
    try {
      return json(await rota(req, env), 200, cors);
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
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Authorization, Content-Type',
    'Vary': 'Origin',
  };
}

const GEOMAP_VOOS = 'https://geomap-docker.onrender.com/integracao/voos/indicadores';

// Apresentação semanal: voos do GeoMap. Quem pode é decidido pelo banco (hub.pode_usar_apresentacao).
export async function voosIndicadores(req, env, buscar = fetch) {
  const token = (req.headers.get('Authorization') || '').replace(/^Bearer\s+/i, '');
  if (!token) return json({ erro: 'Entre no Hub' }, 401, {});
  const url = new URL(req.url);
  const de = url.searchParams.get('de') || '', ate = url.searchParams.get('ate') || '';
  if (!/^\d{4}-\d{2}-\d{2}$/.test(de) || !/^\d{4}-\d{2}-\d{2}$/.test(ate)) return json({ erro: 'Datas inválidas' }, 400, {});
  const p = await buscar(`${env.SUPABASE_URL}/rest/v1/rpc/pode_usar_apresentacao`, {
    method: 'POST',
    headers: { apikey: env.SUPABASE_ANON_KEY, Authorization: `Bearer ${token}`, 'Content-Profile': 'hub', 'Content-Type': 'application/json' },
    body: '{}',
  });
  if (p.status === 401) return json({ erro: 'Sessão expirada' }, 401, {});
  if (!p.ok || (await p.json()) !== true) return json({ erro: 'Sem acesso à Apresentação semanal' }, 403, {});
  let g;
  try {
    g = await buscar(`${GEOMAP_VOOS}?de=${de}&ate=${ate}`, { headers: { 'x-indicadores-token': env.INDICADORES_TOKEN } });
  } catch (e) {
    return json({ erro: 'GeoMap fora do ar' }, 502, {});
  }
  if (!g.ok) return json({ erro: `GeoMap respondeu ${g.status}` }, 502, {});
  return new Response(await g.text(), { status: 200, headers: { 'Content-Type': 'application/json' } });
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

// Troca um arquivo da release sem janela de perda: sobe o novo com nome
// temporário, apaga o antigo e renomeia o novo pro nome original (o link
// público continua o mesmo). Se falhar no meio, o antigo continua lá.
async function substituirAsset(env, releaseId, antigo, nome, arq) {
  const novo = await subirAsset(env, releaseId, `novo-${Date.now()}-${nome}`, arq);
  const del = await github(env, `/releases/assets/${antigo.id}`, { method: 'DELETE' });
  if (!del.ok && del.status !== 404) {
    await github(env, `/releases/assets/${novo.id}`, { method: 'DELETE' });
    throw falha(`GitHub: não foi possível trocar ${nome} (${del.status})`, 502);
  }
  const ren = await github(env, `/releases/assets/${novo.id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: nome }),
  });
  if (!ren.ok) throw falha(`GitHub: arquivo novo enviado mas não renomeado (${ren.status})`, 502);
  return ren.json();
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

// Nome dos arquivos da Colheita, no padrão do Expo_safra.
const SUFIXO_COLHEITA = { exp1l: 'Exp1L', exp2l: 'Exp2L', mapa: 'Exp.Mapa' };

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

  // Colheita não tem controle de revisão: sempre a mesma (Rev0), e o arquivo
  // novo substitui o anterior. O que fica registrado é a nota de cada envio.
  const colheita = modulo === 'colheita';
  const [prep] = await banco(env, token, 'rpc/preparar_envio', {
    metodo: 'POST',
    corpo: { p_modulo: modulo, p_cod_faz: codFaz, p_documento: documento,
             p_nova: colheita ? false : nova, p_motivo: colheita ? null : motivo },
  });

  // Colheita mantém o nome que o campo sempre usou, sem revisão no nome
  // (ex.: 10851_SAO.SEBASTIAO.100_Exp2L.dwg — o GitHub troca espaço por ponto,
  // como já acontecia no Expo_safra).
  const base = colheita
    ? `${codFaz}_${nomeFazenda(prep.fazenda)}_${SUFIXO_COLHEITA[documento] || documento}`
    : `${codFaz}_${nomeFazenda(prep.fazenda)}_${prep.marcador}${prep.numero}${prep.sufixo}`;
  const release = await releaseDaTag(env, prep.tag, `${prep.fazenda} — ${modulo}`);
  const nomes = exts.map(ext => `${base}.${ext}`);
  const existentes = nomes.map(n => (release.assets || []).find(a => a.name === n));
  if (colheita && existentes.some(Boolean) && !(motivo || '').trim()) {
    throw falha('Informe a nota explicando por que o arquivo está sendo atualizado');
  }
  const enviados = [];
  for (const [i, arq] of arquivos.entries()) {
    const nome = nomes[i];
    let asset = existentes[i];
    if (asset && colheita) {
      asset = await substituirAsset(env, release.id, asset, nome, arq);
    } else if (!asset) {
      asset = await subirAsset(env, release.id, nome, arq);
    }
    // (Plantio/Preparo: asset existente com esse nome = reenvio depois de uma
    // falha, o arquivo já é desta revisão.)
    await banco(env, token, 'rpc/registrar_arquivo', {
      metodo: 'POST',
      corpo: { p_revisao_id: prep.revisao_id, p_nome: nome, p_url: asset.browser_download_url, p_tamanho: asset.size },
    });
    if (colheita) {
      await banco(env, token, 'rpc/colheita_nota_arquivo', {
        metodo: 'POST',
        corpo: { p_cod_faz: codFaz, p_nome: nome, p_nota: existentes[i] ? motivo : (motivo || 'primeiro envio') },
      });
    }
    enviados.push({ nome, url: asset.browser_download_url });
  }
  return { revisao: `${prep.marcador}${prep.numero}`, arquivos: enviados };
}

const PAR_CORPO_MAX = 95 * 1048576;
// O GitHub troca caracteres como espaço no nome do asset, e aí o reenvio não acharia o de mesmo nome.
const PAR_NOME = /^[A-Za-z0-9][A-Za-z0-9._-]{0,150}\.(zip|csv)$/;

// Listagem paginada: uma rodada grande pode passar do que cabe numa página.
async function assetDaRelease(env, releaseId, nome) {
  for (let pagina = 1; ; pagina++) {
    const r = await github(env, `/releases/${releaseId}/assets?per_page=100&page=${pagina}`);
    if (!r.ok) throw falha(`GitHub: não foi possível listar a release (${r.status})`, 502);
    const lista = await r.json();
    const achado = lista.find(a => a.name === nome);
    if (achado || lista.length < 100) return achado;
  }
}

// Sobe uma parte dos brutos na release da rodada. Sem rodada_id, o banco reserva
// o id (é a primeira parte); reenviar o mesmo nome substitui o asset.
async function paralelismoParte(req, env) {
  const token = (req.headers.get('Authorization') || '').replace(/^Bearer\s+/i, '');
  if (!token) throw falha('Faça login no Hub para enviar arquivos', 401);
  if (Number(req.headers.get('Content-Length')) > PAR_CORPO_MAX) throw falha('Parte maior que 95 MB', 413);

  const form = await req.formData();
  const rodada = form.get('rodada_id') || '';
  const nome = form.get('nome');
  const arq = form.get('arquivo');
  if (rodada && !/^\d{1,15}$/.test(rodada)) throw falha('Rodada inválida');
  if (typeof nome !== 'string' || !PAR_NOME.test(nome)) throw falha('Nome de arquivo inválido');
  if (!arq || typeof arq !== 'object' || !arq.size) throw falha('Envio incompleto: falta o arquivo');
  if (arq.size > PAR_CORPO_MAX) throw falha('Parte maior que 95 MB', 413);

  let id;
  try {
    id = await banco(env, token, 'rpc/paralelismo_preparar_parte', {
      metodo: 'POST',
      corpo: { p_rodada_id: rodada ? Number(rodada) : null },
    });
  } catch (e) {
    // A rodada já foi gravada (a resposta anterior se perdeu): a release fica como está.
    if (/^rodada_ja_enviada:/.test(e.message)) return { rodada_id: Number(rodada), ja_enviada: true, url: null, bytes: 0 };
    throw e;
  }

  const release = await releaseDaTag(env, `paralelismo-r${id}`, `Paralelismo — rodada ${id}`);
  const antigo = await assetDaRelease(env, release.id, nome);
  const asset = antigo
    ? await substituirAsset(env, release.id, antigo, nome, arq)
    : await subirAsset(env, release.id, nome, arq);
  return { rodada_id: id, url: asset.browser_download_url, bytes: asset.size };
}

// A rodada foi excluída no banco (hub.paralelismo_excluir): a release fica como
// prova e só ganha a marca na descrição. Quem pode é o admin, conforme o banco.
async function paralelismoExcluida(req, env) {
  const token = (req.headers.get('Authorization') || '').replace(/^Bearer\s+/i, '');
  if (!token) throw falha('Faça login no Hub', 401);
  const { release_tag: tag } = await req.json().catch(() => ({}));
  if (typeof tag !== 'string' || !/^paralelismo-r\d+$/.test(tag)) throw falha('Release inválida');
  const nivel = await banco(env, token, 'rpc/paralelismo_nivel', { metodo: 'POST', corpo: {} });
  if (nivel !== 'admin') throw falha('Só administradores marcam rodadas excluídas', 403);
  const viva = await banco(env, token, `paralelismo_rodadas?select=id&release_tag=eq.${tag}`);
  if (viva.length) throw falha('Esta rodada ainda não foi excluída', 409);

  const r = await github(env, `/releases/tags/${tag}`);
  if (r.status === 404) throw falha(`Release ${tag} não encontrada`, 404);
  if (!r.ok) throw falha(`GitHub: não foi possível abrir a release ${tag} (${r.status})`, 502);
  const release = await r.json();
  const descricao = release.body || '';
  if (descricao.includes('EXCLUÍDA em')) return { release_tag: tag, marcada: false };
  const hoje = new Intl.DateTimeFormat('pt-BR', { timeZone: 'America/Sao_Paulo' }).format(new Date());
  const marca = `EXCLUÍDA em ${hoje}`;
  const ed = await github(env, `/releases/${release.id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ body: descricao ? `${descricao}\n\n${marca}` : marca }),
  });
  if (!ed.ok) throw falha(`GitHub: não foi possível marcar a release ${tag} (${ed.status})`, 502);
  return { release_tag: tag, marcada: true };
}

const ROTAS_POST = {
  '/enviar': enviar,
  '/paralelismo/parte': paralelismoParte,
  '/paralelismo/excluida': paralelismoExcluida,
};
