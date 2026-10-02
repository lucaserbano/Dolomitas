/**
 * Orquestração: carrega os dados, monta o mapa e liga os controles.
 */

import { criarMapa, ativarTerreno, adicionarTrilhas, adicionarRefugios, maplibregl } from "./map.js";
import { Reprodutor, estadoEm, tempoMaisProximo } from "./animation.js";
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
  const marcadorCaminhante = new maplibregl.Marker({
    element: alfinete,
    draggable: true,          // arrastar o ponto retrocede ou avança a etapa
  })
    .setLngLat([dias[0].lon[0], dias[0].lat[0]])
    .addTo(mapa);

  let arrastandoPonto = false;
  marcadorCaminhante.on("dragstart", () => {
    arrastandoPonto = true;
    reprodutor.arrastandoMarcador = true;
    alfinete.classList.add("arrastando");
    if (reprodutor.tocando) {
      reprodutor.pausar();
      reprodutor.retomaAposArrasto = true;
    }
    galeria.fechar();
  });
  marcadorCaminhante.on("drag", () => {
    const p = marcadorCaminhante.getLngLat();
    // O ponto gruda na trilha: solto no relevo ele perderia o sentido.
    reprodutor.irPara(reprodutor.indiceDia,
                      tempoMaisProximo(reprodutor.dia, p.lng, p.lat),
                      { manterCamera: true });
  });
  marcadorCaminhante.on("dragend", () => {
    arrastandoPonto = false;
    reprodutor.arrastandoMarcador = false;
    alfinete.classList.remove("arrastando");
    galeria.redefinirApos(reprodutor.dia.n, reprodutor.tempo);
    if (reprodutor.retomaAposArrasto) {
      reprodutor.retomaAposArrasto = false;
      reprodutor.tocar();
    }
  });

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
      galeria.ajustarPinos(dia.n);
    },
    aoQuadro: (dia, estado) => {
      hud.atualizarMedidas(dia, estado, acumulado[reprodutor.indiceDia]);
      hud.atualizarLinhaTempo(reprodutor.indiceDia, estado.t, arrastandoScrub);
      if (!arrastandoPonto) {
        marcadorCaminhante.setLngLat([estado.lon, estado.lat]);
      }
      galeria.verificar(dia, estado.t);
    },
    aoMudarCamera: (livre) => { $("#btn-recentrar").hidden = !livre; },
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

  let arrastandoScrub = false;
  const scrub = hud.construirLinhaTempo(dias, midias, (indice, tempo) => {
    $("#resumo").hidden = true;
    if (galeria.ativa) galeria.fechar();
    galeria.redefinirApos(dias[indice].n, tempo);
    reprodutor.irPara(indice, tempo, { manterCamera: arrastandoScrub });
  });
  scrub.addEventListener("pointerdown", () => { arrastandoScrub = true; });
  ["pointerup", "pointercancel", "blur"].forEach((ev) =>
    scrub.addEventListener(ev, () => { arrastandoScrub = false; }));

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

  $("#btn-recentrar").addEventListener("click", () => reprodutor.retomarCamera());

  document.addEventListener("keydown", (ev) => {
    if (ev.target.matches("input, button")) return;
    if (ev.code === "Space") { ev.preventDefault(); reprodutor.alternar(); return; }
    // setas movem a etapa em passos de um minuto de caminhada
    const passo = ev.shiftKey ? 600 : 60;
    if (ev.code === "ArrowLeft" || ev.code === "ArrowRight") {
      ev.preventDefault();
      const dir = ev.code === "ArrowRight" ? 1 : -1;
      $("#resumo").hidden = true;
      reprodutor.irPara(reprodutor.indiceDia, reprodutor.tempo + dir * passo,
                        { manterCamera: true });
      galeria.redefinirApos(reprodutor.dia.n, reprodutor.tempo);
    }
  });

  window.addEventListener("resize", () => mapa.resize());

  // Ponto de inspeção no console do navegador: útil para conferir a câmera
  // e saltar para um trecho sem depender da interface.
  window.dolomitas = { mapa, reprodutor, galeria, dias };
}

iniciar();
