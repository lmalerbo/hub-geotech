// Função "contas" do Hub Geotech (login único). Única peça com a chave de
// serviço — injetada pelo próprio Supabase em SUPABASE_SERVICE_ROLE_KEY, nunca
// guardada em arquivo. Quem chama manda o próprio login; só admin passa.
// Segredos: HUB_INTEGRACAO_TOKEN (o mesmo que o GeoMap aceita) e GEOMAP_URL.
import { createClient, type SupabaseClient } from "npm:@supabase/supabase-js@2";
import { temAcesso, mapasParaGeomap } from "./regras.js";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const ANON = Deno.env.get("SUPABASE_ANON_KEY")!;
const SERVICO = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const GEOMAP = (Deno.env.get("GEOMAP_URL") || "").replace(/\/$/, "");
const TOKEN_HUB = Deno.env.get("HUB_INTEGRACAO_TOKEN") || "";
const ORIGENS = ["https://lmalerbo.github.io", "http://127.0.0.1:8767"];
const BLOQUEIO = "876000h";
const ALFABETO = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789";

type Acesso = {
  email: string; nome: string; admin: boolean; niveis: Record<string, string>;
  geomap_ativo: boolean; geomap_admin: boolean; geomap_grupos: number[]; geomap_mapas: { mapa_id: number; pode_editar: boolean }[];
};

export function senhaProvisoria(n = 10): string {
  const b = crypto.getRandomValues(new Uint8Array(n));
  return Array.from(b, (x) => ALFABETO[x % ALFABETO.length]).join("");
}

function cors(req: Request) {
  const o = req.headers.get("Origin") || "";
  return {
    "Access-Control-Allow-Origin": ORIGENS.includes(o) ? o : ORIGENS[0],
    "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Vary": "Origin",
  };
}

async function geomap(caminho: string, opcoes: RequestInit = {}) {
  if (!GEOMAP || !TOKEN_HUB) throw new Error("GeoMap não configurado na função (GEOMAP_URL/HUB_INTEGRACAO_TOKEN)");
  const r = await fetch(`${GEOMAP}${caminho}`, {
    ...opcoes,
    headers: { "x-hub-token": TOKEN_HUB, "Content-Type": "application/json" },
    signal: AbortSignal.timeout(20000),   // Render dormindo: não segurar a tela do admin para sempre
  });
  const corpo = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`GeoMap: ${corpo.erro || `HTTP ${r.status}`}`);
  return corpo;
}

async function contaPorEmail(servico: SupabaseClient, email: string) {
  for (let pagina = 1; ; pagina++) {
    const { data, error } = await servico.auth.admin.listUsers({ page: pagina, perPage: 200 });
    if (error) throw new Error(`Auth: ${error.message}`);
    const achou = data.users.find((u) => (u.email || "").toLowerCase() === email);
    if (achou) return achou;
    if (data.users.length < 200) return null;
  }
}

// Erros do Supabase viram exceção (a tela mostra a mensagem em vez de "salvo" sem ter salvo).
async function exigir<T extends { error: { message: string } | null }>(p: PromiseLike<T>, oQue: string): Promise<T> {
  const r = await p;
  if (r.error) throw new Error(`${oQue}: ${r.error.message}`);
  return r;
}

async function bloquear(servico: SupabaseClient, id: string, sim: boolean) {
  await exigir(servico.auth.admin.updateUserById(id, { ban_duration: sim ? BLOQUEIO : "none" }), "Não foi possível atualizar o bloqueio da conta");
}

async function marcarTrocaDeSenha(servico: SupabaseClient, id: string) {
  await exigir(servico.from("usuarios").update({ precisa_trocar_senha: true }).eq("id", id), "Não foi possível marcar a troca de senha");
}

