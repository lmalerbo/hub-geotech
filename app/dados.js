// ─────────────────────────────────────────────────────────────
// DADOS — montagem das fazendas e recarga só da fazenda afetada.
// carregarDados() (index.html) lê tudo e usa os mesmos montadores daqui;
// recarregar({modulo,cod}) lê só os talhões/revisões daquela fazenda e troca
// a entrada dela nas listas, sem reler os outros módulos.
// Usa os globais do index (sb, lerTudo, ET, FZ, FZ_P, FZ_C, ARQ…) só na hora
// da chamada, então pode carregar antes do script principal.
// ─────────────────────────────────────────────────────────────

const SEL_PLANTIO='layer,mes_plantio,mapeamento,projeto,talhoes(cod_faz,talhao_num,area_ha,sist_conser,fazendas(nome))';
const SEL_PREPARO='layer,etapa,conservacao_em,talhoes(cod_faz,talhao_num,area_ha,fazendas(nome))';
// Etapas do Preparo, na ordem, como o banco guarda em talhao_preparo.etapa (A1). Índice = e do talhão.
const ETAPAS_PREPARO=['Identificação','Escoamento','Observações','Preparo','Ok'];
const SEL_COLHEITA='layer,cod_faz,talhao_num,area_ha,estagio,data_ultimo_corte,frente,periodo_op,cortado,tipo_linha,ciclo,projeto_desatualizado,status,voo_id,voo_tipo,voo_status,voo_liberar_em';
const SEL_VOOS='id,layer,tipo,problema,pedido_por,apontado_por,apontado_em,status,data_corte,liberar_em,agendado_em,erro';
const SEL_NOTAS='id,entidade_id,valor_novo,usuario_id,criado_em';
const SEL_ETAPA_STATUS='etapa_id,entidade_id,ok,usuario_id,concluido_em,observacao';
const selRevisoes=proj=>'id,documento,numero,motivo,vigente,criado_em,'+proj+'(id,modulo_id,tipo,cod_faz,nome),'
  +'revisao_arquivos(nome_arquivo,release_url),revisao_origens!revisao_origens_revisao_id_fkey(origem_revisao_id)';
const SEL_REVISOES=selRevisoes('projetos');
const VOOS_FECHADOS='(concluido,cancelado)';

// layer = cod_faz*1000 + talhão (coluna gerada em hub.talhoes).
function faixaLayers(cod){const c=Number(cod)*1000;return [c,c+999];}
function codDoLayer(layer){return String(Math.floor(layer/1000));}

// Plantio: agrupa os talhões por fazenda. A etapa da fazenda é a do talhão menos avançado.
function montarPlantio(linhas){
  const idxEtapa=Object.fromEntries(ET.map((e,i)=>[e.l,i]));
  const porFaz=new Map();
  for(const r of linhas){
    const t=r.talhoes;
    if(!t)continue;
    let f=porFaz.get(t.cod_faz);
    if(!f){
      f={n:t.fazendas?.nome||String(t.cod_faz),cod:String(t.cod_faz),t:0,ha:0,e:ET.length-1,mes:'',_mesIso:null,tals:[]};
      porFaz.set(t.cod_faz,f);
    }
    const e=idxEtapa[r.projeto]??0;
    f.tals.push({layer:r.layer,num:t.talhao_num,ha:t.area_ha||0,sist_conser:t.sist_conser,
                 mes:mesLabel(r.mes_plantio),mapeamento:r.mapeamento,e});
    f.t++;f.ha+=t.area_ha||0;f.e=Math.min(f.e,e);
    if(r.mes_plantio&&(!f._mesIso||r.mes_plantio<f._mesIso)){f._mesIso=r.mes_plantio;f.mes=mesLabel(r.mes_plantio);}
  }
  return [...porFaz.values()].sort((a,b)=>a.n.localeCompare(b.n,'pt-BR')).map(f=>{
    f.ha=Math.round(f.ha*10)/10;f.tals.sort((a,b)=>a.num-b.num);return f;
  });
}

