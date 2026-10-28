// Drone: estado (DR), chamadas ao banco e regras puras. Carregado por index.html antes de drone-previa/inicio/fazenda.
// Tela do Drone (spec Parte 2, §5): fila de trabalho + fazenda com mapa por talhão.
const DR={painel:null,cod:null,geo:null,mapa:null,sel:new Map(),rem:new Set(),modoRemover:false,
  doc:'normal',ajusteId:null,poll:null,info:null};
const DR_ST={aguardando_obstaculos:'aguardando obstáculos',aguardando_infestacao:'aguardando infestação',
  solicitado:'solicitado',em_elaboracao:'em elaboração',devolvido:'devolvido'};
const DR_COR={normal:'#a0694b',catacao:'#5b8c5a',sel:'#5b6ee8',rem:'#c23b3b',sem:'#e9ebef',fora:'#d4890a'};

// Movimento (app/motion.js). Os botões do Drone chamam as funções sem passar o
// botão; ele é pego do evento do clique — antes de qualquer await/prompt, que
// apagam window.event.
function drBotao(){const e=window.event;return e&&e.target&&e.target.closest?e.target.closest('button'):null;}

async function drRpc(nome,args){
  const {data,error}=await sb.rpc(nome,args||{});
  if(error)throw new Error(error.message);
  return data;
}

// Mapa é reaproveitado só se a fazenda/documento é o mesmo e o mapa existe.
function drMapaReaproveitavel(antes,agora,temMapa){return !!temMapa&&antes===agora;}

function drPodeGerarCatacao(sol){return !!sol&&['solicitado','em_elaboracao'].includes(sol.status);}
function drNomeSeguro(nome){
  return String(nome).normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^A-Za-z0-9._-]/g,'_').replace(/\.\./g,'__');
}
function drClasseEscolhida(txt){
  const t=String(txt??'').replace(/m/gi,'').trim();
  if(!t)return null;                                   // vazio: classe pelo nome do arquivo
  const n=Number(t);return [15,25,50].includes(n)?n:undefined;
}

function drPodeCancelar(sol,ger,eu){
  if(!sol||!eu)return false;
  const ocupado=ger&&(ger.status==='processando'||(ger.status==='pronta'&&ger.publicar_pedido_em&&!ger.publicacao_erro));
  if(ocupado)return false;
  if(podeEditar('drone'))return true;
  return sol.solicitante_id===eu.id&&!ger;            // solicitante: só a própria e antes da prévia
}

function drAtual(){
  const tipo=DR.doc;
  const sol=DR.info.sols.find(s=>s.tipo===tipo)||null;
  const ger=sol?DR.info.ger.find(g=>g.solicitacao_id===sol.id)||null:null;
  return{sol,ger};
}

function drValidarSolicitacao(v){
  if(!v.cod)return'Escolha a fazenda.';
  if(v.data){const hoje=new Date();hoje.setHours(0,0,0,0);if(new Date(v.data+'T12:00')<hoje)return'A data desejada já passou.';}
  return null;
}

// ── obstáculos no mapa (objeto + buffer da classe) ──────────────────────
const DR_OBS_COR={15:'#2e7d32',25:'#e0a100',50:'#c62828'};

function drRotuloShape(envio){
  if(!envio)return'Enviar shape de ajuste';
  if(envio.status==='erro')return'Erro no shape — enviar outro';
  if(envio.status==='ok')return'Shape enviado ✓ (trocar)';
  return'Shape em processamento…';
}

// Envios vêm do mais novo para o mais antigo: o primeiro do tipo é o que vale.
function drUltimoEnvio(envios,tipo){return (envios||[]).find(e=>e.tipo===tipo)||null;}

// Muda quando alguma classe ganha versão nova: aí o desenho guardado (DR.obstGeo) não vale mais.
function drAssinaturaObst(obst){return (obst||[]).map(o=>o.classe_m+':'+o.versao).sort().join('|');}
