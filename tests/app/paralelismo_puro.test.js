// Funções puras do Paralelismo. Roda com: node --test tests/app/paralelismo_puro.test.js
// Só dados sintéticos: série BM0000X000000, frotas 9xxxx, fazendas fictícias.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');

const ctx = { console };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(__dirname + '/../../app/paralelismo-puro.js', 'utf8'), ctx);
// Objetos do contexto vm têm outros protótipos: normaliza antes de comparar.
const puro = (v) => JSON.parse(JSON.stringify(v));
const igual = (a, b) => assert.deepStrictEqual(puro(a), b);
const bytesDe = (txt) => Uint8Array.from(Buffer.from(txt, 'latin1'));

const S1 = 'BM0000X000001', S2 = 'BM0000Y000002';
const JDL_PASTA = 'pen/JD-Data/log/2026_USINA_10010Rev1_Parte 1';

// ── parIdentificarJdl ──────────────────────────────────────────────────
test('jdl: série mais frequente, fazenda, revisão e data', () => {
  const b = bytesDe(`\x00${S2}\x01${S1}\xff${S1}\x00xx`);
  igual(ctx.parIdentificarJdl(`${JDL_PASTA}/2026_10_26_08_00_00.jdl`, b), {
    tipo: 'jdl', serie: S1, cod_faz: 10010, revisao: 1,
    fazenda_monitor: '2026_USINA_10010Rev1_Parte 1', data: '2026-10-26',
  });
});

test('jdl: sem série nos bytes dá null; série colada em dígito a mais continua sendo achada pelo padrão', () => {
  assert.strictEqual(ctx.parIdentificarJdl('a/10010Rev0/x.jdl', bytesDe('BM00X000001 BM0000x000001')).serie, null);
  assert.strictEqual(ctx.parIdentificarJdl('a/10010Rev0/x.jdl', new Uint8Array(0)).serie, null);
  assert.strictEqual(ctx.parIdentificarJdl('a/10010Rev0/x.jdl', bytesDe(`${S1}9`)).serie, S1);
});

test('jdl: caminho com contrabarra do Windows', () => {
  const r = ctx.parIdentificarJdl('pen\\log\\FAZ_10010Rev2_Parte 1\\2026_01_02_a.jdl', new Uint8Array(0));
  assert.strictEqual(r.cod_faz, 10010);
  assert.strictEqual(r.revisao, 2);
  assert.strictEqual(r.data, '2026-01-02');
});

test('jdl: pasta organizada acima do log também vale pelo RevN', () => {
  const r = ctx.parIdentificarJdl('TORTA/10233Rev0/JD-Data/log/2026_10_10_a.jdl', new Uint8Array(0));
  assert.strictEqual(r.cod_faz, 10233);
  assert.strictEqual(r.revisao, 0);
  assert.strictEqual(r.fazenda_monitor, '10233Rev0');
});

test('jdl: a pasta mais funda com RevN ganha da mais rasa', () => {
  assert.strictEqual(ctx.parIdentificarJdl('10111Rev0/10222Rev3/a.jdl', new Uint8Array(0)).cod_faz, 10222);
});

test('jdl: sem RevN, usa o primeiro número isolado de 5 dígitos da pasta do arquivo', () => {
  const r = ctx.parIdentificarJdl('pen/log/2026_FAZ_10010_20020_Parte 1/x.jdl', new Uint8Array(0));
  assert.strictEqual(r.cod_faz, 10010);
  assert.strictEqual(r.revisao, null);
  assert.strictEqual(r.fazenda_monitor, '2026_FAZ_10010_20020_Parte 1');
});

test('jdl: número da frota em pasta acima não vira fazenda', () => {
  const r = ctx.parIdentificarJdl('90001/JD-Data/log/x.jdl', new Uint8Array(0));
  assert.strictEqual(r.cod_faz, null);
  assert.strictEqual(r.fazenda_monitor, 'log');
});

