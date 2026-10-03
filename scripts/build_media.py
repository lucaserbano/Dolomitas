#!/usr/bin/env python3
"""
Ancora as fotos e videos de midias/ no trajeto e gera site/data/media.json.

Cada arquivo e posicionado pelo horario em que foi capturado, cruzado com a
serie temporal do dia correspondente — mais confiavel que o GPS da propria
foto, que falha entre paredes de rocha. O GPS do arquivo serve de conferencia.

Roda sem erro com a pasta vazia: o site funciona sem midias e este script
pode ser executado de novo a cada lote que chegar.

Uso:  python3 scripts/build_media.py [--fuso +02:00] [--forcar]
                                    [--crf 26] [--altura 1080]
                                    [--videos-em URL | --videos-aqui]
"""

import json
import math
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_MIDIAS = os.path.join(RAIZ, "midias")
DIR_DADOS = os.path.join(RAIZ, "docs", "data")
DIR_SAIDA = os.path.join(RAIZ, "docs", "media")
# Os videos podem morar fora do repositorio. Quando isso esta configurado,
# eles sao convertidos para ca e esta pasta e que vai para o R2/B2.
DIR_VIDEOS = os.path.join(RAIZ, "videos_para_subir")
CONFIG = os.path.join(RAIZ, "scripts", "config.json")

# Alguns aplicativos reexportam o arquivo e apagam todo vestigio da data de
# captura — o DJI Mimo faz isso. Para esses casos, este arquivo mapeia o nome
# do arquivo ao instante real de gravacao e tem prioridade sobre tudo.
DATAS_MANUAIS = os.path.join(RAIZ, "midias", "_datas.json")

EXT_FOTO = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp"}
EXT_VIDEO = {".mov", ".mp4", ".m4v", ".avi"}

LARGURA_MAX = 2000
LARGURA_MINIATURA = 480
ALTURA_MAX_VIDEO = 1080
QUALIDADE_FOTO = 80       # WebP: ~40% menor que JPEG na mesma qualidade visual
QUALIDADE_MINIATURA = 74
CRF_VIDEO = 28            # maior = menor arquivo; 28 serve bem a fonte 4K

# O GitHub Pages recomenda ate 1 GB por site e bloqueia arquivos acima de
# 100 MB. Avisamos bem antes de chegar la.
LIMITE_ARQUIVO_MB = 60
LIMITE_TOTAL_MB = 700

# As fotos foram feitas nos Dolomitas em setembro: horario de verao da Europa
# Central. Usado so quando o arquivo nao declara o proprio fuso.
FUSO_PADRAO = timezone(timedelta(hours=2))


# ------------------------------------------------------------- metadados

