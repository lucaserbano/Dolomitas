#!/usr/bin/env python3
"""
Descobre o horario de gravacao de videos que perderam os metadados,
cruzando-os com os arquivos originais pela IMAGEM.

O DJI Mimo reexporta o video e apaga toda a data. Como a edicao pode ter
mudado a velocidade e cortado trechos, a duracao nao serve de chave — mas o
que esta na tela continua sendo o mesmo. Entao comparamos quadros: para cada
video editado, procuramos o original cujo conteudo bate.

A comparacao usa dHash, uma assinatura de 64 bits por quadro: a imagem e
reduzida a 9x8 em tons de cinza e cada bit diz se um pixel e mais claro que
o vizinho da direita. Isso sobrevive a recompressao, mudanca de resolucao e
ajustes leves de cor.

Os originais sao lidos onde estiverem; nada e copiado.

Uso:
  python3 scripts/datar_por_originais.py --originais /Volumes/DJI/DCIM
  python3 scripts/datar_por_originais.py --originais ~/Downloads/crus --aplicar
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT_VIDEO = {".mov", ".mp4", ".m4v", ".avi", ".lrf"}

PASSO_ALVO = 0.5      # segundos entre quadros amostrados do video editado
PASSO_ORIGEM = 0.5    # segundos entre quadros amostrados do original
LADO = 16             # hash de 16x16 = 256 bits
LARGURA = LADO + 1    # uma coluna a mais: o dHash compara vizinhos
# Quem decide e a MARGEM sobre o segundo colocado: a distancia absoluta
# sobe muito com recompressao e correcao de cor, mas o concorrente errado
# sobe junto. Dois videos sem relacao ficam perto de 0.5.
LIMITE_BOM = 0.38     # acima disto nem o primeiro colocado convence
MARGEM_MINIMA = 0.07  # vantagem exigida sobre o segundo colocado


def assinaturas(caminho, passo):
    """Lista de dHashes (inteiros de 64 bits) amostrados ao longo do video."""
    # histeq achata diferenças de brilho, contraste e saturação, que é
    # justamente o que uma edição de cor introduz.
    cmd = ["ffmpeg", "-v", "error", "-i", caminho,
           "-vf", (f"fps=1/{passo},format=gray,histeq=strength=0.5,"
                   f"scale={LARGURA}:{LADO}"),
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    try:
        bruto = subprocess.run(cmd, capture_output=True, timeout=600).stdout
    except (subprocess.SubprocessError, OSError):
        return []

    tam = LARGURA * LADO
    quadros = []
    for i in range(0, len(bruto) - tam + 1, tam):
        q = bruto[i:i + tam]
        h = 0
        for linha in range(LADO):
            base = linha * LARGURA
            for col in range(LADO):
                h = (h << 1) | (1 if q[base + col] > q[base + col + 1] else 0)
        quadros.append(h)
    return quadros


BITS = LADO * LADO


def distancia(a, b):
    """Fracao de bits diferentes, de 0 (igual) a 1."""
    return bin(a ^ b).count("1") / BITS


def quando_gravou(caminho):
    """Instante de gravacao do original, pelas tags ou pelo nome."""
    saida = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", caminho],
        capture_output=True, text=True).stdout
    try:
        tags = json.loads(saida)["format"].get("tags", {})
    except (json.JSONDecodeError, KeyError):
        tags = {}
    for chave in ("com.apple.quicktime.creationdate", "creation_time"):
        if chave in tags:
            try:
                return datetime.fromisoformat(str(tags[chave]).replace("Z", "+00:00"))
            except ValueError:
                pass
    # DJI costuma gravar a data no nome: DJI_20260920143025_0003_D.MP4
    m = re.search(r"(20\d{2})(\d{2})(\d{2})[_-]?(\d{2})(\d{2})(\d{2})",
                  os.path.basename(caminho))
    if m:
        try:
            return datetime(*(int(g) for g in m.groups())).astimezone()
        except ValueError:
            pass
    try:
        st = os.stat(caminho)
        return datetime.fromtimestamp(
            getattr(st, "st_birthtime", None) or st.st_mtime, timezone.utc)
    except OSError:
        return None


def listar(pasta):
    achados = []
    for raiz, _, nomes in os.walk(pasta):
        for n in sorted(nomes):
            if n.startswith(".") or os.path.splitext(n)[1].lower() not in EXT_VIDEO:
                continue
            achados.append(os.path.join(raiz, n))
    return achados


def parear(alvos, origens):
    """Para cada video editado, acha o original de conteudo mais parecido."""
    print(f"Lendo {len(origens)} originais...")
    catalogo = []
    for i, p in enumerate(origens, 1):
        h = assinaturas(p, PASSO_ORIGEM)
        print(f"  [{i}/{len(origens)}] {os.path.basename(p):36s} {len(h):4d} quadros")
        if h:
            catalogo.append((p, h, quando_gravou(p)))

    print(f"\nComparando {len(alvos)} editados:")
    resultado, duvidosos = {}, []
    for p in alvos:
        marcas = assinaturas(p, PASSO_ALVO)
        nome = os.path.basename(p)
        if not marcas:
            duvidosos.append((nome, "nao consegui ler os quadros"))
            continue

        notas = []
        for origem, banco, data in catalogo:
            # para cada quadro do editado, o quadro mais parecido do original
            # para cada quadro do editado, o quadro mais parecido do
            # original; o terco inferior resume bem e tolera alguns ruins
            perto = sorted(min(distancia(m, b) for b in banco) for m in marcas)
            corte = max(1, len(perto) // 3)
            notas.append((sum(perto[:corte]) / corte, origem, data))
        notas.sort()

        melhor, segundo = notas[0], (notas[1] if len(notas) > 1 else None)
        margem = (segundo[0] - melhor[0]) if segundo else 1.0
        ok = melhor[0] <= LIMITE_BOM and margem >= MARGEM_MINIMA

        print(f"  {nome:28s} → {os.path.basename(melhor[1]):30s} "
              f"dif {melhor[0]:.3f}  margem {margem:.3f}  "
              f"{'ok' if ok else 'INCERTO'}")
        if ok and melhor[2]:
            resultado[nome] = melhor[2]
        else:
            duvidosos.append((nome, f"melhor palpite {os.path.basename(melhor[1])} "
                                    f"(dif {melhor[0]:.3f}, margem {margem:.3f})"))
    return resultado, duvidosos


def conferir_ordem(achados):
    """Confere se a ordem de exportacao bate com a ordem de gravacao.

    Os arquivos exportados costumam sair na mesma sequencia em que foram
    gravados. Se as datas encontradas respeitarem essa ordem, e um segundo
    indicio — independente da imagem — de que o pareamento esta certo.
    """
    if len(achados) < 3:
        return
    por_nome = sorted(achados.items())
    datas = [d for _, d in por_nome]
    inversoes = sum(1 for a, b in zip(datas, datas[1:]) if b < a)
    pares = len(datas) - 1
    print(f"\nConferencia de ordem: {pares - inversoes}/{pares} pares em sequencia", end="")
    if inversoes == 0:
        print(" — a ordem de exportacao bate com a de gravacao.")
    else:
        print(f" ({inversoes} fora de ordem).")
        print("  Fora de ordem nao e necessariamente erro, mas vale conferir:")
        for (na, da), (nb, db) in zip(por_nome, por_nome[1:]):
            if db < da:
                print(f"    {na} ({da:%H:%M}) vem depois de {nb} ({db:%H:%M})")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--originais", required=True,
                    help="pasta com os arquivos crus (lida no lugar, nada e copiado)")
    ap.add_argument("--alvos", default=os.path.join(RAIZ, "midias"),
                    help="pasta com os videos sem data (padrao: midias/)")
    ap.add_argument("--so-sem-data", action="store_true", default=True,
                    help="considerar apenas os videos que o build_media nao ancorou")
    ap.add_argument("--aplicar", action="store_true",
                    help="gravar o resultado em midias/_datas.json")
    args = ap.parse_args()

    if not os.path.isdir(args.originais):
        raise SystemExit(f"Pasta nao encontrada: {args.originais}")

    alvos = listar(args.alvos)
    origens = [p for p in listar(args.originais)
               if os.path.abspath(p) not in {os.path.abspath(a) for a in alvos}]
    if not alvos:
        raise SystemExit("Nenhum video em " + args.alvos)
    if not origens:
        raise SystemExit("Nenhum video em " + args.originais)

    achados, duvidosos = parear(alvos, origens)

    print(f"\n{len(achados)} pareados com confianca:")
    for nome, data in sorted(achados.items(), key=lambda kv: kv[1]):
        print(f"  {nome:30s} {data:%d/%m %H:%M:%S %z}")
    conferir_ordem(achados)
    if duvidosos:
        print(f"\n{len(duvidosos)} sem certeza:")
        for nome, motivo in duvidosos:
            print(f"  {nome}: {motivo}")

    if not args.aplicar:
        print("\n(nada foi gravado — repita com --aplicar)")
        return

    destino = os.path.join(RAIZ, "midias", "_datas.json")
    tabela = {}
    if os.path.exists(destino):
        with open(destino, encoding="utf-8") as fh:
            tabela = json.load(fh)
    tabela.update({n: d.isoformat() for n, d in achados.items()})
    with open(destino, "w", encoding="utf-8") as fh:
        json.dump(tabela, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"\n{destino} agora tem {len(tabela)} datas.")
    print("Rode: python3 scripts/build_media.py")


if __name__ == "__main__":
    main()
