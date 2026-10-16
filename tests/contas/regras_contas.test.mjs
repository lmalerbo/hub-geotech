// Regras puras da função "contas" (supabase/functions/contas/regras.js), testadas com node --test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { temAcesso } from "../../supabase/functions/contas/regras.js";

test("quem tem módulo do Hub ou GeoMap tem acesso", () => {
  assert.equal(temAcesso({ modulos: ["plantio"], geomap_ativo: false, admin: false }), true);
  assert.equal(temAcesso({ modulos: [], geomap_ativo: true, admin: false }), true);
});

test("admin sem módulos e sem GeoMap continua com acesso (não se tranca fora)", () => {
  // Revisão final (I3): a função bloqueava a conta de um admin que desmarcava todos os módulos.
  assert.equal(temAcesso({ modulos: [], geomap_ativo: false, admin: true }), true);
});

test("sem módulo, sem GeoMap e sem admin: sem acesso (conta bloqueada)", () => {
  assert.equal(temAcesso({ modulos: [], geomap_ativo: false, admin: false }), false);
  assert.equal(temAcesso({}), false);
});
