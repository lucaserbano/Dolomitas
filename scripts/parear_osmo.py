#!/usr/bin/env python3
"""
Monta a pagina de pareamento manual dos arquivos que perderam a data.

O DJI Mimo reexporta os clipes da Osmo 360 e apaga a data de gravacao: o nome
vira o instante da exportacao e nao sobra vestigio da captura. O cartao, esse
sim, guarda a hora no nome de cada clipe. Cruzar imagem contra imagem nao
funciona com fonte 360 — o cru e um par de olhos de peixe e o exportado e um
recorte reenquadrado dele — entao quem decide e o olho.

Esta pagina poe os exportados de um lado, os clipes do cartao do outro, e
devolve o trecho de midias/_datas.json pronto para colar.

Na mesma pagina vao as fotos do WhatsApp. O nome delas marca quando a mensagem
chegou, nao quando a foto foi feita: as do dia 3 chegaram todas a noite, ja no
refugio. Para essas o referencial sao as fotos da Canon, que tem EXIF.

Uso:
  python3 scripts/parear_osmo.py --dia 3 \
      --exportados "midias/D3 Fanes-Valparola" \
      --cartao /Volumes/Untitled/DCIM/CAM_001
"""

import argparse
import base64
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIAS = os.path.join(RAIZ, "docs", "data", "days.json")
TABELA = os.path.join(RAIZ, "midias", "_datas.json")

FUSO = timezone(timedelta(hours=2))          # CEST, o dos Dolomitas em setembro

# Exportado do Mimo: o nome e o instante da exportacao, em milissegundos.
# Nas etapas 5 e 6 o aplicativo passou a exportar como D5_0000_V1-0001.mov;
# por isso qualquer video sem hora de captura tambem entra como exportado.
RE_EXPORTADO = re.compile(r"^(\d{13})\.(MOV|JPG)$", re.I)
# Cartao da Osmo: CAM_AAAAMMDDHHMMSS_NNNN_D.EXT, hora do relogio da camera.
RE_CARTAO = re.compile(r"^CAM_(\d{14})_(\d{4})_D\.(\w+)$", re.I)
RE_WHATSAPP = re.compile(r"^PHOTO-(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})")

EXT_FOTO = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff"}
EXT_VIDEO = {".mov", ".mp4", ".m4v"}


# ---------------------------------------------------------------- utilidades

def rodar(cmd):
    r = subprocess.run(cmd, capture_output=True)
    return r.stdout if r.returncode == 0 else b""


def duracao(caminho):
    saida = rodar(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                   "-of", "default=nw=1:nk=1", caminho])
    try:
        return float(saida.strip())
    except ValueError:
        return 0.0


def _jpeg(img, qualidade=72):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=qualidade, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


# O cru da Osmo 360 e um par de olhos de peixe lado a lado. Encolhido vira
# duas bolhas em que nao se enxerga nada; o v360 do ffmpeg desentorta para
# equirretangular. O corte vertical joga fora o zenite, que e so ceu, e o
# nadir, que e o bastao — sobram os 56 graus para cima e para baixo, onde
# estao os picos e a trilha.
ALTURA_EQUI = 480
FAIXA_EQUI = 300
FILTRO_360 = (f"v360=dfisheye:e:ih_fov=193:iv_fov=193:w={ALTURA_EQUI * 2}:"
              f"h={ALTURA_EQUI},"
              f"crop={ALTURA_EQUI * 2}:{FAIXA_EQUI}:0:{(ALTURA_EQUI - FAIXA_EQUI) // 2}")