async function salvar(comoUsuario: SupabaseClient, servico: SupabaseClient, a: Acesso) {
  const email = String(a.email || "").trim().toLowerCase();
  let conta = await contaPorEmail(servico, email);
  let senha: string | null = null;
  if (!conta) {
    senha = senhaProvisoria();
    const { data, error } = await servico.auth.admin.createUser({
      email, password: senha, email_confirm: true, user_metadata: { nome: a.nome },
    });
    if (error) throw new Error(`Não foi possível criar a conta: ${error.message}`);
    conta = data.user;
  }
  const { error } = await comoUsuario.rpc("acesso_salvar", {
    p_email: email, p_nome: a.nome, p_admin: !!a.admin, p_niveis: a.niveis || {},
    p_geomap_ativo: !!a.geomap_ativo, p_geomap_admin: !!a.geomap_admin, p_geomap_grupos: a.geomap_grupos || [],
    p_geomap_mapas: a.geomap_mapas || [],
  });
  if (error) {
    if (senha) await servico.auth.admin.deleteUser(conta!.id);   // conta recém-criada sem acesso: desfaz
    throw new Error(error.message);
  }
  if (senha) await marcarTrocaDeSenha(servico, conta!.id);
  await bloquear(servico, conta!.id, !temAcesso({ niveis: a.niveis, geomap_ativo: a.geomap_ativo, admin: a.admin }));
  let avisoGeomap: string | null = null;
  try {
    await geomap("/integracao/contas/usuario", {
      method: "PUT",
      body: JSON.stringify({ email, nome: a.nome, ativo: !!a.geomap_ativo, admin: !!a.geomap_admin, grupoIds: a.geomap_grupos || [], mapas: a.geomap_ativo ? mapasParaGeomap(a.geomap_mapas) : [] }),
    });
  } catch (e) { avisoGeomap = (e as Error).message; }
  return { ok: true, senhaProvisoria: senha, avisoGeomap };
}

async function redefinir(servico: SupabaseClient, emailBruto: string) {
  const email = String(emailBruto || "").trim().toLowerCase();
  const conta = await contaPorEmail(servico, email);
  if (!conta) throw new Error("Essa pessoa ainda não tem conta.");
  const senha = senhaProvisoria();
  const { error } = await servico.auth.admin.updateUserById(conta.id, { password: senha });
  if (error) throw new Error(`Não foi possível redefinir: ${error.message}`);
  await marcarTrocaDeSenha(servico, conta.id);
  // Quem tem acesso e estava bloqueado (ex.: pela sincronização antiga) volta a entrar com a provisória.
  const { data: acesso } = await exigir(
    servico.from("acessos").select("niveis,geomap_ativo,admin").eq("email", email).maybeSingle(), "Não foi possível ler o acesso");
  if (temAcesso(acesso)) await bloquear(servico, conta.id, false);
  return { ok: true, senhaProvisoria: senha };
}

async function remover(comoUsuario: SupabaseClient, servico: SupabaseClient, emailBruto: string) {
  const email = String(emailBruto || "").trim().toLowerCase();
  const { data: linhas } = await comoUsuario.rpc("acessos_situacao");
  const nome = (linhas || []).find((x: { email: string }) => x.email === email)?.nome || email;
  const { error } = await comoUsuario.rpc("acesso_remover", { p_email: email });
  if (error) throw new Error(error.message);
  const conta = await contaPorEmail(servico, email);
  if (conta) await bloquear(servico, conta.id, true);
  let avisoGeomap: string | null = null;
  try {
    await geomap("/integracao/contas/usuario", { method: "PUT", body: JSON.stringify({ email, nome, ativo: false, admin: false, grupoIds: [], mapas: [] }) });
  } catch (e) { avisoGeomap = (e as Error).message; }
  return { ok: true, avisoGeomap };
}

Deno.serve(async (req) => {
  const h = cors(req);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: h });
  const resp = (obj: unknown, status = 200) =>
    new Response(JSON.stringify(obj), { status, headers: { ...h, "Content-Type": "application/json" } });
  try {
    const comoUsuario = createClient(SUPABASE_URL, ANON, {
      global: { headers: { Authorization: req.headers.get("Authorization") || "" } },
      db: { schema: "hub" }, auth: { persistSession: false },
    });
    const { data: ehAdmin, error } = await comoUsuario.rpc("eh_admin");
    if (error || !ehAdmin) return resp({ erro: "Só administradores gerenciam acessos." }, 403);
    const servico = createClient(SUPABASE_URL, SERVICO, { db: { schema: "hub" }, auth: { persistSession: false } });
    const corpo = await req.json();
    switch (corpo.acao) {
      case "grupos_geomap": return resp(await geomap("/integracao/contas/grupos"));
      case "mapas_geomap": return resp(await geomap("/integracao/contas/mapas"));
      case "salvar": return resp(await salvar(comoUsuario, servico, corpo));
      case "redefinir_senha": return resp(await redefinir(servico, corpo.email));
      case "remover": return resp(await remover(comoUsuario, servico, corpo.email));
      default: return resp({ erro: "Ação desconhecida" }, 400);
    }
  } catch (e) {
    return resp({ erro: (e as Error).message || String(e) }, 400);
  }
});
