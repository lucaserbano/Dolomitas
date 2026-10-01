#!/usr/bin/env python3
"""
Constroi site/data/days.json e site/data/summary.json a partir do export do Apple Health.

Entradas (pasta relogio/):
  - route_2026-09-NN_*.gpx : trajeto GPS a 1 Hz
  - export.xml             : frequencia cardiaca e estatisticas dos treinos

Uso:  python3 scripts/build_trail.py
"""

import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_RELOGIO = os.path.join(RAIZ, "relogio")
DIR_DADOS = os.path.join(RAIZ, "docs", "data")
CACHE_SAUDE = os.path.join(DIR_DADOS, ".health_cache.json")

# Trechos percorridos, na ordem. Os nomes vieram do cruzamento das coordenadas
# de inicio/fim de cada GPX com o OpenStreetMap (todos a menos de 160 m).
ETAPAS = [
    ("2026-09-19", "Lago di Braies", "Rifugio Sennes"),
    ("2026-09-20", "Rifugio Sennes", "Rifugio Fanes"),
    ("2026-09-21", "Rifugio Fanes", "Rifugio Lagazuoi"),
    ("2026-09-22", "Rifugio Lagazuoi", "Malga Giau"),
    ("2026-09-23", "Malga Giau", "Passo Staulanza"),
    ("2026-09-24", "Passo Staulanza", "Borca di Cadore"),
]

# Parametros de processamento
RDP_EPSILON = 2.5      # metros — tolerancia da simplificacao da geometria
PASSO_TEMPORAL = 10    # segundos — resolucao minima da serie de metricas
JANELA_SUAVIZACAO = 15 # amostras para cada lado (~30 s a 1 Hz)
LIMIAR_GANHO = 3.0     # metros — ruido ignorado no ganho de elevacao


# ---------------------------------------------------------------- utilidades