// Preparo: fazendas da demanda, talhões com a etapa do banco (tals, como o Plantio) e etapas
// concluídas (etapa_status: ok, quem, quando e a observação). A etapa da fazenda é a do talhão menos avançado.
// mes = "Entregue em": mês do último talhão entregue (view preparo_entregas), só com a fazenda toda Ok.
function montarPreparo(linhas,etapas,status,nomeUsr,entregas){
  const idsEtapa=new Set(etapas.map(e=>e.id));
  const st=new Map(status.filter(s=>idsEtapa.has(s.etapa_id)).map(s=>[s.etapa_id+'|'+s.entidade_id,s]));
  const ent=new Map((entregas||[]).map(x=>[x.layer,x]));
  const idxEtapa=Object.fromEntries(ETAPAS_PREPARO.map((n,i)=>[n,i]));
  const porFaz=new Map();
  for(const r of linhas){
    const t=r.talhoes;
    if(!t)continue;
    let f=porFaz.get(t.cod_faz);
    if(!f){
      f={n:t.fazendas?.nome||String(t.cod_faz),cod:String(t.cod_faz),ha:0,mes:'',ciclo25:false,_ult:'',_todosOk:true,
         voo:'?',ok:[],usr:[],dt:[],obs:'',tals:[],e:ETAPAS_PREPARO.length-1};
      porFaz.set(t.cod_faz,f);
    }
    const e=idxEtapa[r.etapa]??0;
    f.tals.push({layer:r.layer,num:t.talhao_num,ha:t.area_ha||0,e,cons:r.conservacao_em||null});
    f.e=Math.min(f.e,e);
    f.ha+=t.area_ha||0;
    const x=ent.get(r.layer);
    if(r.etapa!=='Ok'||!x)f._todosOk=false;
    if(x){if(x.origem==='ciclo_25_26')f.ciclo25=true;if(x.entregue_em>f._ult)f._ult=x.entregue_em;}
  }
  return [...porFaz.entries()].sort((a,b)=>a[1].n.localeCompare(b[1].n,'pt-BR')).map(([cod,f])=>{
    f.ha=Math.round(f.ha*10)/10;
    f.tals.sort((a,b)=>a.num-b.num);
    f.mes=f._todosOk&&f._ult?mesLabel(f._ult.slice(0,10)):'';
    delete f._ult;delete f._todosOk;
    for(const e of etapas){
      const s=st.get(e.id+'|'+cod);
      f.ok.push(!!s?.ok);
      f.usr.push(s?.ok?(nomeUsr[s.usuario_id]||'—'):'');
      f.dt.push(s?.ok?fmtDataHora(s.concluido_em):'');
      if(s?.observacao)f.obs=s.observacao;
    }
    return f;
  });
}

// Colheita: talhões do ICOL por fazenda; status vem calculado do banco.
function montarColheita(linhas,nomeFaz){
  const porFaz=new Map();
  for(const r of linhas){
    let f=porFaz.get(r.cod_faz);
    if(!f){f={n:nomeFaz[r.cod_faz]||String(r.cod_faz),cod:String(r.cod_faz),fr:'',per:'',desat:false,tals:[],_fr:{}};porFaz.set(r.cod_faz,f);}
    f.tals.push({layer:r.layer,id:r.talhao_num,ha:r.area_ha||0,est:r.estagio||'',st:r.status,tipo:r.tipo_linha,
                 ciclo:r.ciclo,desat:r.projeto_desatualizado,cortado:r.cortado,corte:r.data_ultimo_corte,voo:r.voo_id?{tipo:r.voo_tipo,status:r.voo_status,liberar:r.voo_liberar_em}:null,
                 mes:r.periodo_op?'Período '+r.periodo_op:''});
    if(r.frente)f._fr[r.frente]=(f._fr[r.frente]||0)+1;
    if(r.periodo_op&&!f.per)f.per=String(r.periodo_op);
    if(r.projeto_desatualizado)f.desat=true;
  }
  for(const f of porFaz.values())f.porte=Math.max(-1,...f.tals.map(t=>tagPorte(t)??-1));
  return [...porFaz.values()].sort((a,b)=>a.n.localeCompare(b.n,'pt-BR')).map(f=>{
    f.fr=Object.entries(f._fr).sort((a,b)=>b[1]-a[1]).map(x=>x[0]).join(', ')||'—';
    f.tals.sort((a,b)=>a.id-b.id);return f;
  });
}

