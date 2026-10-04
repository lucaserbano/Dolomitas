/**
 * Mapa de terreno 3D e camadas do trajeto.
 *
 * O relevo nao usa imagem de satelite: a altitude e colorida pela paleta do
 * projeto (color-relief) e recebe textura de um hillshade por cima. Isso
 * mantem o mapa coeso com a identidade e, principalmente, deixa as trilhas
 * quentes legiveis sobre qualquer encosta.
 */

// A v6 do MapLibre e ESM e expoe apenas nomes — nao ha export default.
import * as maplibregl from "https://cdn.jsdelivr.net/npm/maplibre-gl@6.11.2/dist/maplibre-gl.mjs";

export { maplibregl };

const DEM = {
  type: "raster-dem",
  tiles: ["https://tiles.mapterhorn.com/{z}/{x}/{y}.webp"],
  encoding: "terrarium",
  tileSize: 512,
  minzoom: 0,
  maxzoom: 15,
  attribution:
    '<a href="https://mapterhorn.com/attribution">© Mapterhorn</a> · ' +
    'dados do trajeto: Apple Watch',
};

/* Rampa de altitude. Comeca em ardosia profunda nos vales e sobe ate a
   pedra clara nos cumes, sempre dessaturada — os tons quentes saturados
   ficam reservados para as trilhas. */
const RAMPA = [
   700, "#16202b",
  1100, "#1d2835",
  1400, "#243341",
  1700, "#2f424d",
  2000, "#44555b",
  2300, "#637068",
  2550, "#808878",
  2800, "#949a86",
  3200, "#a6ab96",
];

export const CASCA = "#141c25"; // contorno escuro sob cada trilha

export function criarMapa(alvo, limites) {
  const mapa = new maplibregl.Map({
    container: alvo,
    style: {
      version: 8,
      // O MapLibre recomenda nao compartilhar a mesma fonte entre o relevo 3D
      // e as camadas pintadas; os tiles sao os mesmos e vem do cache HTTP.
      sources: { relevo: DEM, pintura: { ...DEM } },
      layers: [
        { id: "fundo", type: "background", paint: { "background-color": "#16202b" } },
        {
          id: "altitude",
          type: "color-relief",
          source: "pintura",
          paint: {
            "color-relief-color": [
              "interpolate", ["linear"], ["elevation"], ...RAMPA,
            ],
            "color-relief-opacity": 1,
          },
        },
        {
          id: "sombra",
          type: "hillshade",
          source: "pintura",
          paint: {
            "hillshade-exaggeration": 0.55,
            "hillshade-shadow-color": "#0e151d",
            "hillshade-highlight-color": "#cdc5a4",
            "hillshade-accent-color": "#1d2835",
            "hillshade-illumination-direction": 315,
          },
        },
      ],
    },
    bounds: limites,
    fitBoundsOptions: { padding: 60 },
    maxPitch: 80,
    attributionControl: { compact: true },
    dragRotate: true,
    hash: false,
  });

  mapa.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
  mapa.touchZoomRotate.enableRotation();

  return mapa;
}

/** Ativa o relevo 3D. Chamado depois que o estilo carregou. */
export function ativarTerreno(mapa, exagero = 1.4) {
  mapa.setTerrain({ source: "relevo", exaggeration: exagero });
}

/* ------------------------------------------- trechos sem registro do relogio

   O fim do dia 3 nao tem GPS: a atividade foi encerrada no alto do Lagazuoi,
   e o resto — o teleferico e a trilha ate o Rifugio Valparola — esta tracado
   a mao. Essa parte da linha recebe o mesmo matiz do dia, mas puxado para o
   contorno: quanto menos foi caminhada, mais apagada. Nada disso cria camada
   nova — e tudo a mesma expressao de line-gradient. */
const DESBOTE = { a_pe: 0.35, teleferico: 0.6 };

function misturar(a, b, k) {
  const canal = (cor, i) => parseInt(cor.slice(1 + i * 2, 3 + i * 2), 16);
  const saida = [0, 1, 2].map((i) => {
    const v = Math.round(canal(a, i) * (1 - k) + canal(b, i) * k);
    return v.toString(16).padStart(2, "0");
  });
  return `#${saida.join("")}`;
}