def _rodar(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return r.stdout if r.returncode == 0 else ""
    except (subprocess.SubprocessError, OSError):
        return ""


def _graus(valor, ref):
    """Converte coordenada EXIF (grau, minuto, segundo) em decimal."""
    try:
        d = float(valor[0]) + float(valor[1]) / 60 + float(valor[2]) / 3600
    except (TypeError, IndexError, ValueError, ZeroDivisionError):
        return None
    if ref in ("S", "W"):
        d = -d
    return d


_datas_manuais = None


def preservar_etapas_antigas(itens):
    """Mantem no media.json o que ja foi publicado e saiu de midias/.

    As midias originais sao pesadas e vao sendo retiradas da pasta etapa a
    etapa, enquanto os derivados ficam em docs/media/ para sempre. Sem isto,
    rodar o script depois de esvaziar midias/ apagaria do mapa as etapas
    anteriores. A miniatura e a prova de que a midia continua publicada.
    """
    caminho = os.path.join(DIR_DADOS, "media.json")
    if not os.path.exists(caminho):
        return 0
    try:
        with open(caminho, encoding="utf-8") as fh:
            antigas = json.load(fh).get("midias", [])
    except (json.JSONDecodeError, OSError):
        return 0

    conhecidos = {m["id"] for m in itens}
    guardadas = 0
    for m in antigas:
        if m.get("id") in conhecidos:
            continue
        thumb = os.path.join(RAIZ, "docs", m.get("thumb", ""))
        if m.get("thumb") and os.path.exists(thumb):
            itens.append(m)
            guardadas += 1
    return guardadas


def meta_por_tabela(caminho):
    """Data vinda de midias/_datas.json, quando o arquivo nao tem nenhuma.

    A tabela tem duas secoes, porque as datas nao vem todas da mesma fonte:

    _relogio_da_camera  horas lidas do nome do clipe no cartao. O relogio da
                        camera pode estar adiantado ou atrasado, e so estas
                        andam com _ajuste_minutos.
    _hora_real          horas ja conferidas, de outra fonte — as fotos do
                        WhatsApp, por exemplo, cuja hora veio das fotos da
                        Canon. Nao se mexe nelas.

    Nomes soltos na raiz, do formato antigo, contam como relogio de camera.
    """
    global _datas_manuais
    if _datas_manuais is None:
        _datas_manuais = {}
        if os.path.exists(DATAS_MANUAIS):
            try:
                with open(DATAS_MANUAIS, encoding="utf-8") as fh:
                    bruto = json.load(fh)
            except json.JSONDecodeError as erro:
                raise SystemExit(f"{DATAS_MANUAIS} invalido: {erro}")
            ajuste = timedelta(minutes=float(bruto.get("_ajuste_minutos", 0)))
            se_camera = dict(bruto.get("_relogio_da_camera", {}))
            se_camera.update({n: t for n, t in bruto.items()
                              if not n.startswith("_")})
            if ajuste and se_camera:
                print(f"  (ajuste de {ajuste.total_seconds() / 60:+.0f} min "
                      f"aplicado ao relogio da camera)")
            for secao, desloca in ((se_camera, ajuste),
                                   (bruto.get("_hora_real", {}), timedelta())):
                for nome, texto in secao.items():
                    try:
                        _datas_manuais[nome] = datetime.fromisoformat(
                            str(texto).replace("Z", "+00:00")) + desloca
                    except ValueError:
                        print(f"    ! data invalida para {nome}: {texto!r}")
            if _datas_manuais:
                print(f"  ({len(_datas_manuais)} datas lidas de _datas.json)")
    return _datas_manuais.get(os.path.basename(caminho)), None


def meta_por_pillow(caminho):
    """EXIF de imagens que a Pillow consegue abrir (JPEG, PNG, TIFF, WebP)."""
    try:
        from PIL import Image, ExifTags
    except ImportError:
        return None, None
    try:
        with Image.open(caminho) as img:
            exif = img.getexif()
            if not exif:
                return None, None
            tags = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
            bruto = exif.get_ifd(0x8769)
            tags.update({ExifTags.TAGS.get(k, k): v for k, v in bruto.items()})

            quando = None
            texto = tags.get("DateTimeOriginal") or tags.get("DateTime")
            if texto:
                try:
                    dt = datetime.strptime(str(texto).strip(), "%Y:%m:%d %H:%M:%S")
                    desvio = tags.get("OffsetTimeOriginal") or tags.get("OffsetTime")
                    if desvio:
                        h, m = str(desvio).strip().replace("+", "").split(":")
                        sinal = -1 if str(desvio).strip().startswith("-") else 1
                        dt = dt.replace(tzinfo=timezone(
                            sinal * timedelta(hours=abs(int(h)), minutes=int(m))))
                    quando = dt
                except ValueError:
                    pass

            local = None
            gps = exif.get_ifd(0x8825)
            if gps:
                g = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps.items()}
                lat = _graus(g.get("GPSLatitude"), g.get("GPSLatitudeRef"))
                lon = _graus(g.get("GPSLongitude"), g.get("GPSLongitudeRef"))
                if lat is not None and lon is not None:
                    local = (lat, lon)
            return quando, local
    except Exception:
        return None, None


def meta_por_mdls(caminho):
    """Metadados do Spotlight — cobre HEIC, que a Pillow nao le sem plugin."""
    saida = _rodar(["mdls", "-name", "kMDItemContentCreationDate",
                    "-name", "kMDItemLatitude", "-name", "kMDItemLongitude",
                    caminho])
    if not saida:
        return None, None
    quando = local = None
    lat = lon = None
    for linha in saida.splitlines():
        if "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        chave, valor = chave.strip(), valor.strip()
        if valor in ("(null)", ""):
            continue
        if chave == "kMDItemContentCreationDate":
            try:
                quando = datetime.strptime(valor, "%Y-%m-%d %H:%M:%S %z")
            except ValueError:
                pass
        elif chave == "kMDItemLatitude":
            try:
                lat = float(valor)
            except ValueError:
                pass
        elif chave == "kMDItemLongitude":
            try:
                lon = float(valor)
            except ValueError:
                pass
    if lat is not None and lon is not None:
        local = (lat, lon)
    return quando, local


