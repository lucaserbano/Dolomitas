/**
 * Motor de reprodução: relógio virtual, interpolação do estado e câmera.
 *
 * A posição e todas as métricas saem da mesma série temporal, interpoladas
 * pelo tempo corrido. A câmera voa atrás do trilheiro.
 */

import { desenharAte, destacarFantasma } from "./map.js";

const PITCH = 56;          // mais baixo que antes: enxerga o relevo à frente
const ZOOM = 14.3;

/* A trilha zigueza o tempo todo. Se o rumo vier dos metros imediatamente à
   frente, a câmera gira a cada curva e embrulha o estômago. Então o rumo é
   a tangente entre um ponto atrás e outro bem adiante, o que entrega a
   direção geral da caminhada em vez da direção instantânea. */
const OLHAR_ATRAS = 120;   // metros
const OLHAR_ADIANTE = 400; // metros
const GIRO_MAXIMO = 7;     // graus por segundo
const ZONA_MORTA = 5;      // graus: abaixo disso a câmera nem se mexe

/**
 * Mede o progresso geométrico (0 a 1) de cada vértice ao longo da linha.
 *
 * É a mesma régua do `line-progress` do MapLibre, e é por ela que o traço
 * avança. A distância percorrida não serve: ela fica parada nos trechos em
 * que houve deslocamento sem caminhada — o teleférico do fim do dia 3 —, e
 * aí o desenho ficaria para trás do trilheiro.
 */
export function prepararProgresso(dias) {
  dias.forEach((dia) => {
    const n = dia.lon.length;
    const acumulado = new Float64Array(n);
    for (let i = 1; i < n; i += 1) {
      const escala = Math.cos((dia.lat[i] * Math.PI) / 180);
      const dx = (dia.lon[i] - dia.lon[i - 1]) * 111320 * escala;
      const dy = (dia.lat[i] - dia.lat[i - 1]) * 110540;
      acumulado[i] = acumulado[i - 1] + Math.hypot(dx, dy);
    }
    const total = acumulado[n - 1] || 1;
    dia.prog = Array.from(acumulado, (v) => v / total);
  });
}

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