test('jdl: número colado em mais dígitos ou abaixo de 10000 não é fazenda', () => {
  assert.strictEqual(ctx.parIdentificarJdl('p/123456/x.jdl', new Uint8Array(0)).cod_faz, null);
  assert.strictEqual(ctx.parIdentificarJdl('p/09999/x.jdl', new Uint8Array(0)).cod_faz, null);
  assert.strictEqual(ctx.parIdentificarJdl('p/110010Rev1/x.jdl', new Uint8Array(0)).cod_faz, null);
});

test('jdl: nome de duas fazendas fica com o número colado no Rev e guarda o nome inteiro', () => {
  const r = ctx.parIdentificarJdl('log/2026_USINA_10203-10828Rev0_Parte 1/x.jdl', new Uint8Array(0));
  assert.strictEqual(r.cod_faz, 10828);
  assert.strictEqual(r.fazenda_monitor, '2026_USINA_10203-10828Rev0_Parte 1');
});

test('jdl: arquivo na raiz e data fora do padrão', () => {
  igual(ctx.parIdentificarJdl('x.jdl', new Uint8Array(0)), {
    tipo: 'jdl', serie: null, cod_faz: null, revisao: null, fazenda_monitor: '', data: null,
  });
  assert.strictEqual(ctx.parIdentificarJdl('a/2026_13_40_x.jdl', new Uint8Array(0)).data, null);
  assert.strictEqual(ctx.parIdentificarJdl('a/2026_02_30_x.jdl', new Uint8Array(0)).data, null);
  assert.strictEqual(ctx.parIdentificarJdl('a/2026_10_26.jdl', new Uint8Array(0)).data, null);
});

// ── parIdentificarFdl ──────────────────────────────────────────────────
const FDL = (farm = '10010Rev2', extra = '<EvenByteDelta filePosition="0" />') =>
  `<RCDLogFile><rcdsetup:Farm erid="{f2}" name="20020Rev0" /><rcdsetup:Farm erid="{f1}" name="${farm}" />`
  + '<rcdsetup:Field erid="{t1}" name="1" farmRef="{f1}" /><FieldRef eridRef="{t1}" />'
  + `<LogTaskRegion timeStamp="2026-10-10T10:52:40.400Z" /><LogTaskRegion timeStamp="2026-10-11T10:00:00Z" />${extra}</RCDLogFile>`;

test('fdl: fazenda ligada ao FieldRef, data do primeiro LogTaskRegion e temFdd', () => {
  igual(ctx.parIdentificarFdl('GS3_2630/a/RCD/EIC/Documentation/A1/u.fdl', FDL()), {
    tipo: 'gs3', serie: null, cod_faz: 10010, revisao: 2, fazenda_monitor: '10010Rev2', data: '2026-10-10', temFdd: true,
  });
});

test('fdl: Farm com ordem de atributos diferente', () => {
  const x = '<rcdsetup:Farm name="10010Rev0" erid="f1" /><rcdsetup:Field farmRef="f1" name="1" erid="t1" /><FieldRef eridRef="t1" />';
  assert.strictEqual(ctx.parIdentificarFdl('a.fdl', x).cod_faz, 10010);
});

test('fdl: nome sem RevN usa o número isolado', () => {
  const r = ctx.parIdentificarFdl('a.fdl', FDL('FAZENDA 30030'));
  assert.strictEqual(r.cod_faz, 30030);
  assert.strictEqual(r.revisao, null);
});

test('fdl: sem blocos no catálogo não tem .fdd útil', () => {
  assert.strictEqual(ctx.parIdentificarFdl('a.fdl', FDL('10010Rev2', '')).temFdd, false);
});

test('fdl: filePosition em qualquer tag vale, como no leitor Python', () => {
  assert.strictEqual(ctx.parIdentificarFdl('a.fdl', FDL('10010Rev2', '<OutroBloco filePosition="7" />')).temFdd, true);
});

test('fdl: usa o primeiro LogTaskRegion que tem timeStamp, como o leitor Python', () => {
  const x = '<LogTaskRegion id="1" /><LogTaskRegion timeStamp="2026-10-10T10:00:00Z" />';
  assert.strictEqual(ctx.parIdentificarFdl('a.fdl', x).data, '2026-10-10');
});

