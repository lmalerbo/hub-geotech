// Revisão final (M1): o e-mail não pode ser interpolado dentro de onclick="...('${esc(...)}')".
// esc() vira ' em &#39;, que o navegador desfaz ANTES de rodar o JS do atributo: um e-mail com
// aspas executaria código no navegador do admin. O valor vai em data-email e o JS lê this.dataset.email.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../../app/index.html", import.meta.url), "utf8");

test("nenhum onclick interpola o e-mail como texto de JS", () => {
  const perigosos = html.split("\n").filter((l) => /onclick="[^"]*\('\$\{esc\(/.test(l));
  assert.deepEqual(perigosos, []);
});