# O WhatsApp exporta como PHOTO-AAAA-MM-DD-HH-MM-SS.jpg, com a hora local
# da maquina que exportou. E o unico horario que sobra: o aplicativo apaga
# o EXIF por completo.
RE_NOME_WHATSAPP = re.compile(
    r"(?:PHOTO|VIDEO|IMG|WA)[-_](\d{4})-(\d{2})-(\d{2})[-_](\d{2})[-_.](\d{2})[-_.](\d{2})")


def meta_por_nome(caminho):
    """Horario embutido no nome do arquivo, quando ele segue o padrao."""
    m = RE_NOME_WHATSAPP.search(os.path.basename(caminho))
    if not m:
        return None, None
    try:
        local = datetime(*(int(g) for g in m.groups()))
    except ValueError:
        return None, None
    # Sem fuso no nome: vale o da maquina, que foi quem escreveu o arquivo.
    return local.astimezone(), None


def meta_por_arquivo(caminho):
    """Data de criacao do proprio arquivo, lida do sistema de arquivos.

    E o mesmo instante que o Spotlight reporta, mas sem depender do daemon
    de indexacao — que pode estar fora do ar e devolver vazio, derrubando a
    ancoragem de arquivos que antes funcionavam.
    """
    try:
        st = os.stat(caminho)
    except OSError:
        return None, None
    quando = getattr(st, "st_birthtime", None) or st.st_mtime
    return datetime.fromtimestamp(quando, timezone.utc), None


def meta_por_ffprobe(caminho):
    """creation_time e localizacao ISO6179 dos videos do iPhone."""
    saida = _rodar(["ffprobe", "-v", "quiet", "-print_format", "json",
                    "-show_format", "-show_streams", caminho])
    if not saida:
        return None, None
    try:
        dados = json.loads(saida)
    except json.JSONDecodeError:
        return None, None

    tags = dict(dados.get("format", {}).get("tags", {}))
    for fluxo in dados.get("streams", []):
        for k, v in (fluxo.get("tags") or {}).items():
            tags.setdefault(k, v)

    # A ordem importa: creation_time e reescrita quando o arquivo e copiado,
    # enquanto com.apple.quicktime.creationdate guarda a captura de verdade.
    quando = None
    for chave in ("com.apple.quicktime.creationdate", "creation_time"):
        if chave in tags:
            texto = str(tags[chave]).strip().replace("Z", "+00:00")
            try:
                quando = datetime.fromisoformat(texto)
                break
            except ValueError:
                continue

    local = None
    for chave in ("com.apple.quicktime.location.ISO6709", "location"):
        if chave in tags:
            m = re.match(r"([+-]\d+\.?\d*)([+-]\d+\.?\d*)", str(tags[chave]))
            if m:
                local = (float(m.group(1)), float(m.group(2)))
                break
    return quando, local


def ler_metadados(caminho, ehvideo):
    """Tenta cada fonte de metadados em ordem ate obter um horario."""
    # O nome vem antes do Spotlight: a data do arquivo se perde ao copiar a
    # pasta, enquanto o nome viaja junto.
    # A tabela manual vem primeiro: ela so existe para os casos em que o
    # arquivo perdeu a data, e nesses o que estiver embutido esta errado.
    tentativas = ([meta_por_tabela, meta_por_ffprobe, meta_por_nome,
                   meta_por_mdls, meta_por_arquivo]
                  if ehvideo
                  else [meta_por_tabela, meta_por_pillow, meta_por_nome,
                        meta_por_mdls, meta_por_arquivo, meta_por_ffprobe])
    quando = local = None
    for fn in tentativas:
        q, l = fn(caminho)
        if quando is None and q is not None:
            quando = q
        if local is None and l is not None:
            local = l
        if quando is not None and local is not None:
            break
    return quando, local


# ------------------------------------------------------------ conversao

