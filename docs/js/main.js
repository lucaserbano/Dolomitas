/**
 * Orquestração: carrega os dados, monta o mapa e liga os controles.
 */

import { criarMapa, ativarTerreno, adicionarTrilhas, adicionarRefugios,
         adicionarPinosMidia, maplibregl } from "./map.js";
import { Reprodutor, estadoEm, tempoMaisProximo } from "./animation.js";
import { Galeria } from "./media.js";
import * as hud from "./hud.js";
import { instalarRoda } from "./roda.js";

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
    adicionarPinosMidia(mapa, midias);
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
  /* O painel cobre um pedaço do mapa. Informando isso ao MapLibre como
     padding, o ponto seguido passa a ser enquadrado na área que sobra em
     vez de ficar escondido atrás da foto. */
  function ajustarEnquadramento(aberto) {
    const zero = { top: 0, right: 0, bottom: 0, left: 0 };

    const aplicar = () => {
      if (!aberto) return mapa.setPadding(zero);

      /* Mede a invasão real do painel sobre o canvas, em vez de supor pela
         orientação: em pé o painel é uma folha que mal encosta no mapa, e um
         palpite alto jogava o caminhante para fora da tela. */
      const m = $("#mapa").getBoundingClientRect();
      const p = $("#midia").getBoundingClientRect();
      const sobreporDireita = Math.max(0, m.right - p.left + 16);
      const sobreporBaixo = Math.max(0, m.bottom - p.top + 16);
      const folha = p.width > m.width * 0.8;

      mapa.setPadding(folha
        ? { ...zero, bottom: Math.min(sobreporBaixo, m.height * 0.55) }
        : { ...zero, right: Math.min(sobreporDireita, m.width * 0.5) });
    };

    /* setPadding mexe na câmera e cancelaria um voo em andamento. A primeira
       mídia do dia abre em t=0, bem no meio da aproximação inicial: sem esta
       espera, o mapa ficava parado na visão panorâmica. */
    if (reprodutor.cameraOcupada) mapa.once("moveend", aplicar);
    else aplicar();
  }

  const galeria = new Galeria(mapa, midias, {
    /* Abrir uma mídia sempre para a travessia, e fechá-la nunca a retoma:
       quem decide quando o trajeto anda é o botão de play. Sem isso, passar
       de foto em foto deixava uma retomada pendente que disparava sozinha
       no momento de fechar. */
    aoAbrir: () => {
      requestAnimationFrame(() => ajustarEnquadramento(true));
      reprodutor.pausar();
    },
    aoFechar: () => ajustarEnquadramento(false),
    // passar de foto em foto leva a travessia junto
    aoPular: (m) => {
      $("#resumo").hidden = true;
      reprodutor.irPara(reprodutor.indiceDia, m.t, { manterCamera: true });
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
    setTimeout(() => { if (!galeria.ativa) reprodutor.tocar(); }, 1900);
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
    setTimeout(() => { if (!galeria.ativa) reprodutor.tocar(); }, 1900);
  });

  const caixaMidias = $("#tgl-midias");
  galeria.automatico = caixaMidias.checked;   // o HTML define o padrão
  caixaMidias.addEventListener("change", (ev) => {
    galeria.automatico = ev.target.checked;
  });

  $("#tgl-girar").addEventListener("change", (ev) => {
    reprodutor.rotacao = ev.target.checked;
    // ao voltar a girar, a câmera reencontra o rumo da trilha sem salto
    if (ev.target.checked && reprodutor.rumoAuto) reprodutor.retomarCamera();
  });

  document.querySelectorAll(".velocidade button").forEach((b) => {
    b.addEventListener("click", () => {
      document.querySelectorAll(".velocidade button").forEach((o) => o.classList.remove("ativo"));
      b.classList.add("ativo");
      reprodutor.velocidade = Number(b.dataset.vel);
    });
  });

  $("#btn-recentrar").addEventListener("click", () => reprodutor.retomarCamera());

  // Girar pela roda solta o rumo automático; o enquadramento continua
  // seguindo o caminhante, só para de girar sozinho.
  instalarRoda(mapa, () => reprodutor.soltar("rumo"));

  document.addEventListener("keydown", (ev) => {
    const alvo = ev.target;
    if (alvo instanceof Element
        && alvo.matches('input, button, select, textarea, [role="slider"]')) return;
    if (ev.code === "Space") { ev.preventDefault(); reprodutor.alternar(); return; }
    if (ev.code !== "ArrowLeft" && ev.code !== "ArrowRight") return;
    ev.preventDefault();
    const dir = ev.code === "ArrowRight" ? 1 : -1;

    // Com uma mídia aberta as setas passam de foto em foto; sem nada aberto
    // elas correm o tempo da etapa.
    if (galeria.ativa) { galeria.passar(dir); return; }

    const passo = ev.shiftKey ? 600 : 60;
    $("#resumo").hidden = true;
    reprodutor.irPara(reprodutor.indiceDia, reprodutor.tempo + dir * passo,
                      { manterCamera: true });
    galeria.redefinirApos(reprodutor.dia.n, reprodutor.tempo);
  });

  window.addEventListener("resize", () => {
    mapa.resize();
    if (galeria.ativa) requestAnimationFrame(() => ajustarEnquadramento(true));
  });

  // Ponto de inspeção no console do navegador: útil para conferir a câmera
  // e saltar para um trecho sem depender da interface.
  window.dolomitas = { mapa, reprodutor, galeria, dias };
}

iniciar();
