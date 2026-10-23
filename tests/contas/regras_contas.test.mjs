// Regras puras da função "contas" (supabase/functions/contas/regras.js), testadas com node --test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { temAcesso, mapasParaGeomap } from "../../supabase/functions/contas/regras.js";

test("quem tem nível em módulo do Hub ou GeoMap tem acesso", () => {
  assert.equal(temAcesso({ niveis: { plantio: "leitura" }, geomap_ativo: false, admin: false }), true);
  assert.equal(temAcesso({ niveis: {}, geomap_ativo: true, admin: false }), true);
});

test("admin sem nada tem acesso (não se tranca fora)", () => {
  // Revisão final (I3): a função bloqueava a conta de um admin que desmarcava todos os módulos.
  assert.equal(temAcesso({ niveis: {}, geomap_ativo: false, admin: true }), true);
});

test("sem nível, sem GeoMap e sem admin: sem acesso (conta bloqueada)", () => {
  assert.equal(temAcesso({ niveis: {}, geomap_ativo: false, admin: false }), false);
  assert.equal(temAcesso({}), false);
});

test("Mapas de aplicação sozinho dá acesso (conta não fica bloqueada)", () => {
  assert.equal(temAcesso({ niveis: { corretivos: "editor" } }), true);
});

test("mapasParaGeomap converte o formato do Hub para o do GeoMap", () => {
  assert.deepEqual(mapasParaGeomap([{ mapa_id: 12, pode_editar: true }, { mapa_id: 3, pode_editar: false }]),
    [{ mapaId: 12, podeEditar: true }, { mapaId: 3, podeEditar: false }]);
  assert.deepEqual(mapasParaGeomap(null), []);
});
