"""Gera assets/icone_jdl.ico (pasta + seta) usado pelo CopiarExecutadosJDL.exe."""
import os
from PIL import Image, ImageDraw

VERDE = (45, 125, 70, 255)
VERDE_ESCURO = (30, 90, 50, 255)
BRANCO = (255, 255, 255, 255)


def desenhar(tam):
    img = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # corpo da pasta
    margem = tam * 0.08
    topo_pasta = tam * 0.38
    d.rounded_rectangle(
        [margem, topo_pasta, tam - margem, tam - margem],
        radius=tam * 0.06,
        fill=VERDE,
        outline=VERDE_ESCURO,
        width=max(1, int(tam * 0.02)),
    )
    # abinha da pasta
    d.polygon(
        [
            (margem, topo_pasta),
            (margem + tam * 0.12, topo_pasta - tam * 0.12),
            (margem + tam * 0.40, topo_pasta - tam * 0.12),
            (margem + tam * 0.50, topo_pasta),
        ],
        fill=VERDE,
        outline=VERDE_ESCURO,
    )

    # seta pra baixo (transferencia/copia)
    cx = tam * 0.5
    topo_seta = tam * 0.06
    fim_haste = tam * 0.34
    largura_haste = tam * 0.10
    d.rectangle(
        [cx - largura_haste / 2, topo_seta, cx + largura_haste / 2, fim_haste],
        fill=BRANCO,
    )
    largura_ponta = tam * 0.24
    d.polygon(
        [
            (cx - largura_ponta / 2, fim_haste),
            (cx + largura_ponta / 2, fim_haste),
            (cx, fim_haste + tam * 0.16),
        ],
        fill=BRANCO,
    )
    return img


def main():
    tamanhos = [16, 24, 32, 48, 64, 128, 256]
    imagens = [desenhar(t) for t in tamanhos]
    saida = os.path.join(os.path.dirname(__file__), "icone_jdl.ico")
    imagens[-1].save(saida, format="ICO", sizes=[(t, t) for t in tamanhos])
    print("icone gerado em", saida)


if __name__ == "__main__":
    main()