test('fdl: XML sem ligação ou vazio não quebra', () => {
  igual(ctx.parIdentificarFdl('a.fdl', ''), {
    tipo: 'gs3', serie: null, cod_faz: null, revisao: null, fazenda_monitor: '', data: null, temFdd: false,
  });
  const semCampo = '<rcdsetup:Farm erid="f1" name="10010Rev0" /><LogTaskRegion timeStamp="ontem" />';
  const r = ctx.parIdentificarFdl('a.fdl', semCampo);
  assert.strictEqual(r.cod_faz, null);
  assert.strictEqual(r.data, null);
});

// ── parFrotaSugeridaGs3 ────────────────────────────────────────────────
test('frota sugerida: número na pasta, sem confundir com GS3_2630, RevN ou ano', () => {
  assert.strictEqual(ctx.parFrotaSugeridaGs3('pen/90001/GS3_2630'), '90001');
  assert.strictEqual(ctx.parFrotaSugeridaGs3('GS3_2630_90001'), '90001');
  assert.strictEqual(ctx.parFrotaSugeridaGs3('GS3_2630'), null);
  assert.strictEqual(ctx.parFrotaSugeridaGs3('10966Rev0/GS3_2630'), null);
  assert.strictEqual(ctx.parFrotaSugeridaGs3('2026/GS3_2630'), null);
  assert.strictEqual(ctx.parFrotaSugeridaGs3('10966Rev0/90002/GS3_2630'), '90002');
  assert.strictEqual(ctx.parFrotaSugeridaGs3('pen\\90003\\GS3_2630'), '90003');
  assert.strictEqual(ctx.parFrotaSugeridaGs3(''), null);
});

test('frota sugerida: número separado do GS3 sem ser o modelo continua valendo', () => {
  assert.strictEqual(ctx.parFrotaSugeridaGs3('pen/GS3 90001'), '90001');
  assert.strictEqual(ctx.parFrotaSugeridaGs3('pen/GS3_90001'), '90001');
  assert.strictEqual(ctx.parFrotaSugeridaGs3('pen/GS3 2630'), null);
  assert.strictEqual(ctx.parFrotaSugeridaGs3('pen/GS3 26305'), '26305');
});

test('frota sugerida: mantém o número como está escrito na pasta', () => {
  assert.strictEqual(ctx.parFrotaSugeridaGs3('pen/09001/GS3_2630'), '09001');
});

// ── parSepararJaAnalisados ─────────────────────────────────────────────
const arq = (caminho, sha256, extra = {}) => ({ caminho, sha256, bytes: 10, ...extra });

test('separar: registrado no banco e repetido dentro do pen-drive', () => {
  const r = ctx.parSepararJaAnalisados([arq('a', 'aa'), arq('b', 'bb'), arq('c', 'aa'), arq('d', 'cc'), arq('e', 'cc')], ['bb']);
  igual(r.novos.map((a) => a.caminho), ['a', 'd']);
  igual(r.repetidos.map((a) => a.caminho), ['b', 'c', 'e']);
});

test('separar: aceita Set, ignora caixa do hash e não confunde arquivo sem hash', () => {
  const r = ctx.parSepararJaAnalisados([arq('a', 'AA'), arq('b', null), arq('c', null)], new Set(['aa']));
  igual(r.novos.map((a) => a.caminho), ['b', 'c']);
  igual(r.repetidos.map((a) => a.caminho), ['a']);
});

test('separar: lista de registrados vazia ou nula', () => {
  assert.strictEqual(ctx.parSepararJaAnalisados([arq('a', 'aa')], null).novos.length, 1);
  assert.strictEqual(ctx.parSepararJaAnalisados([], []).novos.length, 0);
});

// ── parConferencia ─────────────────────────────────────────────────────
const FROTAS = [
  { serie: S1, frota: '90001', operacao: 'cana' },
  { serie: 'GS3:90005', frota: '90005', operacao: 'torta' },
];
const jdl = (nome, sha, serie, cod) => arq(`pen/JD-Data/log/F_${cod}Rev0_P/${nome}.jdl`, sha, { tipo: 'jdl', serie, cod_faz: cod });
const DOC = 'RCD/EIC/Documentation/A1';
const fdl = (raiz, u, sha, cod) => arq(`${raiz}/org/${DOC}/${u}.fdl`, sha, { tipo: 'gs3', serie: null, cod_faz: cod, temFdd: true });
const fdd = (raiz, u, sha) => arq(`${raiz}/org/${DOC}/${u}.fdd`, sha);
const pth = (raiz, sha) => arq(`${raiz}/org/RCD/EIC/Fields/A1/c/mapa.pth`, sha);