/** Cores da linha por faixa de line-progress: [[inicio, cor], ...]. */
function paleta(dia) {
  const faixas = [[0, dia.cor]];
  (dia.trechos ?? []).forEach((t) => {
    faixas.push([dia.prog[t.de], misturar(dia.cor, CASCA, DESBOTE[t.modo] ?? 0.5)]);
  });
  return faixas;
}

const paletas = new Map();

/**
 * Cria, para cada etapa, tres camadas: o traçado completo em fantasma,
 * o contorno escuro e a linha colorida.
 *
 * O avanço da animacao nao recria geometria — apenas reescreve a expressao
 * de line-gradient, que corta a linha no ponto desejado via line-progress.
 */
export function adicionarTrilhas(mapa, dias) {
  dias.forEach((dia) => {
    const id = `dia${dia.n}`;
    paletas.set(dia.n, paleta(dia));
    mapa.addSource(id, {
      type: "geojson",
      lineMetrics: true,
      data: {
        type: "Feature",
        properties: {},
        geometry: {
          type: "LineString",
          coordinates: dia.lon.map((lon, i) => [lon, dia.lat[i]]),
        },
      },
    });

    // prévia do caminho que ainda falta — ajuda a se orientar no relevo
    mapa.addLayer({
      id: `${id}-fantasma`,
      type: "line",
      source: id,
      layout: { "line-cap": "round", "line-join": "round", visibility: "none" },
      paint: {
        "line-color": dia.cor,
        "line-width": 1.5,
        "line-opacity": 0.22,
        "line-dasharray": [2, 2.5],
      },
    });

    mapa.addLayer({
      id: `${id}-casca`,
      type: "line",
      source: id,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-width": ["interpolate", ["linear"], ["zoom"], 9, 4, 14, 7.5, 17, 11],
        "line-gradient": corte([[0, CASCA]], 0),
      },
    });

    mapa.addLayer({
      id: `${id}-linha`,
      type: "line",
      source: id,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-width": ["interpolate", ["linear"], ["zoom"], 9, 1.6, 14, 3.6, 17, 6],
        "line-gradient": corte(paletas.get(dia.n), 0),
      },
    });
  });
}

/** Monta a expressao garantindo paradas estritamente crescentes. */
function expressao(paradas) {
  const saida = [];
  let anterior = -1;
  paradas.forEach(([pos, cor]) => {
    const x = Math.min(1, Math.max(0, pos, anterior + 1e-5));
    if (x <= anterior) return;
    saida.push(x, cor);
    anterior = x;
  });
  return ["interpolate", ["linear"], ["line-progress"], ...saida];
}

/** Expressao que mostra a linha de 0 ate `fracao` e some depois. */
function corte(faixas, fracao) {
  const p = Math.max(0.0001, Math.min(0.9999, fracao));
  const paradas = [[0, faixas[0][1]]];
  let cor = faixas[0][1];
  for (let k = 1; k < faixas.length; k += 1) {
    const [inicio, proxima] = faixas[k];
    if (inicio >= p) break;
    // degrau seco: a cor anterior vale ate a vespera do limite
    paradas.push([inicio - 0.0002, cor], [inicio, proxima]);
    cor = proxima;
  }
  paradas.push([p, cor], [p + 0.0005, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]);
  return expressao(paradas);
}

/** Avanca (ou recolhe) o desenho de uma etapa. */
export function desenharAte(mapa, dia, fracao) {
  const faixas = paletas.get(dia.n) ?? [[0, dia.cor]];
  const f = Math.max(0, fracao);
  mapa.setPaintProperty(`dia${dia.n}-linha`, "line-gradient", corte(faixas, f));
  mapa.setPaintProperty(`dia${dia.n}-casca`, "line-gradient",
                        corte([[0, CASCA]], f));
}

/** Mostra o tracejado de prévia apenas na etapa em curso. */
export function destacarFantasma(mapa, dias, nAtual) {
  dias.forEach((dia) => {
    mapa.setLayoutProperty(
      `dia${dia.n}-fantasma`, "visibility",
      dia.n === nAtual ? "visible" : "none",
    );
  });
}