/** Índice do ponto mais próximo de uma distância acumulada. */
function indicePorDistancia(dist, alvo) {
  let lo = 0, hi = dist.length - 1;
  if (alvo <= dist[0]) return 0;
  if (alvo >= dist[hi]) return hi;
  while (hi - lo > 1) {
    const meio = (lo + hi) >> 1;
    if (dist[meio] <= alvo) lo = meio; else hi = meio;
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

  return {
    t, i,
    lon: mix(dia.lon),
    lat: mix(dia.lat),
    ele: mix(dia.ele),
    dist: mix(dia.dist),
    gain: mix(dia.gain),
    loss: mix(dia.loss),
    hr: dia.hr[i] ?? dia.hr[j] ?? null,
    fracao: mix(dia.prog),
    // o pedaço sem registro do relógio em que se está, se for o caso
    trecho: (dia.trechos ?? []).find((tr) => i > tr.de && i <= tr.ate) ?? null,
    fim: t >= ts[ts.length - 1] - 0.001,
  };
}

/** Tempo na etapa correspondente a uma distância percorrida. */
export function tempoNaDistancia(dia, alvo) {
  const i = indicePorDistancia(dia.dist, alvo);
  const j = Math.min(i + 1, dia.dist.length - 1);
  const vao = dia.dist[j] - dia.dist[i];
  const f = vao > 0 ? (alvo - dia.dist[i]) / vao : 0;
  return dia.t[i] + f * (dia.t[j] - dia.t[i]);
}

/**
 * Tempo da etapa cujo ponto está mais próximo de uma coordenada.
 * Usado ao arrastar o marcador do trilheiro sobre o mapa.
 */
export function tempoMaisProximo(dia, lon, lat) {
  const escala = Math.cos((lat * Math.PI) / 180);
  let melhor = Infinity;
  let indice = 0;
  for (let i = 0; i < dia.lon.length; i += 1) {
    const dx = (dia.lon[i] - lon) * escala;
    const dy = dia.lat[i] - lat;
    const d = dx * dx + dy * dy;
    if (d < melhor) { melhor = d; indice = i; }
  }
  return dia.t[indice];
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

/** Menor diferença entre dois ângulos, no intervalo [-180, 180]. */
function difAngulo(de, para) {
  return ((para - de + 540) % 360) - 180;
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

    /* Duas liberdades independentes. Arrastar o mapa solta o enquadramento;
       girar solta o rumo. Assim dá para girar a cena e continuar seguindo o
       trilheiro, que é o que se quer ao examinar uma encosta. */
    this.centralizar = true;
    this.rumoAuto = true;
    /* Preferência do usuário: com a rotação desligada a câmera continua
       acompanhando o trilheiro, mas sem girar a cena. */
    this.rotacao = true;
    /* Enquanto o marcador está sendo arrastado a câmera fica imóvel: se ela
       recentralizasse, o mapa se moveria sob o cursor e o arrasto entraria
       numa realimentação que corre até a ponta da etapa. */
    this.arrastandoMarcador = false;

    this.zoom = ZOOM;
    this.cameraOcupada = false;

    mapa.on("moveend", () => { this.cameraOcupada = false; });
    mapa.on("zoomend", (ev) => { if (ev.originalEvent) this.zoom = mapa.getZoom(); });

    // Só gestos do usuário soltam a câmera; os voos do próprio site não.
    mapa.on("dragstart", (ev) => { if (ev.originalEvent) this.soltar("centralizar"); });
    mapa.on("rotatestart", (ev) => { if (ev.originalEvent) this.soltar("rumo"); });
    mapa.on("pitchstart", (ev) => { if (ev.originalEvent) this.soltar("rumo"); });
  }

  get dia() { return this.dias[this.indiceDia]; }
  get duracaoDia() { return this.dia.t[this.dia.t.length - 1]; }
  get cameraLivre() { return !this.centralizar || !this.rumoAuto; }

  soltar(qual) {
    if (qual === "centralizar") this.centralizar = false;
    else this.rumoAuto = false;
    this.ganchos.aoMudarCamera?.(this.cameraLivre);
  }

  /** Volta a seguir o trilheiro, reaproximando sem solavanco. */
  retomarCamera() {
    this.centralizar = true;
    this.rumoAuto = true;
    this.zoom = ZOOM;
    const e = estadoEm(this.dia, this.tempo);
    this.cameraOcupada = true;
    this.mapa.easeTo({
      center: [e.lon, e.lat],
      zoom: ZOOM, pitch: PITCH,
      bearing: this.rotacao ? this.rumoDaTrilha(this.dia, e) : this.mapa.getBearing(),
      duration: 900, essential: true,
    });
    this.ganchos.aoMudarCamera?.(false);
  }

  /**
   * Direção geral do trecho: tangente entre um ponto atrás e um à frente.
   * Perto do fim os dois pontos se encontram, e aí o rumo anterior vale mais
   * do que um ângulo calculado sobre poucos metros.
   */
  rumoDaTrilha(d, e) {
    const a = indicePorDistancia(d.dist, Math.max(0, e.dist - OLHAR_ATRAS));
    const b = indicePorDistancia(d.dist, e.dist + OLHAR_ADIANTE);
    if (d.dist[b] - d.dist[a] < 25) return this.rumoAtual;
    return rumo(d.lon[a], d.lat[a], d.lon[b], d.lat[b]);
  }

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

    this.centralizar = true;
    this.rumoAuto = true;
    this.ganchos.aoMudarCamera?.(false);
    this.rumoAtual = this.rumoDaTrilha(d, estadoEm(d, 0));

    if (aproximar) {
      this.cameraOcupada = true;
      this.zoom = ZOOM;
      this.mapa.easeTo({
        center: [d.lon[0], d.lat[0]],
        zoom: ZOOM, pitch: PITCH,
        bearing: this.rotacao ? this.rumoAtual : this.mapa.getBearing(),
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
        this.atualizar(dt);
        this.pausar();
        this.concluirEtapa();
        return;
      }
      this.atualizar(dt);
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
  atualizar(dt = 1 / 60) {
    const d = this.dia;
    const e = estadoEm(d, this.tempo);
    desenharAte(this.mapa, d, e.fracao);

    if (!this.cameraOcupada && !this.arrastandoMarcador
        && (this.centralizar || this.rumoAuto)) {
      const camera = { pitch: this.mapa.getPitch(), zoom: this.mapa.getZoom() };

      if (this.centralizar) {
        camera.center = [e.lon, e.lat];
        camera.zoom = this.zoom;
        camera.pitch = PITCH;
      }
      if (this.rumoAuto && this.rotacao) {
        const alvo = this.rumoDaTrilha(d, e);
        const delta = difAngulo(this.rumoAtual, alvo);
        // Abaixo da zona morta a câmera fica parada; acima, gira devagar e
        // com teto de velocidade, para o movimento não embrulhar.
        if (Math.abs(delta) > ZONA_MORTA) {
          const teto = GIRO_MAXIMO * Math.max(dt, 1 / 120) * (this.velocidade / 60);
          const passo = Math.sign(delta) * Math.min(Math.abs(delta) * 0.04, teto);
          this.rumoAtual = (this.rumoAtual + passo + 360) % 360;
        }
        camera.bearing = this.rumoAtual;
      }
      this.mapa.jumpTo(camera);
    }
    this.ganchos.aoQuadro?.(d, e);
  }

  concluirEtapa() {
    const d = this.dia;
    const limites = d.lon.reduce(
      (acc, lon, i) => [
        Math.min(acc[0], lon), Math.min(acc[1], d.lat[i]),
        Math.max(acc[2], lon), Math.max(acc[3], d.lat[i]),
      ],
      [Infinity, Infinity, -Infinity, -Infinity],
    );
    this.cameraOcupada = true;
    this.mapa.fitBounds(limites, {
      padding: { top: 80, bottom: 120, left: 80, right: 80 },
      pitch: 46, duration: 2200, essential: true,
    });
    this.ganchos.aoConcluirEtapa?.(d, this.indiceDia === this.dias.length - 1);
  }

  proximaEtapa() {
    if (this.indiceDia >= this.dias.length - 1) return false;
    this.prepararEtapa(this.indiceDia + 1);
    return true;
  }

  /** Salta para um ponto qualquer da travessia. */
  irPara(indiceDia, tempo, { manterCamera = false } = {}) {
    const tocava = this.tocando;
    if (tocava) this.pausar();
    this.cameraOcupada = false;

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

    // Num salto grande o rumo vai direto ao alvo: interpolar daria um giro
    // longo e sem sentido.
    if (!manterCamera && this.rumoAuto && this.rotacao) {
      this.rumoAtual = this.rumoDaTrilha(this.dia, estadoEm(this.dia, this.tempo));
    }
    this.atualizar();
    if (tocava) this.tocar();
  }
}