test('conferência: agrupa .jdl por série, com frota, operação e fazendas', () => {
  const r = ctx.parConferencia([jdl('a', 'a1', S1, 20020), jdl('b', 'a2', S1, 10010), jdl('c', 'a3', S1, 10010)], FROTAS, []);
  assert.strictEqual(r.length, 1);
  const g = r[0];
  assert.strictEqual(g.tipo, 'jdl');
  assert.strictEqual(g.trator, S1);
  assert.strictEqual(g.frota, '90001');
  assert.strictEqual(g.operacao, 'cana');
  igual(g.fazendas, [10010, 20020]);
  assert.strictEqual(g.nArquivos, 3);
  assert.strictEqual(g.nJaAnalisados, 0);
  igual(g.avisos, []);
  igual(g.arquivos.map((a) => a.sha256), ['a1', 'a2', 'a3']);
});

test('conferência: série fora do cadastro e .jdl sem série avisam serie_desconhecida', () => {
  const r = ctx.parConferencia([jdl('a', 'a1', S2, 10010), jdl('b', 'a2', null, 10010)], FROTAS, []);
  assert.strictEqual(r.length, 2);
  assert.strictEqual(r[0].trator, S2);
  assert.strictEqual(r[0].frota, null);
  assert.strictEqual(r[0].operacao, null);
  igual(r[0].avisos, ['serie_desconhecida']);
  assert.strictEqual(r[1].trator, null);
  igual(r[1].avisos, ['serie_desconhecida']);
});

test('conferência: pasta GS3 usa a frota do nome pela chave GS3:<frota>', () => {
  const raiz = 'pen/90005/GS3_2630';
  const r = ctx.parConferencia([fdl(raiz, 'u1', 's1', 10010), fdd(raiz, 'u1', 's2'), pth(raiz, 's3')], FROTAS, []);
  assert.strictEqual(r.length, 1);
  const g = r[0];
  assert.strictEqual(g.tipo, 'gs3');
  assert.strictEqual(g.trator, raiz);
  assert.strictEqual(g.frota, '90005');
  assert.strictEqual(g.frotaSugerida, '90005');
  assert.strictEqual(g.operacao, 'torta');
  igual(g.fazendas, [10010]);
  assert.strictEqual(g.nArquivos, 2);
  igual(g.arquivos.map((a) => a.sha256), ['s1', 's2']);
  igual(g.avisos, []);
});

test('conferência: pasta GS3 com frota fora do cadastro fica sem frota, com a sugestão', () => {
  const raiz = 'pen/90009/GS3_2630';
  const g = ctx.parConferencia([fdl(raiz, 'u1', 's1', 10010), fdd(raiz, 'u1', 's2')], FROTAS, [])[0];
  assert.strictEqual(g.frota, null);
  assert.strictEqual(g.frotaSugerida, '90009');
  igual(g.avisos, ['serie_desconhecida']);
});

test('conferência: pasta só com mapa de cobertura é gs3_sem_documentacao', () => {
  const raiz = 'pen/90005/GS3_2630';
  const g = ctx.parConferencia([pth(raiz, 's1'), arq(`${raiz}/org/RCD/EIC/Fields/A1/c/m.PVF`, 's2')], FROTAS, [])[0];
  igual(g.avisos, ['gs3_sem_documentacao']);
  assert.strictEqual(g.nArquivos, 0);
  igual(g.fazendas, []);
});

test('conferência: .fdl sem o .fdd vizinho não conta como documentação', () => {
  const raiz = 'pen/90005/GS3_2630';
  const g = ctx.parConferencia([fdl(raiz, 'u1', 's1', 10010), fdd(raiz, 'outra', 's2'), pth(raiz, 's3')], FROTAS, [])[0];
  assert.ok(g.avisos.includes('gs3_sem_documentacao'));
});