def haversine(lat1, lon1, lat2, lon2):
    """Distancia em metros entre dois pontos."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def rdp_indices(pontos, epsilon):
    """Douglas-Peucker iterativo. `pontos` sao pares (x, y) em metros.

    Retorna os indices preservados. A versao iterativa evita estouro de pilha
    nos trechos longos (ate 24 mil pontos por dia).
    """
    n = len(pontos)
    if n < 3:
        return list(range(n))
    manter = [False] * n
    manter[0] = manter[-1] = True
    pilha = [(0, n - 1)]
    while pilha:
        ini, fim = pilha.pop()
        if fim <= ini + 1:
            continue
        ax, ay = pontos[ini]
        bx, by = pontos[fim]
        dx, dy = bx - ax, by - ay
        comp = math.hypot(dx, dy)
        pior, idx = 0.0, -1
        for i in range(ini + 1, fim):
            px, py = pontos[i]
            if comp > 0:
                d = abs(dy * px - dx * py + bx * ay - by * ax) / comp
            else:
                d = math.hypot(px - ax, py - ay)
            if d > pior:
                pior, idx = d, i
        if pior > epsilon and idx > 0:
            manter[idx] = True
            pilha.append((ini, idx))
            pilha.append((idx, fim))
    return [i for i, k in enumerate(manter) if k]


def interpolar_serie(x_alvo, xs, ys):
    """Interpolacao linear com busca binaria. xs precisa estar ordenado."""
    if not xs:
        return None
    if x_alvo <= xs[0]:
        return ys[0]
    if x_alvo >= xs[-1]:
        return ys[-1]
    lo, hi = 0, len(xs) - 1
    while hi - lo > 1:
        meio = (lo + hi) // 2
        if xs[meio] <= x_alvo:
            lo = meio
        else:
            hi = meio
    intervalo = xs[hi] - xs[lo]
    if intervalo <= 0:
        return ys[lo]
    f = (x_alvo - xs[lo]) / intervalo
    return ys[lo] + f * (ys[hi] - ys[lo])


# ------------------------------------------------------------------- cores

def _srgb_para_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_para_srgb(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def hex_para_oklab(h):
    h = h.lstrip("#")
    r, g, b = (_srgb_para_linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (
        0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
        1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
        0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s,
    )


def oklab_para_hex(L, a, b_):
    l = (L + 0.3963377774 * a + 0.2158037573 * b_) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b_) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b_) ** 3
    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    saida = ""
    for c in (r, g, b):
        v = round(max(0.0, min(1.0, _linear_para_srgb(c))) * 255)
        saida += f"{v:02x}"
    return "#" + saida


def rampa_dias(n):
    """n cores interpoladas em OKLCH ao longo de #b8b08d -> #f2d492 -> #f29559.

    O tom #b8b08d entra como ponta inicial porque so entre #f2d492 e #f29559
    os seis passos ficariam indistinguiveis entre si.
    """
    paradas = ["#b8b08d", "#f2d492", "#f29559"]
    lch = []
    for h in paradas:
        L, a, b = hex_para_oklab(h)
        lch.append((L, math.hypot(a, b), math.atan2(b, a)))
    cores = []
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0.0
        pos = t * (len(lch) - 1)
        k = min(int(pos), len(lch) - 2)
        f = pos - k
        L1, C1, H1 = lch[k]
        L2, C2, H2 = lch[k + 1]
        dh = H2 - H1
        while dh > math.pi:
            dh -= 2 * math.pi
        while dh < -math.pi:
            dh += 2 * math.pi
        L = L1 + f * (L2 - L1)
        C = C1 + f * (C2 - C1)
        H = H1 + f * dh
        cores.append(oklab_para_hex(L, C * math.cos(H), C * math.sin(H)))
    return cores


# --------------------------------------------------------------- leitura GPX

RE_PONTO = re.compile(
    r'<trkpt lon="([-\d.]+)" lat="([-\d.]+)">'
    r'<ele>([-\d.]+)</ele>'
    r'<time>([^<]+)</time>'
    r'.*?<hAcc>([-\d.]+)</hAcc><vAcc>([-\d.]+)</vAcc>'
)


def ler_gpx(caminho):
    """Le um GPX do Apple Health e devolve a lista de pontos.

    Pontos com vAcc negativo tem a altitude marcada como ausente: o relogio
    grava ele=0 quando o altimetro falha, o que inflaria o ganho de elevacao.
    As coordenadas desses pontos continuam validas.
    """
    with open(caminho, "r", encoding="utf-8") as fh:
        bruto = fh.read()
    pontos = []
    for lon, lat, ele, t, hacc, vacc in RE_PONTO.findall(bruto):
        quando = datetime.fromisoformat(t.replace("Z", "+00:00"))
        pontos.append({
            "lon": float(lon),
            "lat": float(lat),
            "ele": float(ele) if float(vacc) > 0 else None,
            "ts": quando.timestamp(),
            "hacc": float(hacc),
        })
    if not pontos:
        raise SystemExit(f"Nenhum ponto reconhecido em {caminho}")
    return pontos


def preencher_altitudes(pontos):
    """Interpola linearmente as altitudes ausentes, no lugar."""
    validos = [i for i, p in enumerate(pontos) if p["ele"] is not None]
    if not validos:
        raise SystemExit("Nenhuma altitude valida no trajeto")
    # Bordas: repete o valor valido mais proximo.
    for i in range(validos[0]):
        pontos[i]["ele"] = pontos[validos[0]]["ele"]
    for i in range(validos[-1] + 1, len(pontos)):
        pontos[i]["ele"] = pontos[validos[-1]]["ele"]
    for a, b in zip(validos, validos[1:]):
        if b == a + 1:
            continue
        ea, eb = pontos[a]["ele"], pontos[b]["ele"]
        for i in range(a + 1, b):
            f = (i - a) / (b - a)
            pontos[i]["ele"] = ea + f * (eb - ea)


def suavizar(valores, janela):
    """Media movel simetrica."""
    n = len(valores)
    saida = [0.0] * n
    acum = [0.0]
    for v in valores:
        acum.append(acum[-1] + v)
    for i in range(n):
        ini = max(0, i - janela)
        fim = min(n, i + janela + 1)
        saida[i] = (acum[fim] - acum[ini]) / (fim - ini)
    return saida


# ------------------------------------------------------- leitura export.xml

DATAS = {d for d, _, _ in ETAPAS}


def _epoch(txt):
    """Converte '2026-09-19 04:18:03 -0300' em epoch UTC."""
    return datetime.strptime(txt, "%Y-%m-%d %H:%M:%S %z").timestamp()


def ler_saude(caminho):
    """Varre o export.xml em streaming e extrai o necessario dos 6 dias.

    O arquivo tem ~330 MB, entao usamos iterparse e descartamos cada elemento
    logo apos processa-lo. O resultado vai para um cache em disco, ja que a
    varredura leva alguns minutos e o conteudo nunca muda.
    """
    if os.path.exists(CACHE_SAUDE):
        with open(CACHE_SAUDE, "r", encoding="utf-8") as fh:
            print("  (usando cache de saude)")
            return json.load(fh)

    print("  varrendo export.xml (330 MB, leva alguns minutos)...")
    fc = []          # (epoch, bpm)
    treinos = {}     # data -> estatisticas e pausas

    contexto = ET.iterparse(caminho, events=("end",))
    for _, elem in contexto:
        if elem.tag == "Record":
            if elem.get("type") == "HKQuantityTypeIdentifierHeartRate":
                ini = elem.get("startDate", "")
                if ini[:10] in DATAS:
                    try:
                        fc.append((_epoch(ini), float(elem.get("value"))))
                    except (TypeError, ValueError):
                        pass
            elem.clear()

        elif elem.tag == "Workout":
            ini = elem.get("startDate", "")
            if (elem.get("workoutActivityType") == "HKWorkoutActivityTypeHiking"
                    and ini[:10] in DATAS):
                dia = ini[:10]
                info = {"pausas": [], "kcal": None, "distRelogio": None,
                        "fcMed": None, "fcMax": None, "fcMin": None}
                for filho in elem:
                    if filho.tag == "WorkoutStatistics":
                        tipo = filho.get("type", "")
                        if tipo.endswith("ActiveEnergyBurned"):
                            info["kcal"] = float(filho.get("sum", 0))
                        elif tipo.endswith("DistanceWalkingRunning"):
                            info["distRelogio"] = float(filho.get("sum", 0)) * 1000
                        elif tipo.endswith("HeartRate"):
                            info["fcMed"] = float(filho.get("average", 0))
                            info["fcMax"] = float(filho.get("maximum", 0))
                            info["fcMin"] = float(filho.get("minimum", 0))
                    elif filho.tag == "WorkoutEvent":
                        tipo = filho.get("type", "")
                        if tipo in ("HKWorkoutEventTypePause", "HKWorkoutEventTypeResume"):
                            info["pausas"].append(
                                ("pausa" if tipo.endswith("Pause") else "retoma",
                                 _epoch(filho.get("date")))
                            )
                info["pausas"].sort(key=lambda p: p[1])
                treinos[dia] = info
            elem.clear()

    fc.sort()
    dados = {"fc": fc, "treinos": treinos}
    os.makedirs(DIR_DADOS, exist_ok=True)
    with open(CACHE_SAUDE, "w", encoding="utf-8") as fh:
        json.dump(dados, fh)
    print(f"  {len(fc)} amostras de FC, {len(treinos)} treinos")
    return dados


def intervalos_parados(pausas, inicio, fim):
    """Pares [inicio, fim] de cada pausa, em segundos desde a largada."""
    janelas = []
    aberta = None
    for tipo, quando in pausas:
        if tipo == "pausa" and aberta is None:
            aberta = quando
        elif tipo == "retoma" and aberta is not None:
            janelas.append([round(aberta - inicio, 1), round(quando - inicio, 1)])
            aberta = None
    if aberta is not None:
        janelas.append([round(aberta - inicio, 1), round(fim - inicio, 1)])
    return [j for j in janelas if j[1] > j[0] >= 0]


def tempo_em_movimento(pausas, inicio, fim):
    """Desconta os intervalos pausados do tempo total."""
    parado = 0.0
    aberta = None
    for tipo, quando in pausas:
        if tipo == "pausa" and aberta is None:
            aberta = quando
        elif tipo == "retoma" and aberta is not None:
            parado += max(0.0, quando - aberta)
            aberta = None
    if aberta is not None:
        parado += max(0.0, fim - aberta)
    return max(0.0, (fim - inicio) - parado)


# ------------------------------------------------------------- montagem

def processar_dia(n, data, de, para, caminho_gpx, cor, saude):
    pontos = ler_gpx(caminho_gpx)
    preencher_altitudes(pontos)

    eles = suavizar([p["ele"] for p in pontos], JANELA_SUAVIZACAO)

    # Distancia e ganho acumulados ponto a ponto.
    dist_acum = [0.0] * len(pontos)
    for i in range(1, len(pontos)):
        dist_acum[i] = dist_acum[i - 1] + haversine(
            pontos[i - 1]["lat"], pontos[i - 1]["lon"],
            pontos[i]["lat"], pontos[i]["lon"],
        )

    # Ganho e perda compartilham a mesma referencia movel: so conta quando o
    # desvio passa do limiar, senao o ruido do altimetro vira subida falsa.
    ganho_acum = [0.0] * len(pontos)
    perda_acum = [0.0] * len(pontos)
    referencia = eles[0]
    total_ganho = 0.0
    total_perda = 0.0
    for i, e in enumerate(eles):
        if e > referencia + LIMIAR_GANHO:
            total_ganho += e - referencia
            referencia = e
        elif e < referencia - LIMIAR_GANHO:
            total_perda += referencia - e
            referencia = e
        ganho_acum[i] = total_ganho
        perda_acum[i] = total_perda

    # Vertices mantidos: geometria (Douglas-Peucker) unida a uma amostragem
    # temporal regular, que garante resolucao para a FC e a altitude no HUD.
    lat0 = math.radians(pontos[0]["lat"])
    projetado = [
        (p["lon"] * 111320 * math.cos(lat0), p["lat"] * 110540)
        for p in pontos
    ]
    escolhidos = set(rdp_indices(projetado, RDP_EPSILON))
    t0 = pontos[0]["ts"]
    proximo = t0
    for i, p in enumerate(pontos):
        if p["ts"] >= proximo:
            escolhidos.add(i)
            proximo = p["ts"] + PASSO_TEMPORAL
    escolhidos.add(0)
    escolhidos.add(len(pontos) - 1)
    indices = sorted(escolhidos)

    fc_x = [t for t, _ in saude["fc"]]
    fc_y = [v for _, v in saude["fc"]]

    serie = {"lon": [], "lat": [], "ele": [], "t": [], "hr": [],
             "dist": [], "gain": [], "loss": []}
    for i in indices:
        p = pontos[i]
        serie["lon"].append(round(p["lon"], 6))
        serie["lat"].append(round(p["lat"], 6))
        serie["ele"].append(round(eles[i], 1))
        serie["t"].append(round(p["ts"] - t0, 1))
        bpm = interpolar_serie(p["ts"], fc_x, fc_y)
        serie["hr"].append(round(bpm) if bpm is not None else None)
        serie["dist"].append(round(dist_acum[i], 1))
        serie["gain"].append(round(ganho_acum[i], 1))
        serie["loss"].append(round(perda_acum[i], 1))

    treino = saude["treinos"].get(data, {})
    duracao = pontos[-1]["ts"] - t0
    pausas = treino.get("pausas", [])
    movimento = tempo_em_movimento(pausas, t0, pontos[-1]["ts"])
    paradas = intervalos_parados(pausas, t0, pontos[-1]["ts"])

    fcs = [v for v in serie["hr"] if v]
    resumo = {
        "dist": round(dist_acum[-1]),
        "ganho": round(total_ganho),
        "perda": round(total_perda),
        "dur": round(duracao),
        "mov": round(movimento),
        "eleMin": round(min(eles)),
        "eleMax": round(max(eles)),
        "fcMed": round(treino.get("fcMed") or (sum(fcs) / len(fcs) if fcs else 0)),
        "fcMax": round(treino.get("fcMax") or (max(fcs) if fcs else 0)),
        "fcMin": round(treino.get("fcMin") or (min(fcs) if fcs else 0)),
        "kcal": round(treino.get("kcal") or 0),
        "inicioUTC": round(t0),
    }

    return {
        "n": n, "data": data, "de": de, "para": para, "cor": cor,
        "pontos": len(indices), "paradas": paradas, "resumo": resumo, **serie,
    }


def main():
    if not os.path.isdir(DIR_RELOGIO):
        raise SystemExit(f"Pasta nao encontrada: {DIR_RELOGIO}")

    export = os.path.join(DIR_RELOGIO, "export.xml")
    if not os.path.exists(export):
        raise SystemExit(f"Arquivo nao encontrado: {export}")

    os.makedirs(DIR_DADOS, exist_ok=True)
    print("Lendo dados de saude...")
    saude = ler_saude(export)

    gpxs = {}
    for nome in os.listdir(DIR_RELOGIO):
        m = re.match(r"route_(\d{4}-\d{2}-\d{2})_.*\.gpx$", nome)
        if m:
            gpxs[m.group(1)] = os.path.join(DIR_RELOGIO, nome)

    cores = rampa_dias(len(ETAPAS))
    dias = []
    print("\nProcessando trajetos:")
    for i, (data, de, para) in enumerate(ETAPAS):
        if data not in gpxs:
            raise SystemExit(f"GPX ausente para {data}")
        dia = processar_dia(i + 1, data, de, para, gpxs[data], cores[i], saude)
        dias.append(dia)
        r = dia["resumo"]
        print(f"  Dia {dia['n']} {data}  {de} -> {para}")
        print(f"         {r['dist']/1000:5.2f} km  +{r['ganho']:4d} m  "
              f"-{r['perda']:4d} m  FC {r['fcMed']:3d}/{r['fcMax']:3d}  "
              f"{dia['pontos']:5d} pontos")

    todos_lon = [v for d in dias for v in d["lon"]]
    todos_lat = [v for d in dias for v in d["lat"]]
    dist_total = sum(d["resumo"]["dist"] for d in dias)
    ganho_total = sum(d["resumo"]["ganho"] for d in dias)
    perda_total = sum(d["resumo"]["perda"] for d in dias)

    resumo = {
        "titulo": "Alta Via 1",
        "subtitulo": "Dolomitas",
        "dias": len(dias),
        "distTotal": dist_total,
        "ganhoTotal": ganho_total,
        "perdaTotal": perda_total,
        "eleMin": min(d["resumo"]["eleMin"] for d in dias),
        "eleMax": max(d["resumo"]["eleMax"] for d in dias),
        "limites": [min(todos_lon), min(todos_lat), max(todos_lon), max(todos_lat)],
        "periodo": [ETAPAS[0][0], ETAPAS[-1][0]],
    }

    with open(os.path.join(DIR_DADOS, "days.json"), "w", encoding="utf-8") as fh:
        json.dump({"dias": dias}, fh, separators=(",", ":"))
    with open(os.path.join(DIR_DADOS, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(resumo, fh, ensure_ascii=False, indent=2)

    tam = os.path.getsize(os.path.join(DIR_DADOS, "days.json")) / 1024
    print(f"\nTOTAL  {dist_total/1000:.1f} km  +{ganho_total} m  -{perda_total} m  "
          f"elevacao {resumo['eleMin']}-{resumo['eleMax']} m")
    print(f"days.json: {tam:.0f} KB  ({sum(d['pontos'] for d in dias)} pontos)")


if __name__ == "__main__":
    main()
