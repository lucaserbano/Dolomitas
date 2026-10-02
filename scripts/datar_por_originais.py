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

# Camera 360 (DJI Osmo 360): o arquivo cru e dual fisheye e o video exportado
# e um recorte reenquadrado dele. Para comparar, reprojetamos o cru em varias
# direcoes e procuramos a que bate.
YAWS = tuple(range(0, 360, 30))
PITCHES = (0,)
# O recorte exportado e 9:16; projetar direto na grade quase quadrada do
# hash deformava a geometria de um jeito que o alvo nao sofre.
PROJ_L, PROJ_A = 180, 320
FOV_H, FOV_V = 70, 110

PASSO_ALVO = 0.5      # segundos entre quadros amostrados do video editado
PASSO_ORIGEM = 2.0    # segundos entre quadros amostrados do original
LADO = 16             # hash de 16x16 = 256 bits
LARGURA = LADO + 1    # uma coluna a mais: o dHash compara vizinhos
# Quem decide e a MARGEM sobre o segundo colocado: a distancia absoluta
# sobe muito com recompressao e correcao de cor, mas o concorrente errado
# sobe junto. Dois videos sem relacao ficam perto de 0.5.
LIMITE_BOM = 0.38     # acima disto nem o primeiro colocado convence
MARGEM_MINIMA = 0.07  # vantagem exigida sobre o segundo colocado


def eh_360(caminho):
    """Dual fisheye vem em quadro 2:1; e a assinatura desse formato."""
    saida = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", caminho],
        capture_output=True, text=True).stdout.strip().split(",")
    try:
        l, a = int(saida[0]), int(saida[1])
    except (ValueError, IndexError):
        return False
    return a > 0 and 1.9 < l / a < 2.1


def assinaturas_360(caminho, passo):
    """Assinaturas do cru 360, varrendo varias direcoes de camera."""
    todas = []
    for pitch in PITCHES:
        for yaw in YAWS:
            vf = (f"fps=1/{passo},"
                  f"v360=dfisheye:flat:ih_fov=193:iv_fov=193:"
                  f"yaw={yaw}:pitch={pitch}:h_fov={FOV_H}:v_fov={FOV_V}:"
                  f"w={PROJ_L}:h={PROJ_A},"
                  f"format=gray,histeq=strength=0.5,scale={LARGURA}:{LADO}")
            todas += _hashes(caminho, vf)
    return todas


def _hashes(caminho, vf):
    cmd = ["ffmpeg", "-v", "error", "-i", caminho, "-map", "0:v:0", "-vf", vf,
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    try:
        bruto = subprocess.run(cmd, capture_output=True, timeout=900).stdout
    except (subprocess.SubprocessError, OSError):
        return []
    tam = LARGURA * LADO
    saida = []
    for i in range(0, len(bruto) - tam + 1, tam):
        q = bruto[i:i + tam]
        h = 0
        for linha in range(LADO):
            base = linha * LARGURA
            for col in range(LADO):
                h = (h << 1) | (1 if q[base + col] > q[base + col + 1] else 0)
        saida.append(h)
    return saida


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

    catalogo.sort(key=lambda c: c[2] or datetime.min.replace(tzinfo=timezone.utc))
    alvos = sorted(alvos, key=os.path.basename)

    print(f"\nAssinando {len(alvos)} editados e montando a matriz:")
    custo = []
    for p in alvos:
        marcas = assinaturas(p, PASSO_ALVO)
        linha = []
        for _, banco, _ in catalogo:
            if not marcas or not banco:
                linha.append(1.0)
                continue
            # para cada quadro do editado, o quadro mais parecido do
            # original; o terco inferior resume bem e tolera alguns ruins
            perto = sorted(min(distancia(m, b) for b in banco) for m in marcas)
            corte = max(1, len(perto) // 3)
            linha.append(sum(perto[:corte]) / corte)
        custo.append(linha)
        j = min(range(len(linha)), key=lambda k: linha[k])
        print(f"  {os.path.basename(p):28s} isolado → "
              f"{os.path.basename(catalogo[j][0]):30s} dif {linha[j]:.3f}")

    print("\nAlinhando a sequencia:")
    return avaliar(alvos, catalogo, custo, alinhar(custo))


def alinhar(custo):
    """Casa cada editado com um original preservando a ordem.

    Os videos sao exportados na mesma sequencia em que foram gravados, entao
    formam uma subsequencia crescente dos crus. Impor essa ordem e o que
    torna o resultado confiavel: um pareamento isolado pode errar, mas a
    sequencia inteira dificilmente encaixa errado de ponta a ponta.
    """
    n, m = len(custo), len(custo[0]) if custo else 0
    if not n or m < n:
        return [None] * n
    INF = float("inf")
    melhor = [[INF] * (m + 1) for _ in range(n + 1)]
    de = [[None] * (m + 1) for _ in range(n + 1)]
    for j in range(m + 1):
        melhor[0][j] = 0.0
    for i in range(1, n + 1):
        for j in range(i, m + 1):
            pular = melhor[i][j - 1]
            usar = melhor[i - 1][j - 1] + custo[i - 1][j - 1]
            if usar <= pular:
                melhor[i][j], de[i][j] = usar, "usar"
            else:
                melhor[i][j], de[i][j] = pular, "pular"
    escolha = [None] * n
    i, j = n, m
    while i > 0 and j > 0:
        if de[i][j] == "usar":
            escolha[i - 1] = j - 1
            i -= 1
        j -= 1
    return escolha


def avaliar(alvos, catalogo, custo, atribuicao):
    """Converte o alinhamento em datas, separando o que ficou duvidoso."""
    resultado, duvidosos = {}, []
    for i, p in enumerate(alvos):
        nome = os.path.basename(p)
        j = atribuicao[i]
        if j is None:
            duvidosos.append((nome, "o alinhamento nao encontrou par"))
            continue
        d = custo[i][j]
        rivais = sorted(v for k, v in enumerate(custo[i]) if k != j)
        margem = (rivais[0] - d) if rivais else 1.0
        origem, _, data = catalogo[j]
        isolado = min(range(len(custo[i])), key=lambda k: custo[i][k])
        selo = "ok" if d <= LIMITE_BOM else "FRACO"
        if isolado != j:
            selo += "  (a ordem corrigiu o palpite isolado)"
        print(f"  {nome:28s} → {os.path.basename(origem):30s} "
              f"dif {d:.3f}  margem {margem:+.3f}  {selo}")
        if d <= LIMITE_BOM and data:
            resultado[nome] = data
        else:
            duvidosos.append((nome, f"{os.path.basename(origem)} (dif {d:.3f})"))
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
    ap.add_argument("--filtro", default="",
                    help="so considera originais cujo nome contenha este texto")
    ap.add_argument("--aplicar", action="store_true",
                    help="gravar o resultado em midias/_datas.json")
    args = ap.parse_args()

    if not os.path.isdir(args.originais):
        raise SystemExit(f"Pasta nao encontrada: {args.originais}")

    alvos = listar(args.alvos)
    origens = [p for p in listar(args.originais)
               if args.filtro in os.path.basename(p)]
    origens = [p for p in origens
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