test('conferência: .fdl com temFdd false não conta como documentação', () => {
  const raiz = 'pen/90005/GS3_2630';
  const f = fdl(raiz, 'u1', 's1', 10010);
  f.temFdd = false;
  const g = ctx.parConferencia([f, fdd(raiz, 'u1', 's2'), pth(raiz, 's3')], FROTAS, [])[0];
  assert.ok(g.avisos.includes('gs3_sem_documentacao'));
});

test('conferência: mesmo pen-drive de novo com .pth novo não vira sem documentação', () => {
  const raiz = 'pen/90005/GS3_2630';
  const g = ctx.parConferencia([fdl(raiz, 'u1', 's1', 10010), fdd(raiz, 'u1', 's2'), pth(raiz, 'novo')], FROTAS, ['s1', 's2'])[0];
  igual(g.avisos, ['ja_analisados']);
  assert.strictEqual(g.nArquivos, 0);
  assert.strictEqual(g.nJaAnalisados, 2);
  igual(g.arquivos, []);
  igual(g.fazendas, []);
});

test('conferência: já analisados saem da contagem, e o repetido dentro do pen-drive também', () => {
  const r = ctx.parConferencia([jdl('a', 'a1', S1, 10010), jdl('b', 'a2', S1, 20020), jdl('c', 'a3', S1, 30030), jdl('d', 'a3', S1, 30030)], FROTAS, ['a2']);
  const g = r[0];
  igual(g.avisos, ['ja_analisados']);
  assert.strictEqual(g.nArquivos, 2);
  assert.strictEqual(g.nJaAnalisados, 2);
  igual(g.fazendas, [10010, 30030]);
});

test('conferência: pen-drive com .jdl e GS3 juntos, e arquivos soltos fora de qualquer grupo', () => {
  const raiz = 'pen/GS3_2630';
  const r = ctx.parConferencia([jdl('a', 'a1', S1, 10010), fdl(raiz, 'u1', 's1', 20020), fdd(raiz, 'u1', 's2'),
    arq('pen/leiame.txt', 't1'), arq(`${raiz}/org/RCD/EIC/setup.fds`, 't2')], FROTAS, []);
  igual(r.map((g) => g.tipo), ['jdl', 'gs3']);
  assert.strictEqual(r[1].trator, raiz);
  assert.strictEqual(r[1].nArquivos, 2);
});

test('conferência: GS3 sem pasta GS3 no caminho agrupa pelo que vem antes de RCD, ou pela pasta do arquivo', () => {
  const a = ctx.parConferencia([arq('pen/90005/RCD/EIC/Documentation/A1/u.fdl', 's1', { tipo: 'gs3', cod_faz: 10010, temFdd: true })], FROTAS, [])[0];
  assert.strictEqual(a.trator, 'pen/90005');
  assert.strictEqual(a.frota, '90005');
  const b = ctx.parConferencia([arq('copia/u.FDL', 's1', { tipo: 'gs3', cod_faz: 10010, temFdd: true })], FROTAS, [])[0];
  assert.strictEqual(b.trator, 'copia');
});

test('conferência: duas pastas GS3 viram dois tratores, e não muda a lista recebida', () => {
  const entrada = [fdl('p/90005/GS3_2630', 'u1', 's1', 10010), fdl('p/90009/GS3_2630', 'u2', 's2', 10010)];
  const copia = JSON.stringify(entrada);
  assert.strictEqual(ctx.parConferencia(entrada, FROTAS, []).length, 2);
  assert.strictEqual(JSON.stringify(entrada), copia);
});

test('conferência: sem arquivos', () => {
  igual(ctx.parConferencia([], FROTAS, []), []);
});

test('conferência: pasta documentada não esconde o aviso de outra pasta só com mapa', () => {
  const doc = 'pen/90005/GS3_2630', sem = 'pen/90009/GS3_2630';
  const r = ctx.parConferencia([fdl(doc, 'u1', 's1', 10010), fdd(doc, 'u1', 's2'), pth(doc, 's3'), pth(sem, 's4')], FROTAS, []);
  assert.ok(!r[0].avisos.includes('gs3_sem_documentacao'));
  assert.ok(r[1].avisos.includes('gs3_sem_documentacao'));
});

