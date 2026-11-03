// Apresentação semanal: exporta os slides para .pptx (imagem de cada slide + notas). Sem DOM no topo.
// Usa as globais htmlToImage e PptxGenJS, carregadas pela página.
// `function` (não const/let) para ficar visível no contexto vm dos testes.

// Nome do arquivo baixado, a partir da semana (ex.: S5M10).
function apNomeArquivo(semana) {
  return semana.toLowerCase() + ' - Apresentacao Geotecnologia - Indicadores e Entregas.pptx';
}

// Um slide por elemento já montado no DOM (1920x1080), com a imagem em tela cheia.
async function apExportar(slidesEls, notas, semana) {
  await document.fonts.ready;
  const pptx = new PptxGenJS();
  pptx.layout = 'LAYOUT_WIDE';
  for (let i = 0; i < slidesEls.length; i++) {
    const el = slidesEls[i];
    const data = await htmlToImage.toPng(el, { pixelRatio: 2, width: 1920, height: 1080 });
    const s = pptx.addSlide();
    s.addImage({ data, x: 0, y: 0, w: '100%', h: '100%' });
    if (notas[i]) s.addNotes(notas[i]);
  }
  await pptx.writeFile({ fileName: apNomeArquivo(semana) });
}
