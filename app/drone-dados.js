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

// ── motor de atualização (spec §4) ───────────────────────────────────────
// JSON das partes que alimentam cada pedaço da tela. Parte com a mesma
// assinatura do ciclo anterior não é redesenhada (fim do pisca-pisca).
function drAssinaturas(info,geo,doc){
  const tal=(geo.features||[]).filter(f=>f.properties.camada==='talhao');
  const envios=(info.envios||[]).map(({enviado_em,...e})=>e);
  return{
    cab:JSON.stringify([info.faz,doc,geo.normal,geo.catacao,geo.cobertura_pct,
      tal.map(f=>[f.properties.talhao,f.properties.status,f.properties.area_ha])]),
    painel:JSON.stringify([doc,geo.normal&&geo.normal.revisao,info.sols,info.ger,envios,info.obst,info.revs]),
    obst:drAssinaturaObst(info.obst),
    mapa:JSON.stringify([doc,geo.features])};
}
function drPartesMudadas(antes,agora){return Object.keys(agora).filter(k=>!antes||antes[k]!==agora[k]);}
function drRespostaValida(codPedido,codAtual){return codPedido===codAtual;}
function drOcupado(info,ger){
  return !!((ger&&(['fila','processando'].includes(ger.status)||(ger.publicar_pedido_em&&!ger.publicacao_erro)))
    ||(info.envios||[]).some(e=>e.status==='fila'||e.status==='processando'));
}
// Talhões que pulsam no mapa enquanto a prévia é gerada (Catação não tem escopo: só a varredura).
function drTalhoesGerando(ger){
  if(!ger||!['fila','processando'].includes(ger.status))return[];
  return((ger.escopo&&ger.escopo.incluir)||[]).map(i=>i.talhao);
}

// Polling único (spec §4): um timer só. Pausa com a aba oculta ou fora da view
// do Drone e retoma ao voltar. O callback roda uma vez; quem quer continuar chama drPollIniciar de novo.
const DR_POLL={t:null,fn:null,ms:0,fora:false};
function drPollAgendar(){
  clearTimeout(DR_POLL.t);DR_POLL.t=null;
  if(!DR_POLL.fn||DR_POLL.fora||document.visibilityState==='hidden')return;
  DR_POLL.t=setTimeout(()=>{DR_POLL.t=null;const f=DR_POLL.fn;DR_POLL.fn=null;f();},DR_POLL.ms);
}
function drPollIniciar(fn,ms){DR_POLL.fn=fn;DR_POLL.ms=ms;drPollAgendar();}
function drPollParar(){clearTimeout(DR_POLL.t);DR_POLL.t=null;DR_POLL.fn=null;}
function drPollVisivel(naTela){DR_POLL.fora=!naTela;drPollAgendar();}
if(document.addEventListener)document.addEventListener('visibilitychange',drPollAgendar);