test('conferência: mesma sessão em duas pastas conta uma vez, senão o envio seria recusado', () => {
  const r = ctx.parConferencia([fdl('p/90005/GS3_2630', 'u1', 's1', 10010), fdl('p/90009/GS3_2630', 'u1', 's1', 10010)], FROTAS, []);
  assert.strictEqual(r[0].nArquivos, 1);
  assert.strictEqual(r[1].nArquivos, 0);
  assert.strictEqual(r[1].nJaAnalisados, 1);
  igual(r[1].avisos, ['serie_desconhecida', 'ja_analisados']);
});

test('conferência: pasta acima que começa com GS3 não junta dois tratores', () => {
  const r = ctx.parConferencia([fdl('GS3/90005/GS3_2630', 'u1', 's1', 10010), fdl('GS3/90009/GS3_2630', 'u2', 's2', 10010)], FROTAS, []);
  igual(r.map((g) => g.trator), ['GS3/90005/GS3_2630', 'GS3/90009/GS3_2630']);
  igual(r.map((g) => g.frotaSugerida), ['90005', '90009']);
});

test('conferência: pasta acima chamada RCD não junta dois tratores', () => {
  const f = (raiz, sha) => arq(`RCD/${raiz}/GS3_2630/org/RCD/EIC/a.fdl`, sha, { tipo: 'gs3', cod_faz: 10010, temFdd: true });
  const r = ctx.parConferencia([f('90005', 's1'), f('90009', 's2')], FROTAS, []);
  igual(r.map((g) => g.trator), ['RCD/90005/GS3_2630', 'RCD/90009/GS3_2630']);
});

test('conferência: nome de arquivo que começa com GS3 não vira pasta', () => {
  const g = ctx.parConferencia([arq('pen/90005/GS3.pth', 's1')], FROTAS, [])[0];
  assert.strictEqual(g.trator, 'pen/90005');
});

test('conferência: pasta abaixo de RCD que começa com GS3 não muda a pasta do trator', () => {
  const g = ctx.parConferencia([arq('pen/GS3_2630/org/RCD/EIC/GS3x/u.fdl', 's1', { tipo: 'gs3', cod_faz: 10010, temFdd: true })], FROTAS, [])[0];
  assert.strictEqual(g.trator, 'pen/GS3_2630');
});

// ── parRegistrosDoGrupo ────────────────────────────────────────────────
test('registros: tipo pela extensão, frota do grupo, .fdd herda a fazenda do .fdl vizinho', () => {
  const raiz = 'pen/90005/GS3_2630';
  const f = fdl(raiz, 'u1', 's1', 10010);
  f.fazenda_monitor = '10010Rev0';
  const g = ctx.parConferencia([f, fdd(raiz, 'u1', 's2')], FROTAS, [])[0];
  igual(ctx.parRegistrosDoGrupo(g), [
    { sha256: 's1', caminho: f.caminho, bytes: 10, tipo: 'fdl', serie: null, frota: '90005', cod_faz: 10010, fazenda_monitor: '10010Rev0' },
    { sha256: 's2', caminho: `${raiz}/org/${DOC}/u1.fdd`, bytes: 10, tipo: 'fdd', serie: null, frota: '90005', cod_faz: 10010, fazenda_monitor: '10010Rev0' },
  ]);
});

test('registros: .jdl leva a série, e a frota escolhida pelo usuário é a que vale', () => {
  const g = ctx.parConferencia([jdl('a', 'a1', S2, 10010)], FROTAS, [])[0];
  const [r] = ctx.parRegistrosDoGrupo({ ...g, frota: '90007' });
  assert.strictEqual(r.tipo, 'jdl');
  assert.strictEqual(r.serie, S2);
  assert.strictEqual(r.frota, '90007');
  assert.strictEqual(r.fazenda_monitor, null);
});