def tira_do_video(caminho, instantes, larg, alt, antes="", lado_a_lado=False):
    """Junta varios quadros do video numa so imagem.

    `antes` e um filtro aplicado antes da escala — e por onde entra o v360.
    """
    from PIL import Image
    filtro = f"{antes}," if antes else ""
    quadros = []
    for t in instantes:
        bruto = rodar(["ffmpeg", "-v", "quiet", "-ss", f"{t:.2f}", "-i", caminho,
                       "-map", "0:v:0", "-frames:v", "1", "-vf",
                       f"{filtro}scale={larg}:{alt}", "-f", "image2",
                       "-c:v", "mjpeg", "-"])
        if bruto:
            try:
                quadros.append(Image.open(io.BytesIO(bruto)).convert("RGB"))
            except Exception:
                pass
    if not quadros:
        return None
    n = len(quadros)
    tira = Image.new("RGB", (larg * n, alt) if lado_a_lado else (larg, alt * n))
    for i, q in enumerate(quadros):
        tira.paste(q, (i * larg, 0) if lado_a_lado else (0, i * alt))
    return _jpeg(tira)


def foto_equirect(caminho, larg, alt):
    """Foto 360 do cartao: ja vem costurada, so falta tirar ceu e chao."""
    from PIL import Image, ImageOps
    try:
        with Image.open(caminho) as img:
            img = img.convert("RGB")
            faixa = round(img.height * FAIXA_EQUI / ALTURA_EQUI)
            topo = (img.height - faixa) // 2
            img = img.crop((0, topo, img.width, topo + faixa))
            return _jpeg(ImageOps.fit(img, (larg, alt), Image.LANCZOS))
    except Exception as erro:
        print(f"    ! {os.path.basename(caminho)}: {erro}")
        return None


def tira_da_foto(caminho, larg, alt):
    from PIL import Image, ImageOps
    temporario = None
    if os.path.splitext(caminho)[1].lower() in (".heic", ".heif"):
        # A Pillow nao le HEIC sem plugin; o sips ja vem no macOS.
        temporario = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "_heic.tmp.jpg")
        rodar(["sips", "-s", "format", "jpeg", "-Z", str(max(larg, alt) * 2),
               caminho, "--out", temporario])
        if not os.path.exists(temporario):
            print(f"    ! sips nao converteu {os.path.basename(caminho)}")
            return None
        caminho = temporario
    try:
        with Image.open(caminho) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")
            img = ImageOps.fit(img, (larg, alt), Image.LANCZOS)
            return _jpeg(img)
    except Exception as erro:
        print(f"    ! {os.path.basename(caminho)}: {erro}")
        return None
    finally:
        if temporario and os.path.exists(temporario):
            os.remove(temporario)


def quando_do_arquivo(caminho, ehvideo):
    """Instante da captura, no fuso dos Dolomitas, ou None se nao houver.

    Quatro fontes, na ordem em que merecem credito: o EXIF da foto, os tags do
    video, o sips — que le o HEIC que a Pillow nao abre — e o Spotlight.

    O sips vem antes do `mdls` porque devolve a hora como ela esta no arquivo,
    sem fuso, enquanto o Spotlight carimba nela o fuso desta maquina: cinco
    horas de erro numa foto feita na Europa e copiada no Brasil. E o `mdls`
    ainda depende do indice, que nao existe em disco externo.
    """
    quando = None if ehvideo else _exif_quando(caminho)
    if quando is None and ehvideo:
        quando = _ffprobe_quando(caminho)
    if quando is None:
        quando = _sips_quando(caminho)
    if quando is None:
        quando = _mdls_quando(caminho)
    return quando


EXT_SIPS = {".heic", ".heif"}


def _sips_quando(caminho):
    """Data de captura de um HEIC pelo sips, ja no fuso dos Dolomitas."""
    if os.path.splitext(caminho)[1].lower() not in EXT_SIPS:
        return None
    saida = rodar(["sips", "-g", "creation", caminho]).decode("utf-8", "ignore")
    m = re.search(r"creation:\s*(\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2})", saida)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y:%m:%d %H:%M:%S").replace(tzinfo=FUSO)
    except ValueError:
        return None


