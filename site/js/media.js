/**
 * Fotos e vídeos ancorados no trajeto.
 *
 * Com o interruptor ligado, a travessia pausa sozinha ao alcançar cada mídia
 * e só continua quando o "X" é clicado. Desligado, os pinos seguem no mapa
 * e podem ser abertos a qualquer momento sem interromper o fluxo.
 */

import { maplibregl } from "./map.js";

export class Galeria {
  constructor(mapa, midias, ganchos = {}) {
    this.mapa = mapa;
    this.midias = midias;
    this.ganchos = ganchos;
    this.ativa = null;
    this.vistas = new Set();
    this.automatico = true;

    this.painel = document.getElementById("midia");
    this.conteudo = document.getElementById("midia-conteudo");
    this.hora = document.querySelector('[data-campo="mHora"]');
    this.legenda = document.querySelector('[data-campo="mLegenda"]');

    document.getElementById("midia-fechar")
      .addEventListener("click", () => this.fechar());

    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && this.ativa) this.fechar();
    });

    this.pinos = new Map();
    this.criarPinos();
  }

  criarPinos() {
    this.midias.forEach((m) => {
      const el = document.createElement("div");
      el.className = "pino";
      el.title = `${m.hora} · ${m.legenda}`;
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        this.abrir(m, true);
      });
      const marcador = new maplibregl.Marker({ element: el })
        .setLngLat([m.lon, m.lat])
        .addTo(this.mapa);
      this.pinos.set(m.id, { el, marcador });
    });
  }

  /**
   * Procura a mídia que acabou de ser alcançada nesta etapa.
   * A janela de meio minuto evita que um salto grande de tempo pule o item.
   */
  verificar(dia, tempo) {
    if (!this.automatico || this.ativa) return;
    const achado = this.midias.find(
      (m) => m.dia === dia.n &&
             !this.vistas.has(m.id) &&
             tempo >= m.t &&
             tempo - m.t < 30,
    );
    if (achado) this.abrir(achado, false);
  }

  abrir(m, manual) {
    if (this.ativa?.id === m.id) return;
    this.ativa = m;
    this.vistas.add(m.id);

    this.conteudo.replaceChildren(this.montar(m));
    this.hora.textContent = m.hora;
    this.legenda.textContent = m.legenda;
    this.painel.hidden = false;

    this.pinos.forEach(({ el }) => el.classList.remove("ativo"));
    this.pinos.get(m.id)?.el.classList.add("ativo");

    this.ganchos.aoAbrir?.(m, manual);
  }

  montar(m) {
    if (m.tipo === "video") {
      const v = document.createElement("video");
      v.src = m.src;
      v.poster = m.thumb;
      v.loop = true;
      v.muted = true;
      v.autoplay = true;
      v.playsInline = true;
      v.setAttribute("playsinline", "");
      v.play?.().catch(() => {});
      return v;
    }
    const img = document.createElement("img");
    img.src = m.src;
    img.alt = `Foto feita após ${m.legenda}`;
    img.decoding = "async";
    return img;
  }

  fechar() {
    if (!this.ativa) return;
    const fechada = this.ativa;
    this.ativa = null;
    this.painel.hidden = true;
    this.conteudo.replaceChildren();
    this.pinos.get(fechada.id)?.el.classList.remove("ativo");
    this.ganchos.aoFechar?.(fechada);
  }

  /** Ao voltar no tempo, as mídias daquele trecho voltam a disparar. */
  redefinirApos(diaN, tempo) {
    this.midias.forEach((m) => {
      if (m.dia > diaN || (m.dia === diaN && m.t >= tempo)) this.vistas.delete(m.id);
    });
  }

  redefinirTudo() { this.vistas.clear(); }
}