test('registros: .fdd sem .fdl novo ao lado fica sem fazenda, e o manifesto sai com a frota', () => {
  const raiz = 'pen/90005/GS3_2630';
  const g = ctx.parConferencia([fdd(raiz, 'u1', 's2')], FROTAS, [])[0];
  const r = ctx.parRegistrosDoGrupo(g);
  assert.strictEqual(r[0].cod_faz, null);
  assert.strictEqual(ctx.parManifestoCsv(r).split('\n')[1], `${raiz}/org/${DOC}/u1.fdd;10;s2;90005;`);
});

test('conferência: aceita Set em jaAnalisados e frotas nula', () => {
  const g = ctx.parConferencia([jdl('a', 'a1', S1, 10010)], null, new Set(['a1']))[0];
  assert.strictEqual(g.nJaAnalisados, 1);
  assert.strictEqual(g.frota, null);
});

test('conferência: .FDD maiúsculo e caminho com contrabarra contam como documentação', () => {
  const g = ctx.parConferencia([
    arq('pen\\GS3_2630\\org\\RCD\\u.FDL', 's1', { tipo: 'gs3', cod_faz: 10010, temFdd: true }),
    arq('pen\\GS3_2630\\org\\RCD\\u.FDD', 's2'),
    arq('pen\\GS3_2630\\org\\RCD\\m.pth', 's3'),
  ], FROTAS, [])[0];
  assert.strictEqual(g.trator, 'pen/GS3_2630');
  assert.ok(!g.avisos.includes('gs3_sem_documentacao'));
});

// ── parPartes ──────────────────────────────────────────────────────────
const it = (caminho, bytes) => ({ caminho, bytes });

test('partes: enche na ordem e abre outra quando passa do limite', () => {
  const r = ctx.parPartes([it('a', 40), it('b', 60), it('c', 30), it('d', 10)], 100);
  igual(r.map((p) => p.map((a) => a.caminho)), [['a', 'b'], ['c', 'd']]);
});

test('partes: exatamente o limite cabe', () => {
  assert.strictEqual(ctx.parPartes([it('a', 100)], 100).length, 1);
  assert.strictEqual(ctx.parPartes([it('a', 50), it('b', 50), it('c', 1)], 100).length, 2);
});

test('partes: arquivo maior que o limite vai sozinho, com aviso, sem mudar a entrada', () => {
  const entrada = [it('a', 10), it('grande', 500), it('b', 10)];
  const r = ctx.parPartes(entrada, 100);
  igual(r, [[it('a', 10)], [{ caminho: 'grande', bytes: 500, aviso: 'maior_que_limite' }], [it('b', 10)]]);
  assert.strictEqual(entrada[1].aviso, undefined);
});

test('partes: arquivo grande mantém os outros campos', () => {
  const r = ctx.parPartes([{ caminho: 'g', bytes: 500, sha256: 'aa', frota: '90001' }], 100);
  igual(r, [[{ caminho: 'g', bytes: 500, sha256: 'aa', frota: '90001', aviso: 'maior_que_limite' }]]);
});

test('partes: limite padrão é 90 MB e lista vazia não gera parte', () => {
  const mb = 1024 * 1024;
  assert.strictEqual(ctx.parPartes([it('a', 45 * mb), it('b', 45 * mb), it('c', 1)]).length, 2);
  igual(ctx.parPartes([]), []);
});

// ── parMesclarComVigente ───────────────────────────────────────────────
const linha = (frota, data, coords, extra = {}) => ({ frota, data, coords, ...extra });

test('mesclar: junta vigentes e novas, vigentes primeiro', () => {
  const r = ctx.parMesclarComVigente([linha('90001', '2026-10-01', [[0, 0], [10, 0]])], [linha('90002', '2026-10-02', [[0, 3], [10, 3]])]);
  igual(r.map((l) => l.frota), ['90001', '90002']);
});

test('mesclar: mesma linha não duplica, mesmo com menos decimais vindos do banco', () => {
  const vig = [linha('90001', '2026-10-01', [[600000.123456789, 7600000.5], [600010, 7600000.5]])];
  const nova = [linha('90001', '2026-10-01', [[600000.12345678912, 7600000.5000000001], [600010, 7600000.5]], { operacao: 'cana', cod_faz: 10010 })];
  assert.strictEqual(ctx.parMesclarComVigente(vig, nova).length, 1);
});