def _ffprobe_quando(caminho):
    saida = rodar(["ffprobe", "-v", "quiet", "-print_format", "json",
                   "-show_format", "-show_streams", caminho])
    if not saida:
        return None
    try:
        dados = json.loads(saida)
    except json.JSONDecodeError:
        return None
    tags = dict(dados.get("format", {}).get("tags", {}))
    for fluxo in dados.get("streams", []):
        for k, v in (fluxo.get("tags") or {}).items():
            tags.setdefault(k, v)
    # creation_time e reescrita ao copiar; a chave da Apple guarda a captura.
    for chave in ("com.apple.quicktime.creationdate", "creation_time"):
        if chave in tags:
            try:
                return datetime.fromisoformat(
                    str(tags[chave]).strip().replace("Z", "+00:00")
                ).astimezone(FUSO)
            except ValueError:
                continue
    return None


def _mdls_quando(caminho):
    saida = rodar(["mdls", "-name", "kMDItemContentCreationDate", "-raw", caminho])
    try:
        texto = saida.decode().strip()
        return datetime.strptime(texto, "%Y-%m-%d %H:%M:%S %z").astimezone(FUSO)
    except (UnicodeDecodeError, ValueError):
        return None


def _exif_quando(caminho):
    """DateTimeOriginal, ja no fuso dos Dolomitas."""
    from PIL import Image, ExifTags
    try:
        with Image.open(caminho) as img:
            bruto = img.getexif().get_ifd(0x8769)
    except Exception:
        return None
    tags = {ExifTags.TAGS.get(k, k): v for k, v in bruto.items()}
    texto = tags.get("DateTimeOriginal")
    if not texto:
        return None
    try:
        dt = datetime.strptime(str(texto).strip(), "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None
    desvio = tags.get("OffsetTimeOriginal")
    if desvio:
        sinal = -1 if str(desvio).strip().startswith("-") else 1
        h, m = str(desvio).strip().lstrip("+-").split(":")
        dt = dt.replace(tzinfo=timezone(
            sinal * timedelta(hours=int(h), minutes=int(m))))
    else:
        dt = dt.replace(tzinfo=FUSO)
    return dt.astimezone(FUSO)


# ------------------------------------------------------------------- trajeto

def carregar_dia(n):
    with open(DIAS, encoding="utf-8") as fh:
        for d in json.load(fh)["dias"]:
            if d["n"] == n:
                return d
    raise SystemExit(f"dia {n} nao esta em {DIAS}")


def janela_da_travessia(folga_horas=14):
    """Do inicio do primeiro dia ao fim do ultimo, com folga para as noites.

    Serve de peneira contra data que nao e de captura. O mdls devolve a data
    do sistema de arquivos quando nao ha metadado nenhum — uma foto do
    WhatsApp salva com outro nome sai dali com a data em que foi copiada.
    Qualquer instante fora desta janela e lixo, nao hora de captura.
    """
    with open(DIAS, encoding="utf-8") as fh:
        dias = json.load(fh)["dias"]
    inicios = [d["resumo"]["inicioUTC"] for d in dias]
    fins = [d["resumo"]["inicioUTC"] + d["resumo"]["dur"] for d in dias]
    folga = timedelta(hours=folga_horas)
    return (datetime.fromtimestamp(min(inicios), FUSO) - folga,
            datetime.fromtimestamp(max(fins), FUSO) + folga)


def tabela_existente():
    """O que ja esta datado, nas duas secoes, para a pagina nao apagar etapas
    anteriores ao devolver o arquivo inteiro."""
    if not os.path.exists(TABELA):
        return {"_relogio_da_camera": {}, "_hora_real": {}}
    with open(TABELA, encoding="utf-8") as fh:
        bruto = json.load(fh)
    relogio = dict(bruto.get("_relogio_da_camera", {}))
    # Formato antigo: os nomes ficavam soltos na raiz, todos em hora de camera.
    for nome, valor in bruto.items():
        if not nome.startswith("_"):
            relogio[nome] = valor
    return {"_relogio_da_camera": relogio,
            "_hora_real": dict(bruto.get("_hora_real", {}))}


def contexto(dia, quando):
    """Onde a caminhada estava naquele instante."""
    rel = quando.timestamp() - dia["resumo"]["inicioUTC"]
    ts = dia["t"]
    if rel < ts[0] or rel > ts[-1]:
        return {"rel": rel, "fora": True}
    lo, hi = 0, len(ts) - 1
    while lo < hi:
        meio = (lo + hi) // 2
        if ts[meio] < rel:
            lo = meio + 1
        else:
            hi = meio
    return {"rel": rel, "ele": round(dia["ele"][lo]),
            "km": round(dia["dist"][lo] / 1000, 1),
            "ganho": round(dia["gain"][lo])}


# -------------------------------------------------------------- coleta

def miniatura(caminho, ehvideo, larg, alt):
    return (tira_do_video(caminho, [duracao(caminho) * 0.3], larg, alt)
            if ehvideo else tira_da_foto(caminho, larg, alt))


def coletar(args, dia):
    data_cartao = dia["data"].replace("-", "")
    comeco, fim = janela_da_travessia()
    exportados, sem_data, referencia, outros_dias = [], [], [], []

    print("Exportados do Mimo:")
    for nome in sorted(os.listdir(args.exportados)):
        if nome.startswith("."):
            continue
        caminho = os.path.join(args.exportados, nome)
        ext = os.path.splitext(nome)[1].lower()
        if ext not in EXT_FOTO | EXT_VIDEO:
            continue
        ehvideo = ext in EXT_VIDEO
        # Nome do WhatsApp marca a chegada da mensagem, nao a captura: nunca
        # serve de referencia e sempre precisa de hora dada a mao.
        whatsapp = bool(RE_WHATSAPP.match(nome))

        exportado = bool(RE_EXPORTADO.match(nome))
        if not exportado and ehvideo and not whatsapp:
            # O Mimo ja trocou de padrao de nome mais de uma vez — nas etapas 5
            # e 6 os clipes sairam como D5_0000_V1-0001.mov. O que define um
            # exportado nao e o nome: e ser video sem hora de captura, e para
            # video o cartao e o unico lugar onde essa hora sobrou.
            q = quando_do_arquivo(caminho, True)
            exportado = q is None or not (comeco <= q <= fim)

        if exportado:
            dur = duracao(caminho) if ehvideo else 0.0
            tira = (tira_do_video(caminho, [dur * 0.2, dur * 0.75], 190, 338,
                                  lado_a_lado=True)
                    if ehvideo else tira_da_foto(caminho, 190, 338))
            exportados.append({"nome": nome, "video": ehvideo,
                               "dur": round(dur, 1), "img": tira})
            print(f"  {len(exportados):3d}  {nome}  {dur:5.1f}s")
            continue

        quando = None if whatsapp else quando_do_arquivo(caminho, ehvideo)
        if quando is not None and not (comeco <= quando <= fim):
            print(f"    {nome}: {quando:%d/%m/%Y %H:%M} esta fora da travessia "
                  f"— nao e hora de captura, vai para a datacao a mao")
            quando = None

        if quando is None:
            sem_data.append({"nome": nome, "video": ehvideo,
                             "img": miniatura(caminho, ehvideo, 220, 220)})
        elif quando.strftime("%Y%m%d") == data_cartao:
            referencia.append({"nome": nome, "video": ehvideo,
                               "iso": quando.isoformat(),
                               "hora": quando.strftime("%H:%M"),
                               "ctx": contexto(dia, quando),
                               "img": miniatura(caminho, ehvideo, 220, 220)})
        else:
            outros_dias.append((nome, quando))

    referencia.sort(key=lambda c: c["iso"])
    sem_data.sort(key=lambda w: w["nome"])

    print(f"\n{len(referencia)} midias com hora propria servem de referencia; "
          f"{len(sem_data)} precisam de hora.")
    if outros_dias:
        print("\nNesta pasta, mas de outro dia (vao para a etapa certa "
              "sozinhas, pelo horario):")
        for nome, quando in sorted(outros_dias, key=lambda x: x[1]):
            print(f"  {nome}: {quando:%d/%m %H:%M}")

    print(f"\nClipes do cartao em {dia['data']}:")
    crus, vistos = [], set()
    for nome in sorted(os.listdir(args.cartao)):
        m = RE_CARTAO.match(nome)
        if not m or not m.group(1).startswith(data_cartao):
            continue
        seq, ext = m.group(2), m.group(3).upper()
        if seq in vistos or ext == "OSV":      # OSV e o cru do LRF; DNG, da JPG
            continue
        if ext == "DNG" and os.path.exists(
                os.path.join(args.cartao, nome[:-3] + "JPG")):
            continue
        vistos.add(seq)
        caminho = os.path.join(args.cartao, nome)
        relogio = datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=FUSO)
        real = relogio + timedelta(minutes=args.ajuste)
        video = ext == "LRF"
        dur = duracao(caminho) if video else 0.0
        tira = (tira_do_video(caminho, [dur * 0.1, dur * 0.5, dur * 0.9],
                              520, 162, antes=FILTRO_360)
                if video else foto_equirect(caminho, 520, 162))
        crus.append({"id": seq, "nome": nome, "video": video,
                     "dur": round(dur, 1),
                     "relogio": relogio.strftime("%H:%M"),
                     "iso": relogio.isoformat(),
                     "hora": real.strftime("%H:%M"),
                     "ctx": contexto(dia, real), "img": tira})
        print(f"  {seq}  {relogio:%H:%M} -> {real:%H:%M}  "
              f"{'video' if video else 'foto '}  {dur:5.1f}s")

    return exportados, crus, sem_data, referencia


