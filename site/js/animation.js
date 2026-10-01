/**
 * Motor de reprodução: relógio virtual, interpolação do estado e câmera.
 *
 * A posição e todas as métricas saem da mesma série temporal, interpoladas
 * pelo tempo corrido. A câmera voa atrás do caminhante.
 */

import { desenharAte, destacarFantasma } from "./map.js";

const PITCH = 62;
const ZOOM = 14.6;
const SUAVIZACAO_RUMO = 0.07;  // quanto menor, mais lento o giro da câmera
const OLHAR_ADIANTE = 45;      // metros à frente usados para calcular o rumo

/** Busca binária: último índice cujo tempo é <= alvo. */
function indicePara(ts, alvo) {
  let lo = 0, hi = ts.length - 1;
  if (alvo <= ts[0]) return 0;
  if (alvo >= ts[hi]) return hi - 1;
  while (hi - lo > 1) {
    const meio = (lo + hi) >> 1;
    if (ts[meio] <= alvo) lo = meio; else hi = meio;
  }
  return lo;
}

/** Estado completo da etapa num instante. */
export function estadoEm(dia, tempo) {
  const ts = dia.t;
  const t = Math.max(0, Math.min(tempo, ts[ts.length - 1]));
  const i = indicePara(ts, t);
  const j = Math.min(i + 1, ts.length - 1);
  const vao = ts[j] - ts[i];
  const f = vao > 0 ? (t - ts[i]) / vao : 0;
  const mix = (a) => a[i] + f * (a[j] - a[i]);

  const total = dia.dist[dia.dist.length - 1] || 1;
  const dist = mix(dia.dist);

  return {
    t,
    i,
    lon: mix(dia.lon),
    lat: mix(dia.lat),
    ele: mix(dia.ele),
    dist,
    gain: mix(dia.gain),
    loss: mix(dia.loss),
    hr: dia.hr[i] ?? dia.hr[j] ?? null,
    fracao: dist / total,
    fim: t >= ts[ts.length - 1] - 0.001,
  };
}