/**
 * Pinos das mídias como camada do mapa, e não como marcadores HTML.
 *
 * Marcador HTML é posicionado só por lon/lat: com o relevo 3D ligado ele
 * ignora a altitude do ponto e aparece deslocado encosta acima, mudando de
 * lugar a cada zoom. A camada é desenhada pela GPU já drapejada no terreno,
 * fica no lugar certo e aguenta centenas de pontos sem pesar.
 */
export function adicionarPinosMidia(mapa, midias) {
  mapa.addSource("midias", {
    type: "geojson",
    data: {
      type: "FeatureCollection",
      features: midias.map((m, i) => ({
        type: "Feature",
        id: i,
        properties: { id: m.id, dia: m.dia, indice: i, tipo: m.tipo },
        geometry: { type: "Point", coordinates: [m.lon, m.lat] },
      })),
    },
  });

  mapa.addLayer({
    id: "midias",
    type: "circle",
    source: "midias",
    minzoom: 12,
    filter: ["==", ["get", "dia"], -1],
    paint: {
      "circle-radius": [
        "interpolate", ["linear"], ["zoom"],
        12, 2.5,
        14, ["case", ["boolean", ["feature-state", "ativa"], false], 7, 4],
        17, ["case", ["boolean", ["feature-state", "ativa"], false], 11, 6.5],
      ],
      "circle-color": [
        "case", ["boolean", ["feature-state", "ativa"], false],
        "#f2d492", "#f29559",
      ],
      "circle-opacity": [
        "case", ["boolean", ["feature-state", "ativa"], false], 1, 0.75,
      ],
      "circle-stroke-width": 1.5,
      "circle-stroke-color": CASCA,
      "circle-pitch-alignment": "map",
    },
  });
}

/** Mostra apenas os pinos da etapa em curso. */
export function filtrarPinos(mapa, diaN) {
  if (mapa.getLayer("midias")) {
    mapa.setFilter("midias", ["==", ["get", "dia"], diaN ?? -1]);
  }
}

/**
 * Etiquetas dos pontos de partida e chegada de cada etapa, mais os marcos
 * intermediários declarados em build_trail.py (um refúgio no meio do
 * caminho, por exemplo) e os lugares de paisagem — os que não estão no
 * trajeto, mas situam quem olha: um pico, uma torre, a cidade lá embaixo.
 */
export function adicionarRefugios(mapa, dias, paisagem = []) {
  const pontos = [];
  dias.forEach((dia, i) => {
    if (i === 0) {
      pontos.push({ nome: dia.de, lon: dia.lon[0], lat: dia.lat[0], tipo: "inicio" });
    }
    (dia.marcos ?? []).forEach((m) => {
      pontos.push({ nome: m.nome, lon: m.lon, lat: m.lat, tipo: "marco" });
    });
    const u = dia.lon.length - 1;
    /* Quem vai e volta chega onde saiu: o nome do destino já foi para o ponto
       da meia-volta, e aqui vale o nome da partida. */
    pontos.push({ nome: dia.idaevolta ? dia.de : dia.para,
                  lon: dia.lon[u], lat: dia.lat[u], tipo: "fim" });
  });
  paisagem.forEach((p) => {
    pontos.push({ nome: p.nome, lon: p.lon, lat: p.lat, tipo: "paisagem" });
  });

  const marcadores = pontos.map((p) => {
    const el = document.createElement("div");
    el.className = "refugio";
    el.dataset.tipo = p.tipo;
    el.textContent = p.nome;
    return new maplibregl.Marker({ element: el, anchor: "left", offset: [6, 0] })
      .setLngLat([p.lon, p.lat])
      .addTo(mapa);
  });

  // Numa visao muito aberta os nomes se empilham e viram ruido.
  const ZOOM_MINIMO = 10.5;
  const ajustar = () => {
    const mostrar = mapa.getZoom() >= ZOOM_MINIMO;
    marcadores.forEach((m) => {
      m.getElement().style.visibility = mostrar ? "visible" : "hidden";
    });
  };
  mapa.on("zoom", ajustar);
  ajustar();

  return marcadores;
}