def gerar_foto(origem, destino, largura, qualidade):
    """Redimensiona e grava em WebP.

    A Pillow nao abre HEIC sem plugin, entao nesses casos usamos o sips, que
    ja vem no macOS e tambem escreve WebP.
    """
    if os.path.exists(destino):
        return True
    ext = os.path.splitext(origem)[1].lower()

    # O sips le HEIC mas nao escreve WebP, entao passamos por um JPEG
    # temporario e deixamos a Pillow fazer a compressao final.
    temporario = None
    if ext in (".heic", ".heif"):
        temporario = destino + ".tmp.jpg"
        _rodar(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "92",
                "-Z", str(largura), origem, "--out", temporario])
        if not os.path.exists(temporario):
            print(f"    ! sips nao converteu {os.path.basename(origem)}")
            return False
        origem = temporario

    try:
        from PIL import Image, ImageOps
        with Image.open(origem) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            if img.width > largura:
                img = img.resize(
                    (largura, round(img.height * largura / img.width)),
                    Image.LANCZOS)
            img.save(destino, "WEBP", quality=qualidade, method=6)
        return True
    except Exception as erro:
        print(f"    ! falha ao converter {os.path.basename(origem)}: {erro}")
        return False
    finally:
        if temporario and os.path.exists(temporario):
            os.remove(temporario)


def gerar_video(origem, destino, poster):
    """Transcodifica para MP4 h264 pronto para streaming progressivo."""
    if not os.path.exists(destino):
        r = subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", origem,
            "-vf", (f"scale='min({ALTURA_MAX_VIDEO * 16 // 9},iw)'"
                    f":'min({ALTURA_MAX_VIDEO},ih)'"
                    f":force_original_aspect_ratio=decrease:force_divisible_by=2"),
            "-c:v", "libx264", "-preset", "slow", "-crf", str(CRF_VIDEO),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-c:a", "aac", "-b:a", "128k", destino,
        ], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"    ! ffmpeg falhou em {os.path.basename(origem)}: "
                  f"{r.stderr.strip()[:200]}")
            return False
    if not os.path.exists(poster):
        gerar_poster(destino, poster)
    return os.path.exists(destino)


def gerar_poster(video, poster):
    """Primeiro quadro do video como WebP.

    Nem toda build do ffmpeg traz o encoder WebP (a do Homebrew nao traz),
    entao extraimos um JPEG e convertemos com a Pillow.
    """
    temporario = poster + ".tmp.jpg"
    _rodar(["ffmpeg", "-y", "-loglevel", "error", "-i", video,
            "-vf", f"scale={LARGURA_MINIATURA}:-2", "-frames:v", "1",
            "-q:v", "3", temporario])
    if not os.path.exists(temporario):
        return False
    try:
        from PIL import Image
        with Image.open(temporario) as img:
            img.convert("RGB").save(poster, "WEBP",
                                    quality=QUALIDADE_MINIATURA, method=6)
    except Exception:
        shutil.move(temporario, poster)   # sem Pillow, fica o JPEG mesmo
        return True
    finally:
        if os.path.exists(temporario):
            os.remove(temporario)
    return os.path.exists(poster)


def dimensoes(caminho):
    """Largura e altura do arquivo ja convertido, para o painel do site
    poder reservar exatamente a proporcao da midia."""
    ext = os.path.splitext(caminho)[1].lower()
    if ext in (".mp4", ".mov"):
        saida = _rodar(["ffprobe", "-v", "quiet", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height",
                        "-of", "csv=p=0:s=x", caminho])
        try:
            w, h = saida.strip().split("x")[:2]
            return int(w), int(h)
        except (ValueError, IndexError):
            return None, None
    try:
        from PIL import Image
        with Image.open(caminho) as img:
            return img.width, img.height
    except Exception:
        return None, None


# ------------------------------------------------------------- ancoragem

# Fotos tiradas antes de ligar o relogio (no cafe da manha) e depois de
# chega-lo (no refugio) fazem parte da etapa. Em vez de descarta-las, elas
# sao presas ao primeiro ou ao ultimo ponto do trajeto daquele dia.
MARGEM_ANTES = 4 * 3600
MARGEM_DEPOIS = 10 * 3600


