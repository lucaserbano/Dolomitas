/**
 * Orquestração: carrega os dados, monta o mapa e liga os controles.
 */

import { criarMapa, ativarTerreno, adicionarTrilhas, adicionarRefugios, maplibregl } from "./map.js";
import { Reprodutor, estadoEm } from "./animation.js";
import { Galeria } from "./media.js";
import * as hud from "./hud.js";

const $ = (s) => document.querySelector(s);

function avisar(texto) {
  const el = $("#aviso");
  el.textContent = texto;
  el.hidden = false;
}

async function carregar(caminho, reserva) {
  try {
    const r = await fetch(caminho, { cache: "no-cache" });
    if (!r.ok) throw new Error(r.status);
    return await r.json();
  } catch (erro) {
    if (reserva !== undefined) return reserva;
    throw erro;
  }
}

async function iniciar() {
  hud.prepararCampos();

  if (!maplibregl.supported?.() && !window.WebGL2RenderingContext) {
    avisar("Este navegador não tem suporte a WebGL, necessário para o mapa 3D.");
    return;
  }

  let dados, resumo, galeriaDados;
  try {
    [dados, resumo, galeriaDados] = await Promise.all([
      carregar("data/days.json"),
      carregar("data/summary.json"),
      carregar("data/media.json", { midias: [] }),
    ]);
  } catch {
    avisar("Não consegui ler os dados do trajeto. Rode scripts/build_trail.py e sirva a pasta site/ por HTTP.");
    return;
  }

  const dias = dados.dias;
  const midias = galeriaDados.midias ?? [];
  hud.escreverResumoGeral(resumo);

  // distância acumulada até o início de cada etapa
  const acumulado = [];
  dias.reduce((soma, d, i) => (acumulado[i] = soma, soma + d.resumo.dist), 0);

  const mapa = criarMapa("mapa", resumo.limites);
  let pronto = false;

  mapa.on("error", (e) => console.warn("mapa:", e?.error?.message || e));

  mapa.once("load", () => {
    ativarTerreno(mapa);
    adicionarTrilhas(mapa, dias);
    adicionarRefugios(mapa, dias);
    pronto = true;
  });

  /* ---------------------------------------------------- marcador do caminhante */
  const alfinete = document.createElement("div");
  alfinete.className = "caminhante";
  const marcadorCaminhante = new maplibregl.Marker({ element: alfinete })
    .setLngLat([dias[0].lon[0], dias[0].lat[0]])
    .addTo(mapa);

  /* ------------------------------------------------------------- reprodutor */
  const galeria = new Galeria(mapa, midias, {
    aoAbrir: (m, manual) => {
      if (!manual && reprodutor.tocando) {
        reprodutor.pausar();
        reprodutor.pausadoPorMidia = true;
      }
    },
    aoFechar: () => {
      if (reprodutor.pausadoPorMidia) {
        reprodutor.pausadoPorMidia = false;
        reprodutor.tocar();
      }
    },
  });

  const reprodutor = new Reprodutor(mapa, dias, {
    aoTrocarEtapa: (dia) => {
      hud.trocarEtapa(dia);
      galeria.fechar();
    },
    aoQuadro: (dia, estado) => {
      hud.atualizarMedidas(dia, estado, acumulado[reprodutor.indiceDia]);
      hud.atualizarLinhaTempo(reprodutor.indiceDia, estado.t);
      marcadorCaminhante.setLngLat([estado.lon, estado.lat]);
      galeria.verificar(dia, estado.t);
    },
    aoMudarEstado: (tocando) => {
      $(".icone-tocar").dataset.estado = tocando ? "tocando" : "pausado";
      $("#btn-tocar").setAttribute("aria-label", tocando ? "Pausar" : "Retomar");
    },
    aoConcluirEtapa: (dia, ehUltima) => {
      const proxima = ehUltima ? "" : dias[reprodutor.indiceDia + 1].para;
      hud.preencherResumo(dia, ehUltima, proxima);
      $("#resumo").hidden = false;
    },
  });

  hud.construirLinhaTempo(dias, midias, (indice, tempo) => {
    $("#resumo").hidden = true;
    galeria.fechar();
    galeria.redefinirApos(dias[indice].n, tempo);
    reprodutor.irPara(indice, tempo);
  });

  /* ---------------------------------------------------------------- controles */
  $("#btn-comecar").addEventListener("click", () => {
    if (!pronto) {
      avisar("O relevo ainda está carregando. Tente de novo em instantes.");
      return;
    }
    $("#intro").classList.add("saindo");
    $("#app").classList.add("ativo");
    $("#app").setAttribute("aria-hidden", "false");
    setTimeout(() => { $("#intro").hidden = true; mapa.resize(); }, 660);
    reprodutor.prepararEtapa(0);
    setTimeout(() => reprodutor.tocar(), 1900);
  });

  $("#btn-tocar").addEventListener("click", () => {
    $("#resumo").hidden = true;
    reprodutor.alternar();
  });

  $("#btn-seguir").addEventListener("click", () => {
    $("#resumo").hidden = true;
    if (!reprodutor.proximaEtapa()) {
      galeria.redefinirTudo();
      reprodutor.prepararEtapa(0);
    }
    setTimeout(() => reprodutor.tocar(), 1900);
  });

  $("#tgl-midias").addEventListener("change", (ev) => {
    galeria.automatico = ev.target.checked;
  });

  document.querySelectorAll(".velocidade button").forEach((b) => {
    b.addEventListener("click", () => {
      document.querySelectorAll(".velocidade button").forEach((o) => o.classList.remove("ativo"));
      b.classList.add("ativo");
      reprodutor.velocidade = Number(b.dataset.vel);
    });
  });

  // arrastar na linha do tempo: a câmera para de seguir enquanto se mexe no mapa
  mapa.on("dragstart", () => { reprodutor.seguirCamera = false; });
  mapa.on("zoomstart", (e) => { if (e.originalEvent) reprodutor.seguirCamera = false; });
  $("#btn-tocar").addEventListener("dblclick", () => { reprodutor.seguirCamera = true; });

  document.addEventListener("keydown", (ev) => {
    if (ev.target.matches("input, button")) return;
    if (ev.code === "Space") { ev.preventDefault(); reprodutor.alternar(); }
  });

  window.addEventListener("resize", () => mapa.resize());
}

iniciar();