test('mesclar: não duplica no limite de arredondamento entre memória e banco', () => {
  const vig = [linha('90001', null, [[0.0005, 1], [2, 1]])];
  const nova = [linha('90001', null, [[0.00049999999999, 1], [2, 1]])];
  assert.strictEqual(ctx.parMesclarComVigente(vig, nova).length, 1);
});

test('mesclar: mesma geometria de outra frota ou outra data continua, e duplicata entre as novas sai', () => {
  const c = [[0, 0], [10, 0]];
  const r = ctx.parMesclarComVigente([linha('90001', '2026-10-01', c)],
    [linha('90002', '2026-10-01', c), linha('90001', '2026-10-02', c), linha('90003', null, c), linha('90003', null, c)]);
  assert.strictEqual(r.length, 4);
});

test('mesclar: listas vazias ou nulas', () => {
  igual(ctx.parMesclarComVigente([], []), []);
  assert.strictEqual(ctx.parMesclarComVigente(null, [linha('1', null, [[0, 0], [1, 1]])]).length, 1);
});

// ── parMesExecucao (mesma regra do Python: paralelismo/analise.py, mes_execucao) ─────
test('mês: soma por mês e devolve o maior', () => {
  assert.strictEqual(ctx.parMesExecucao({ '2026-09-30': 5, '2026-10-01': 3, '2026-10-02': 3 }), '2026-10-01');
});

test('mês: empate fica com o primeiro que apareceu, como no Counter do Python', () => {
  assert.strictEqual(ctx.parMesExecucao({ '2026-10-05': 4, '2026-09-05': 4 }), '2026-10-01');
});

test('mês: ignora data vazia e devolve null sem data', () => {
  assert.strictEqual(ctx.parMesExecucao({ '': 100, 'null': 100, '2026-03-01': 1 }), '2026-03-01');
  assert.strictEqual(ctx.parMesExecucao({}), null);
  assert.strictEqual(ctx.parMesExecucao({ '': 9 }), null);
});

// ── parFormatarPct ─────────────────────────────────────────────────────
test('pct: vírgula decimal e duas casas', () => {
  assert.strictEqual(ctx.parFormatarPct(1951, 2506), '77,85%');
  assert.strictEqual(ctx.parFormatarPct(1, 1), '100,00%');
  assert.strictEqual(ctx.parFormatarPct(0, 5), '0,00%');
  assert.strictEqual(ctx.parFormatarPct(1, 8), '12,50%');
});

test('pct: arredonda certo onde o binário erra', () => {
  // 1,005% exato: toFixed direto daria 1,00%.
  assert.strictEqual(ctx.parFormatarPct(201, 20000), '1,01%');
});

test('pct: total zero não dá NaN', () => {
  assert.strictEqual(ctx.parFormatarPct(0, 0), '—');
  assert.strictEqual(ctx.parFormatarPct(3, null), '—');
});

// ── parManifestoCsv ────────────────────────────────────────────────────
test('manifesto: cabeçalho e uma linha por arquivo', () => {
  const r = ctx.parManifestoCsv([{ caminho: 'a/b.jdl', bytes: 10, sha256: 'aa', frota: '90001', cod_faz: 10010 }]);
  assert.strictEqual(r, 'caminho;bytes;sha256;frota;fazenda\na/b.jdl;10;aa;90001;10010\n');
});

test('manifesto: vazios, e campo com ponto e vírgula ou aspas vai entre aspas', () => {
  const r = ctx.parManifestoCsv([{ caminho: 'a;b "c".fdd', bytes: 1, sha256: 'bb' }]);
  assert.strictEqual(r.split('\n')[1], '"a;b ""c"".fdd";1;bb;;');
});

test('manifesto: sem arquivos fica só o cabeçalho', () => {
  assert.strictEqual(ctx.parManifestoCsv([]), 'caminho;bytes;sha256;frota;fazenda\n');
});