# -------------------------------------------------------------- pagina

def escrever(destino, dados, modelo):
    os.makedirs(destino, exist_ok=True)
    with open(os.path.join(destino, "dados.js"), "w", encoding="utf-8") as fh:
        fh.write("window.DADOS = ")
        json.dump(dados, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";\n")
    with open(os.path.join(destino, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(modelo)
    tam = sum(os.path.getsize(os.path.join(destino, f))
              for f in os.listdir(destino)) / 1e6
    print(f"\n{destino}  ({tam:.1f} MB)")


def principal():
    p = argparse.ArgumentParser()
    p.add_argument("--dia", type=int, required=True)
    p.add_argument("--exportados", required=True)
    p.add_argument("--cartao", required=True)
    p.add_argument("--ajuste", type=float, default=-54,
                   help="minutos a somar ao relogio da camera (padrao: -54)")
    p.add_argument("--saida", default=None)
    args = p.parse_args()

    if not os.path.isdir(args.cartao):
        raise SystemExit(f"cartao nao encontrado: {args.cartao}")
    dia = carregar_dia(args.dia)
    exportados, crus, sem_data, referencia = coletar(args, dia)

    dados = {
        "dia": {"n": dia["n"], "data": dia["data"], "de": dia["de"],
                "para": dia["para"],
                "inicio": datetime.fromtimestamp(
                    dia["resumo"]["inicioUTC"], FUSO).strftime("%H:%M"),
                "fim": datetime.fromtimestamp(
                    dia["resumo"]["inicioUTC"] + dia["resumo"]["dur"],
                    FUSO).strftime("%H:%M")},
        "ajuste": args.ajuste,
        "existente": tabela_existente(),
        "exportados": exportados, "crus": crus,
        "semData": sem_data, "referencia": referencia,
    }
    saida = args.saida or os.path.join(RAIZ, "pareamento")
    modelo_path = os.path.join(RAIZ, "scripts", "parear_osmo.html")
    with open(modelo_path, encoding="utf-8") as fh:
        modelo = fh.read().replace("__DIA__", str(dia["n"]))
    escrever(saida, dados, modelo)


if __name__ == "__main__":
    principal()
