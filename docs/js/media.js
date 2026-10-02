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
      this.pinos.set(m.id, { el, marcador, dia: m.dia });
    });

    // São centenas de pinos ao longo da travessia. Mostrados todos de uma
    // vez, eles viram uma faixa pontilhada que esconde a própria trilha.
    this.mapa.on("zoom", () => this.ajustarPinos());
    this.ajustarPinos();
  }

  /** Só a etapa em curso mostra pinos, e só com zoom suficiente. */
  ajustarPinos(diaAtual = this.diaAtual) {
    this.diaAtual = diaAtual;
    const perto = this.mapa.getZoom() >= 12.5;
    this.pinos.forEach(({ el, dia }) => {
      const mostrar = perto && (diaAtual === undefined || dia === diaAtual);
      el.style.display = mostrar ? "" : "none";
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

    // o painel reserva a proporção exata antes de a mídia chegar
    const quadro = this.painel.querySelector(".midia-quadro");
    if (m.w && m.h) quadro.style.setProperty("--prop", `${m.w} / ${m.h}`);
    else quadro.style.removeProperty("--prop");

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
      v.poster = m.thumb;          // o quadro aparece antes do vídeo chegar
      v.loop = true;
      v.muted = true;
      v.autoplay = true;
      v.playsInline = true;
      v.preload = "metadata";
      v.setAttribute("playsinline", "");
      // Vídeos podem estar hospedados fora; se faltarem, o poster continua
      // valendo e o motivo fica explícito em vez de um quadro preto.
      v.addEventListener("error", () => this.falhar(m), { once: true });
      v.play?.().catch(() => {});
      return v;
    }
    const img = document.createElement("img");
    img.src = m.src;
    img.alt = `Foto feita após ${m.legenda}`;
    img.decoding = "async";
    img.addEventListener("error", () => this.falhar(m), { once: true });
    return img;
  }

  /** Troca a mídia quebrada pelo poster e uma explicação curta. */
  falhar(m) {
    if (this.ativa?.id !== m.id) return;
    const caixa = document.createElement("div");
    caixa.className = "midia-ausente";
    if (m.thumb) {
      const prev = document.createElement("img");
      prev.src = m.thumb;
      prev.alt = "";
      caixa.appendChild(prev);
    }
    const aviso = document.createElement("p");
    aviso.textContent = m.src.startsWith("http")
      ? "Este vídeo está hospedado fora do site e não pôde ser carregado."
      : "Arquivo não encontrado.";
    caixa.appendChild(aviso);
    this.conteudo.replaceChildren(caixa);
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