def localizar_no_trajeto(dias, epoch):
    """Encontra o dia e a posicao correspondentes ao instante dado.

    Escolhe a etapa cujo intervalo esta mais proximo do instante, para que
    uma foto da noite nao caia na etapa do dia seguinte por engano.
    """
    candidatos = []
    for dia in dias:
        t0 = dia["resumo"]["inicioUTC"]
        fim = dia["t"][-1]
        rel = epoch - t0
        if rel < -MARGEM_ANTES or rel > fim + MARGEM_DEPOIS:
            continue
        distancia = 0 if 0 <= rel <= fim else (abs(rel) if rel < 0 else rel - fim)
        candidatos.append((distancia, dia, rel))

    if not candidatos:
        return None, None, None, None
    _, dia, rel = min(candidatos, key=lambda c: c[0])

    if rel < 0:
        fase = "antes"
    elif rel > dia["t"][-1]:
        fase = "depois"
    else:
        fase = "trajeto"
    rel = max(0.0, min(rel, dia["t"][-1]))
    ts = dia["t"]
    lo, hi = 0, len(ts) - 1
    while hi - lo > 1:
        meio = (lo + hi) // 2
        if ts[meio] <= rel:
            lo = meio
        else:
            hi = meio
    intervalo = ts[hi] - ts[lo]
    f = (rel - ts[lo]) / intervalo if intervalo > 0 else 0.0
    mistura = lambda c: c[lo] + f * (c[hi] - c[lo])
    return dia, rel, fase, {
        "lon": round(mistura(dia["lon"]), 6),
        "lat": round(mistura(dia["lat"]), 6),
        "ele": round(mistura(dia["ele"])),
        "dist": round(mistura(dia["dist"])),
        "gain": round(mistura(dia["gain"])),
    }


def formatar_duracao(segundos):
    h, resto = divmod(int(segundos), 3600)
    m = resto // 60
    return f"{h}h{m:02d}" if h else f"{m} min"


def montar_legenda(rel, estado, fase, dia):
    """Tempo de atividade + ganho de elevacao + distancia no dia.

    Fora do trajeto essas tres medidas nao dizem nada (seriam todas zero,
    ou todas o total do dia), entao a legenda vira a situacao do momento.
    """
    if fase == "antes":
        return f"Antes da partida, em {dia['de']}"
    if fase == "depois":
        return f"Na chegada, em {dia['para']}"
    km = f"{estado['dist'] / 1000:.1f}".replace(".", ",")   # separador pt-BR
    return (f"{formatar_duracao(rel)} de caminhada  ·  "
            f"+{estado['gain']} m  ·  "
            f"{km} km no dia")


# ------------------------------------------------- onde os videos vao morar

def ler_config():
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError:
            pass
    return {}