// Revisões agrupadas por projeto e documento (a vigente primeiro).
function agruparRevisoes(revisoes){
  const projetos=new Map(),codDaRevisao=new Map();
  for(const r of revisoes){
    const p=r.projetos;
    if(!projetos.has(p.id))projetos.set(p.id,{...p,docs:{},origens:new Set()});
    const pr=projetos.get(p.id);
    (pr.docs[r.documento]??=[]).push({id:r.id,doc:r.documento,modulo:p.modulo_id,numero:r.numero,motivo:r.motivo,
      vigente:r.vigente,criado_em:r.criado_em,arquivos:r.revisao_arquivos||[]});
    (r.revisao_origens||[]).forEach(o=>pr.origens.add(o.origem_revisao_id));
    if(p.tipo==='individual')codDaRevisao.set(r.id,p.cod_faz);
  }
  for(const p of projetos.values())
    Object.values(p.docs).forEach(rs=>rs.sort((a,b)=>(b.vigente-a.vigente)||(b.numero-a.numero)));
  return {projetos,codDaRevisao};
}

// modulo|cod → {docs, blocos}; personalizado aparece em cada fazenda de onde
// vieram as revisões de origem.
function montarArquivos(revisoes){
  const {projetos,codDaRevisao}=agruparRevisoes(revisoes);
  const arq={};
  const entrada=(mod,cod)=>(arq[mod+'|'+cod]??={docs:{},blocos:[]});
  for(const p of projetos.values()){
    if(p.tipo==='individual')entrada(p.modulo_id,p.cod_faz).docs=p.docs;
    else new Set([...p.origens].map(id=>codDaRevisao.get(id)).filter(Boolean))
      .forEach(cod=>entrada(p.modulo_id,cod).blocos.push(p));
  }
  return arq;
}

// Troca a fazenda `cod` em `lista` (ordenada por nome) pela `nova`, no mesmo
// lugar; sem `nova`, tira da lista; se ainda não existia, entra na ordem.
function trocarFazenda(lista,cod,nova){
  const i=lista.findIndex(f=>f.cod===String(cod));
  if(i>=0){if(nova)lista[i]=nova;else lista.splice(i,1);return;}
  if(!nova)return;
  const j=lista.findIndex(f=>f.n.localeCompare(nova.n,'pt-BR')>0);
  lista.splice(j<0?lista.length:j,0,nova);
}

// Qual fazenda uma ação (função do banco) afeta. null = não dá pra saber → recarga inteira.
function alvoDaAcao(fn,args={}){
  const modulo=args.p_modulo||['plantio','preparo','colheita'].find(m=>fn.startsWith(m+'_'));
  if(!modulo)return null;
  if(args.p_cod_faz!=null)return {modulo,cod:String(args.p_cod_faz)};
  const layers=args.p_layers;
  if(Array.isArray(layers)&&layers.length){
    const cods=new Set(layers.map(codDoLayer));
    if(cods.size===1)return {modulo,cod:[...cods][0]};
  }
  return null;
}

const resultado=({data,error})=>{if(error)throw error;return data;};
function lerRevisoesFazenda(modulo,cod){
  return lerTudo(()=>sb.from('projeto_revisoes').select(selRevisoes('projetos!inner'))
    .eq('projetos.modulo_id',modulo).eq('projetos.cod_faz',cod).eq('projetos.tipo','individual')
    .order('numero',{ascending:false}).order('id'));
}
function trocarArquivos(modulo,cod,revisoes){
  const {projetos}=agruparRevisoes(revisoes);
  const docs=[...projetos.values()][0]?.docs||{};
  const blocos=ARQ[modulo+'|'+cod]?.blocos||[];   // personalizados não mudam com ação de uma fazenda
  if(Object.keys(docs).length||blocos.length)ARQ[modulo+'|'+cod]={docs,blocos};
  else delete ARQ[modulo+'|'+cod];
}

