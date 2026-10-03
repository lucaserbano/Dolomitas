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
RE_EXPORTADO = re.compile(r"^(\d{13})\.(MOV|JPG)$", re.I)
# Cartao da Osmo: CAM_AAAAMMDDHHMMSS_NNNN_D.EXT, hora do relogio da camera.
RE_CARTAO = re.compile(r"^CAM_(\d{14})_(\d{4})_D\.(\w+)$", re.I)
RE_WHATSAPP = re.compile(r"^PHOTO-(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})")


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


def tira_do_video(caminho, instantes, larg, alt):
    """Junta varios quadros do video numa so imagem, empilhados."""
    from PIL import Image
    quadros = []
    for t in instantes:
        bruto = rodar(["ffmpeg", "-v", "quiet", "-ss", f"{t:.2f}", "-i", caminho,
                       "-map", "0:v:0", "-frames:v", "1", "-vf",
                       f"scale={larg}:{alt}", "-f", "image2", "-c:v", "mjpeg",
                       "-"])
        if bruto:
            try:
                quadros.append(Image.open(io.BytesIO(bruto)).convert("RGB"))
            except Exception:
                pass
    if not quadros:
        return None
    tira = Image.new("RGB", (larg, alt * len(quadros)))
    for i, q in enumerate(quadros):
        tira.paste(q, (0, i * alt))
    return _jpeg(tira)


def tira_da_foto(caminho, larg, alt):
    from PIL import Image, ImageOps
    try:
        with Image.open(caminho) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")
            img = ImageOps.fit(img, (larg, alt), Image.LANCZOS)
            return _jpeg(img)
    except Exception as erro:
        print(f"    ! {os.path.basename(caminho)}: {erro}")
        return None


def exif_quando(caminho):
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

def coletar(args, dia):
    data_cartao = dia["data"].replace("-", "")
    exportados, whatsapp, canon = [], [], []

    print("Exportados do Mimo:")
    for nome in sorted(os.listdir(args.exportados)):
        caminho = os.path.join(args.exportados, nome)
        m = RE_EXPORTADO.match(nome)
        if m:
            video = m.group(2).upper() == "MOV"
            dur = duracao(caminho) if video else 0.0
            tira = (tira_do_video(caminho, [dur * 0.2, dur * 0.75], 132, 234)
                    if video else tira_da_foto(caminho, 132, 234))
            exportados.append({"nome": nome, "video": video,
                               "dur": round(dur, 1), "img": tira})
            print(f"  {len(exportados):3d}  {nome}  {dur:5.1f}s")
            continue
        if RE_WHATSAPP.match(nome):
            whatsapp.append({"nome": nome, "img": tira_da_foto(caminho, 190, 190)})
            continue
        if nome.lower().endswith((".jpg", ".jpeg")):
            quando = exif_quando(caminho)
            if quando and quando.strftime("%Y%m%d") == data_cartao:
                canon.append({"nome": nome, "iso": quando.isoformat(),
                              "hora": quando.strftime("%H:%M"),
                              "ctx": contexto(dia, quando),
                              "img": tira_da_foto(caminho, 190, 190)})

    canon.sort(key=lambda c: c["iso"])
    whatsapp.sort(key=lambda w: w["nome"])

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
        tira = (tira_do_video(caminho, [dur * 0.1, dur * 0.5, dur * 0.9], 260, 130)
                if video else tira_da_foto(caminho, 260, 195))
        crus.append({"id": seq, "nome": nome, "video": video,
                     "dur": round(dur, 1),
                     "relogio": relogio.strftime("%H:%M"),
                     "iso": relogio.isoformat(),
                     "hora": real.strftime("%H:%M"),
                     "ctx": contexto(dia, real), "img": tira})
        print(f"  {seq}  {relogio:%H:%M} -> {real:%H:%M}  "
              f"{'video' if video else 'foto '}  {dur:5.1f}s")

    return exportados, crus, whatsapp, canon


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
    exportados, crus, whatsapp, canon = coletar(args, dia)

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
        "whatsapp": whatsapp, "canon": canon,
    }
    saida = args.saida or os.path.join(RAIZ, "pareamento")
    modelo_path = os.path.join(RAIZ, "scripts", "parear_osmo.html")
    with open(modelo_path, encoding="utf-8") as fh:
        modelo = fh.read().replace("__DIA__", str(dia["n"]))
    escrever(saida, dados, modelo)


if __name__ == "__main__":
    principal()