/** Rumo em graus entre dois pontos geográficos. */
function rumo(lon1, lat1, lon2, lat2) {
  const f1 = (lat1 * Math.PI) / 180;
  const f2 = (lat2 * Math.PI) / 180;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const y = Math.sin(dl) * Math.cos(f2);
  const x = Math.cos(f1) * Math.sin(f2) - Math.sin(f1) * Math.cos(f2) * Math.cos(dl);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

/** Interpola ângulos pelo caminho mais curto — sem o salto em 0°/360°. */
function misturarAngulo(de, para, f) {
  let d = ((para - de + 540) % 360) - 180;
  return (de + d * f + 360) % 360;
}

export class Reprodutor {
  constructor(mapa, dias, ganchos = {}) {
    this.mapa = mapa;
    this.dias = dias;
    this.ganchos = ganchos;

    this.indiceDia = 0;
    this.tempo = 0;
    this.velocidade = 180;
    this.tocando = false;
    this.rumoAtual = 0;
    this.ultimoQuadro = 0;
    this.quadro = null;
    this.seguirCamera = true;
    this.pausadoPorMidia = false;

    // Zoom que a camera mantem ao seguir. Guardado aqui porque ler
    // mapa.getZoom() a cada quadro cancelaria qualquer voo em andamento.
    this.zoom = ZOOM;
    this.cameraOcupada = false;

    // enquanto um voo (easeTo/fitBounds) acontece, o seguidor fica quieto
    mapa.on("moveend", () => { this.cameraOcupada = false; });
    mapa.on("zoomend", (ev) => {
      if (ev.originalEvent) this.zoom = mapa.getZoom();
    });
  }

  get dia() { return this.dias[this.indiceDia]; }
  get duracaoDia() { return this.dia.t[this.dia.t.length - 1]; }

  /** Posiciona a câmera no início de uma etapa, olhando na direção da trilha. */
  prepararEtapa(indice, aproximar = true) {
    this.indiceDia = indice;
    this.tempo = 0;
    const d = this.dia;

    destacarFantasma(this.mapa, this.dias, d.n);
    this.dias.forEach((outro, k) => {
      if (k > indice) desenharAte(this.mapa, outro, 0);
      else if (k < indice) desenharAte(this.mapa, outro, 1);
    });
    desenharAte(this.mapa, d, 0);

    this.rumoAtual = rumo(d.lon[0], d.lat[0], d.lon[Math.min(12, d.lon.length - 1)], d.lat[Math.min(12, d.lat.length - 1)]);

    if (aproximar) {
      this.cameraOcupada = true;
      this.zoom = ZOOM;
      this.mapa.easeTo({
        center: [d.lon[0], d.lat[0]],
        zoom: ZOOM, pitch: PITCH, bearing: this.rumoAtual,
        duration: 1800, essential: true,
      });
    }
    this.ganchos.aoTrocarEtapa?.(d);
    this.atualizar();
  }

  tocar() {
    if (this.tocando) return;
    this.tocando = true;
    this.ultimoQuadro = performance.now();
    this.ganchos.aoMudarEstado?.(true);
    const passo = (agora) => {
      if (!this.tocando) return;
      const dt = Math.min((agora - this.ultimoQuadro) / 1000, 0.1);
      this.ultimoQuadro = agora;
      this.tempo += dt * this.velocidade;

      if (this.tempo >= this.duracaoDia) {
        this.tempo = this.duracaoDia;
        this.atualizar();
        this.pausar();
        this.concluirEtapa();
        return;
      }
      this.atualizar();
      this.quadro = requestAnimationFrame(passo);
    };
    this.quadro = requestAnimationFrame(passo);
  }

  pausar() {
    this.tocando = false;
    if (this.quadro) cancelAnimationFrame(this.quadro);
    this.quadro = null;
    this.ganchos.aoMudarEstado?.(false);
  }

  alternar() { this.tocando ? this.pausar() : this.tocar(); }

  /** Recalcula posição, câmera e avisa quem escuta. */
  atualizar() {
    const d = this.dia;
    const e = estadoEm(d, this.tempo);
    desenharAte(this.mapa, d, e.fracao);

    if (this.seguirCamera && !this.cameraOcupada) {
      const alvo = this.olharAdiante(d, e);
      this.rumoAtual = misturarAngulo(this.rumoAtual, alvo, SUAVIZACAO_RUMO);
      this.mapa.jumpTo({
        center: [e.lon, e.lat],
        bearing: this.rumoAtual,
        pitch: PITCH,
        zoom: this.zoom,
      });
    }
    this.ganchos.aoQuadro?.(d, e);
  }

  /** Rumo apontando para um ponto adiante na trilha, para a câmera não tremer. */
  olharAdiante(d, e) {
    const limite = e.dist + OLHAR_ADIANTE;
    let k = e.i;
    while (k < d.dist.length - 1 && d.dist[k] < limite) k += 1;
    if (k === e.i) k = Math.min(e.i + 1, d.lon.length - 1);
    return rumo(e.lon, e.lat, d.lon[k], d.lat[k]);
  }

  concluirEtapa() {
    const d = this.dia;
    const coords = d.lon.map((lon, i) => [lon, d.lat[i]]);
    const limites = coords.reduce(
      (acc, c) => [
        Math.min(acc[0], c[0]), Math.min(acc[1], c[1]),
        Math.max(acc[2], c[0]), Math.max(acc[3], c[1]),
      ],
      [Infinity, Infinity, -Infinity, -Infinity],
    );
    this.cameraOcupada = true;
    this.mapa.fitBounds(limites, {
      padding: { top: 80, bottom: 120, left: 80, right: 80 },
      pitch: 48, duration: 2200, essential: true,
    });
    this.ganchos.aoConcluirEtapa?.(d, this.indiceDia === this.dias.length - 1);
  }

  /** Avança para a próxima etapa, se houver. */
  proximaEtapa() {
    if (this.indiceDia >= this.dias.length - 1) return false;
    this.prepararEtapa(this.indiceDia + 1);
    return true;
  }

  /** Salta para um ponto qualquer da travessia. */
  irPara(indiceDia, tempo) {
    const tocava = this.tocando;
    if (tocava) this.pausar();
    this.cameraOcupada = false;   // um salto manual interrompe qualquer voo
    if (indiceDia !== this.indiceDia) {
      this.indiceDia = indiceDia;
      destacarFantasma(this.mapa, this.dias, this.dia.n);
      this.dias.forEach((outro, k) => {
        if (k > indiceDia) desenharAte(this.mapa, outro, 0);
        else if (k < indiceDia) desenharAte(this.mapa, outro, 1);
      });
      this.ganchos.aoTrocarEtapa?.(this.dia);
    }
    this.tempo = Math.max(0, Math.min(tempo, this.duracaoDia));
    const e = estadoEm(this.dia, this.tempo);
    this.rumoAtual = this.olharAdiante(this.dia, e);
    this.atualizar();
    if (tocava) this.tocar();
  }
}