// Lê só a fazenda do alvo e troca a entrada dela (FZ / FZ_P / FZ_C e ARQ).
async function carregarFazenda({modulo,cod}){
  if(!['plantio','preparo','colheita'].includes(modulo))throw new Error('módulo sem recarga por fazenda: '+modulo);
  const [ini,fim]=faixaLayers(cod);
  const revisoes=lerRevisoesFazenda(modulo,cod);
  if(modulo==='plantio'){
    const [linhas,revs]=await Promise.all([
      lerTudo(()=>sb.from('talhao_plantio').select(SEL_PLANTIO).gte('layer',ini).lte('layer',fim).order('layer')),
      revisoes]);
    return ()=>{trocarFazenda(FZ,cod,montarPlantio(linhas)[0]);trocarArquivos(modulo,cod,revs);};
  }
  if(modulo==='preparo'){
    const [linhas,etapas,status,entregas,revs]=await Promise.all([
      lerTudo(()=>sb.from('talhao_preparo').select(SEL_PREPARO).gte('layer',ini).lte('layer',fim).order('layer')),
      lerTudo(()=>sb.from('etapas').select('id,ordem').eq('modulo_id','preparo').order('ordem')),
      lerTudo(()=>sb.from('etapa_status').select(SEL_ETAPA_STATUS).eq('entidade_id',cod).order('etapa_id')),
      lerTudo(()=>sb.from('preparo_entregas').select('layer,entregue_em,origem').eq('cod_faz',cod).order('layer')),
      revisoes]);
    const nomeUsr=Object.fromEntries(USUARIOS.map(u=>[u.id,u.nome]));
    return ()=>{trocarFazenda(FZ_P,cod,montarPreparo(linhas,etapas,status,nomeUsr,entregas)[0]);trocarArquivos(modulo,cod,revs);};
  }
  if(modulo==='colheita'){
    const [linhas,faz,voos,notas,revs]=await Promise.all([
      lerTudo(()=>sb.from('colheita_talhoes').select(SEL_COLHEITA).eq('cod_faz',cod).order('layer')),
      sb.from('fazendas').select('cod_faz,nome').eq('cod_faz',cod).then(resultado),
      lerTudo(()=>sb.from('colheita_voos').select(SEL_VOOS).gte('layer',ini).lte('layer',fim)
        .not('status','in',VOOS_FECHADOS).order('id')),
      lerTudo(()=>sb.from('log_auditoria').select(SEL_NOTAS).eq('modulo_id','colheita').eq('campo','arquivo')
        .eq('entidade_id',cod).order('id',{ascending:false})),
      revisoes]);
    const nomeFaz=Object.fromEntries(faz.map(f=>[f.cod_faz,f.nome]));
    return ()=>{
      trocarFazenda(FZ_C,cod,montarColheita(linhas,nomeFaz)[0]);
      VOOS_C=VOOS_C.filter(v=>codDoLayer(v.layer)!==cod).concat(voos).sort((a,b)=>a.id-b.id);
      if(notas.length)NOTAS_C[cod]=notas;else delete NOTAS_C[cod];
      trocarArquivos(modulo,cod,revs);
    };
  }
}

// Avisos são poucos e mudam por gatilho no banco a cada ação: relê todos.
async function carregarAvisos(){
  const [avisos,lidos]=await Promise.all([
    lerTudo(()=>sb.from('avisos').select('id,modulo_id,tipo,cod_faz,titulo,texto,atualizado_em').is('resolvido_em',null).order('atualizado_em',{ascending:false})),
    lerTudo(()=>sb.from('avisos_lidos').select('aviso_id').order('aviso_id'))]);
  const lidosSet=new Set(lidos.map(l=>l.aviso_id));
  return avisos.map(a=>({...a,lido:lidosSet.has(a.id)}));
}