def gravar_config(cfg):
    with open(CONFIG, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


# ------------------------------------------------------------------- peso

def relatar_peso(itens, base_videos=None):
    """Mostra quanto a pasta publicada vai pesar e alerta sobre o GitHub Pages.

    O Pages recomenda ate 1 GB por site e o GitHub recusa qualquer arquivo
    acima de 100 MB, entao convem saber disso antes do primeiro push.
    """
    def tamanho(rel):
        caminho = (os.path.join(DIR_VIDEOS, rel.rsplit("/", 1)[-1])
                   if rel.startswith("http")
                   else os.path.join(RAIZ, "docs", rel))
        return os.path.getsize(caminho) if os.path.exists(caminho) else 0

    fotos = [i for i in itens if i["tipo"] == "foto"]
    videos = [i for i in itens if i["tipo"] == "video"]
    peso_fotos = sum(tamanho(i["src"]) + tamanho(i["thumb"]) for i in fotos)
    peso_videos = sum(tamanho(i["src"]) + tamanho(i["thumb"]) for i in videos)
    total = peso_fotos + peso_videos

    print("\nPeso dos arquivos publicados:")
    if fotos:
        print(f"  {len(fotos):3d} fotos   {peso_fotos / 1e6:7.1f} MB"
              f"   (media {peso_fotos / len(fotos) / 1e6:.2f} MB)")
    if videos:
        print(f"  {len(videos):3d} videos  {peso_videos / 1e6:7.1f} MB"
              f"   (media {peso_videos / len(videos) / 1e6:.2f} MB)")
    print(f"  {'total':>7}    {total / 1e6:7.1f} MB")

    if base_videos:
        print(f"\n  Os videos NAO estao no repositorio.")
        print(f"  Suba o conteudo de videos_para_subir/ para:")
        print(f"    {base_videos}")
        print(f"  Apenas as {len(fotos)} fotos ({peso_fotos / 1e6:.1f} MB) vao para o Git.")
        return

    grandes = [(i, tamanho(i["src"])) for i in itens
               if tamanho(i["src"]) > LIMITE_ARQUIVO_MB * 1e6]
    if grandes:
        print(f"\n  ATENCAO: {len(grandes)} arquivo(s) acima de {LIMITE_ARQUIVO_MB} MB.")
        for i, t in sorted(grandes, key=lambda g: -g[1])[:5]:
            print(f"    {t / 1e6:6.1f} MB  {i['original']}")
        print("    O GitHub recusa arquivos acima de 100 MB. Para encolher,")
        print("    rode de novo com --crf 30 ou --altura 720.")

    if total > LIMITE_TOTAL_MB * 1e6:
        print(f"\n  ATENCAO: o total passou de {LIMITE_TOTAL_MB} MB.")
        print("    O GitHub Pages recomenda no maximo 1 GB por site.")
        print("    Considere --crf 30, --altura 720, ou hospedar os videos fora.")


# ---------------------------------------------------------------- principal

def main():
    global CRF_VIDEO, ALTURA_MAX_VIDEO
    args = sys.argv[1:]
    forcar = "--forcar" in args
    if "--crf" in args:
        CRF_VIDEO = int(args[args.index("--crf") + 1])
    if "--altura" in args:
        ALTURA_MAX_VIDEO = int(args[args.index("--altura") + 1])

    cfg = ler_config()
    if "--videos-em" in args:
        cfg["baseVideos"] = args[args.index("--videos-em") + 1].rstrip("/")
        gravar_config(cfg)
    if "--videos-aqui" in args:
        cfg.pop("baseVideos", None)
        gravar_config(cfg)
    base_videos = cfg.get("baseVideos")
    fuso = FUSO_PADRAO
    if "--fuso" in args:
        try:
            texto = args[args.index("--fuso") + 1]
            sinal = -1 if texto.startswith("-") else 1
            h, _, m = texto.lstrip("+-").partition(":")
            fuso = timezone(sinal * timedelta(hours=int(h), minutes=int(m or 0)))
        except (IndexError, ValueError):
            raise SystemExit("--fuso espera algo como +02:00")

    caminho_dias = os.path.join(DIR_DADOS, "days.json")
    if not os.path.exists(caminho_dias):
        raise SystemExit("Rode scripts/build_trail.py primeiro.")
    with open(caminho_dias, encoding="utf-8") as fh:
        dias = json.load(fh)["dias"]

    os.makedirs(DIR_MIDIAS, exist_ok=True)
    os.makedirs(DIR_SAIDA, exist_ok=True)
    if base_videos:
        os.makedirs(DIR_VIDEOS, exist_ok=True)
    if forcar and os.path.isdir(DIR_SAIDA):
        shutil.rmtree(DIR_SAIDA)
        os.makedirs(DIR_SAIDA)

    arquivos = []
    for pasta, _, nomes in os.walk(DIR_MIDIAS):
        for nome in sorted(nomes):
            if nome.startswith("."):
                continue
            ext = os.path.splitext(nome)[1].lower()
            if ext in EXT_FOTO or ext in EXT_VIDEO:
                arquivos.append(os.path.join(pasta, nome))

    if not arquivos:
        with open(os.path.join(DIR_DADOS, "media.json"), "w", encoding="utf-8") as fh:
            json.dump({"midias": []}, fh, ensure_ascii=False, indent=2)
        print("Nenhuma midia em midias/ — media.json vazio gerado.")
        print("O site funciona normalmente; rode este script de novo quando")
        print("colocar as fotos e videos na pasta.")
        return

    print(f"Encontradas {len(arquivos)} midias.\n")
    itens, sem_ancora = [], []

    for indice, caminho in enumerate(arquivos, 1):
        nome = os.path.basename(caminho)
        ext = os.path.splitext(nome)[1].lower()
        ehvideo = ext in EXT_VIDEO

        quando, local = ler_metadados(caminho, ehvideo)
        if quando is None:
            sem_ancora.append((nome, "sem data de captura"))
            continue
        if quando.tzinfo is None:
            quando = quando.replace(tzinfo=fuso)

        dia, rel, fase, estado = localizar_no_trajeto(dias, quando.timestamp())
        if dia is None:
            sem_ancora.append((nome, f"fora do periodo ({quando:%d/%m %H:%M})"))
            continue

        base = f"d{dia['n']}_{int(rel):06d}_{re.sub(r'[^a-zA-Z0-9]+', '', os.path.splitext(nome)[0])[:24]}"
        if ehvideo:
            arq = f"{base}.mp4"
            thumb = f"{base}_thumb.webp"
            # O poster fica sempre no repositorio: e pequeno e permite que o
            # site mostre o quadro antes de buscar o video la fora.
            destino_video = os.path.join(
                DIR_VIDEOS if base_videos else DIR_SAIDA, arq)
            if not gerar_video(caminho, destino_video,
                               os.path.join(DIR_SAIDA, thumb)):
                sem_ancora.append((nome, "falha na conversao do video"))
                continue
        else:
            arq = f"{base}.webp"
            thumb = f"{base}_thumb.webp"
            if not gerar_foto(caminho, os.path.join(DIR_SAIDA, arq),
                              LARGURA_MAX, QUALIDADE_FOTO):
                sem_ancora.append((nome, "falha na conversao da foto"))
                continue
            gerar_foto(caminho, os.path.join(DIR_SAIDA, thumb),
                       LARGURA_MINIATURA, QUALIDADE_MINIATURA)

        larg, alt = dimensoes(destino_video if ehvideo and base_videos
                              else os.path.join(DIR_SAIDA, arq))

        # Distancia entre o GPS do arquivo e o ponto do trajeto, quando houver.
        desvio = None
        if local:
            desvio = round(math.hypot(
                (local[0] - estado["lat"]) * 110540,
                (local[1] - estado["lon"]) * 76000))

        itens.append({
            "id": base,
            "dia": dia["n"],
            "t": round(rel, 1),
            "tipo": "video" if ehvideo else "foto",
            "src": (f"{base_videos}/{arq}" if (ehvideo and base_videos)
                    else f"media/{arq}"),
            "thumb": f"media/{thumb}",
            "w": larg, "h": alt,
            "lon": estado["lon"], "lat": estado["lat"], "ele": estado["ele"],
            "dist": estado["dist"], "gain": estado["gain"],
            "legenda": montar_legenda(rel, estado, fase, dia),
            "fase": fase,
            "hora": quando.astimezone(fuso).strftime("%H:%M"),
            "desvioGps": desvio,
            "original": nome,
        })
        marca = {"antes": "  ←partida", "depois": "  chegada→"}.get(fase, "")
        print(f"  [{indice:3d}/{len(arquivos)}] dia {dia['n']}  "
              f"{formatar_duracao(rel):>7}{marca:>10}  {nome}")

    guardadas = preservar_etapas_antigas(itens)
    itens.sort(key=lambda m: (m["dia"], m["t"]))
    with open(os.path.join(DIR_DADOS, "media.json"), "w", encoding="utf-8") as fh:
        json.dump({"midias": itens}, fh, ensure_ascii=False, indent=2)

    print(f"\n{len(itens) - guardadas} midias ancoradas no trajeto.")
    if guardadas:
        print(f"({guardadas} de etapas anteriores mantidas: o original saiu de "
              f"midias/, mas o arquivo publicado continua em docs/media/)")
    relatar_peso(itens, base_videos)
    distantes = [m for m in itens if m["desvioGps"] and m["desvioGps"] > 150]
    if distantes:
        print(f"\n{len(distantes)} com GPS proprio distante do trajeto "
              f"(conferir se o horario bate):")
        for m in distantes[:10]:
            print(f"  {m['original']}: {m['desvioGps']} m")
    if sem_ancora:
        print(f"\n{len(sem_ancora)} nao ancoradas:")
        for nome, motivo in sem_ancora:
            print(f"  {nome}: {motivo}")
        print("\nPara datar na mao, crie midias/_datas.json assim:")
        print("  {")
        for nome, _ in sem_ancora[:3]:
            print(f'    "{nome}": "2026-09-20T12:34:56+02:00",')
        print("  }")
        print("\nSe forem fotos editadas, exporte de novo pelo app Fotos usando")
        print("'Exportar Original Nao Modificado' para preservar os metadados.")


if __name__ == "__main__":
    main()
