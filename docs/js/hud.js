/**
 * Leituras do painel: métricas ao vivo, perfil de elevação e linha do tempo.
 */

const $ = (sel, raiz = document) => raiz.querySelector(sel);
const campos = {};

/** Cacheia os nós marcados com data-campo para não consultar o DOM a cada quadro. */
export function prepararCampos() {
  document.querySelectorAll("[data-campo]").forEach((el) => {
    campos[el.dataset.campo] = el;
  });
}

const definir = (nome, valor) => {
  const el = campos[nome];
  if (el && el.textContent !== valor) el.textContent = valor;
};

/* ------------------------------------------------------------ formatos */

export const km = (m, casas = 1) =>
  (m / 1000).toFixed(casas).replace(".", ",");

export const metros = (m) =>
  Math.round(m).toLocaleString("pt-BR");

export function duracao(segundos) {
  const s = Math.max(0, Math.round(segundos));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h ? `${h}h${String(m).padStart(2, "0")}` : `${m} min`;
}

const DATA_CURTA = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short" });
export const dataCurta = (iso) => {
  const [a, m, d] = iso.split("-").map(Number);
  return DATA_CURTA.format(new Date(a, m - 1, d)).replace(".", "");
};

/* ------------------------------------------------------- medidas ao vivo */

export function escreverResumoGeral(resumo) {
  const valores = {
    dist: `${km(resumo.distTotal)}<i>km</i>`,
    ganho: `${metros(resumo.ganhoTotal)}<i>m</i>`,
    perda: `${metros(resumo.perdaTotal)}<i>m</i>`,
    dias: String(resumo.dias),
    distCurto: `${km(resumo.distTotal)} km`,
  };
  document.querySelectorAll("[data-resumo]").forEach((el) => {
    const v = valores[el.dataset.resumo];
    if (v !== undefined) el.innerHTML = v;
  });
}

export function trocarEtapa(dia) {
  document.documentElement.style.setProperty("--cor-dia", dia.cor);
  definir("diaNum", String(dia.n));
  definir("diaData", dataCurta(dia.data));
  definir("diaDe", dia.de);
  definir("diaPara", dia.para);
  desenharPerfil(dia);
}

export function atualizarMedidas(dia, estado, distAnterior) {
  definir("altitude", metros(estado.ele));
  definir("fc", estado.hr ? String(estado.hr) : "—");
  definir("ganho", metros(estado.gain));
  definir("perda", metros(estado.loss));
  definir("distDia", km(estado.dist));
  definir("distTotal", km(distAnterior + estado.dist));
  definir("decorrido", duracao(estado.t));
  definir("duracao", duracao(emMovimento(dia, estado.t)));

  // o ponto ao lado de "Frequência" bate no ritmo lido
  if (estado.hr) {
    document.documentElement.style.setProperty(
      "--periodo-fc", `${(60 / estado.hr).toFixed(2)}s`);
  }
  moverCursor(estado.fracao);
}

/** Tempo efetivamente caminhando: desconta as pausas já ocorridas. */
function emMovimento(dia, t) {
  let parado = 0;
  for (const [ini, fim] of dia.paradas ?? []) {
    if (t <= ini) break;
    parado += Math.min(t, fim) - ini;
  }
  return Math.max(0, t - parado);
}

/* --------------------------------------------------- perfil de elevação */

const SVG_L = 320, SVG_A = 96, MARGEM = 8;

export function desenharPerfil(dia) {
  const dists = dia.dist;
  const eles = dia.ele;
  const total = dists[dists.length - 1] || 1;
  const min = Math.min(...eles);
  const max = Math.max(...eles);
  const vao = max - min || 1;

  const x = (d) => (d / total) * SVG_L;
  const y = (e) => MARGEM + (1 - (e - min) / vao) * (SVG_A - 2 * MARGEM);

  // uma amostra a cada ~2 px já descreve a silhueta
  const passo = Math.max(1, Math.floor(dists.length / 240));
  let d = "";
  for (let i = 0; i < dists.length; i += passo) {
    d += `${i === 0 ? "M" : "L"}${x(dists[i]).toFixed(1)},${y(eles[i]).toFixed(1)}`;
  }
  d += `L${SVG_L},${y(eles[eles.length - 1]).toFixed(1)}`;

  $("#perfil-linha").setAttribute("d", d);
  $("#perfil-area").setAttribute("d", `${d}L${SVG_L},${SVG_A}L0,${SVG_A}Z`);
  definir("perfilMin", `${metros(min)} m`);
  definir("perfilMax", `${metros(max)} m`);
}

function moverCursor(fracao) {
  const x = Math.max(0, Math.min(1, fracao)) * SVG_L;
  const c = $("#perfil-cursor");
  c.setAttribute("x1", x);
  c.setAttribute("x2", x);
}

/* ------------------------------------------------------- linha do tempo */

let faixas = [];
let duracoes = [];
let duracaoTotal = 0;

/** Converte uma fração da travessia inteira em (etapa, segundos). */
export function fracaoParaPosicao(fracao) {
  let restante = Math.max(0, Math.min(1, fracao)) * duracaoTotal;
  for (let i = 0; i < duracoes.length; i += 1) {
    if (restante <= duracoes[i] || i === duracoes.length - 1) {
      return { dia: i, tempo: Math.min(restante, duracoes[i]) };
    }
    restante -= duracoes[i];
  }
  return { dia: 0, tempo: 0 };
}

/** O caminho inverso, para manter o controle deslizante em sincronia. */
export function posicaoParaFracao(indiceDia, tempo) {
  let antes = 0;
  for (let i = 0; i < indiceDia; i += 1) antes += duracoes[i];
  return duracaoTotal ? (antes + tempo) / duracaoTotal : 0;
}

export function construirLinhaTempo(dias, midias, aoBuscar) {
  const trilho = $("#trilho");
  const scrub = $("#scrub");
  trilho.innerHTML = "";
  const alca = document.createElement("div");
  alca.className = "alca-tempo";
  alca.id = "alca-tempo";
  faixas = [];
  duracoes = dias.map((d) => d.t[d.t.length - 1]);
  duracaoTotal = duracoes.reduce((a, b) => a + b, 0);

  dias.forEach((dia, i) => {
    const dur = duracoes[i];
    const el = document.createElement("div");
    el.className = "faixa";
    el.style.flex = `${dur / duracaoTotal}`;
    el.style.setProperty("--cor", dia.cor);

    const feito = document.createElement("div");
    feito.className = "faixa-feito";

    // numero e destino separados: em telas estreitas so o numero fica
    const rotulo = document.createElement("span");
    rotulo.className = "faixa-rotulo";
    const num = document.createElement("b");
    num.className = "faixa-n";
    num.textContent = String(dia.n);
    const destino = document.createElement("span");
    destino.className = "faixa-destino";
    destino.textContent = dia.para;
    rotulo.append(num, destino);

    el.append(feito, rotulo);

    midias.filter((m) => m.dia === dia.n).forEach((m) => {
      const marca = document.createElement("i");
      marca.className = "marca-midia";
      marca.style.left = `${(m.t / dur) * 100}%`;
      el.appendChild(marca);
    });

    trilho.appendChild(el);
    faixas.push({ el, feito, dur });
  });
  trilho.appendChild(alca);

  /* O controle é um <input type="range"> de verdade, invisível por cima do
     trilho. Sai de graça: arrastar nos dois sentidos, setas do teclado,
     Home/End e leitura por leitor de tela — nada disso funcionaria com um
     punhado de ouvintes de clique. */
  // O valor é o segundo da travessia, então as setas do teclado andam meio
  // minuto de caminhada por toque, em vez de uma fração imperceptível.
  scrub.max = String(Math.round(duracaoTotal));
  scrub.step = "30";
  scrub.addEventListener("input", () => {
    const { dia, tempo } = fracaoParaPosicao(Number(scrub.value) / duracaoTotal);
    aoBuscar(dia, tempo);
  });
  return scrub;
}

export function atualizarLinhaTempo(indiceDia, tempo, arrastando) {
  faixas.forEach((f, i) => {
    f.el.classList.toggle("atual", i === indiceDia);
    const pct = i < indiceDia ? 100 : i === indiceDia ? (tempo / f.dur) * 100 : 0;
    f.feito.style.width = `${Math.max(0, Math.min(100, pct))}%`;
  });
  const fracao = posicaoParaFracao(indiceDia, tempo);
  const alca = $("#alca-tempo");
  if (alca) alca.style.left = `${fracao * 100}%`;
  if (!arrastando) {
    const scrub = $("#scrub");
    const v = String(Math.round(fracao * duracaoTotal));
    if (scrub.value !== v) scrub.value = v;
  }
}

/* -------------------------------------------------------- card de etapa */

export function preencherResumo(dia, ehUltima, proxima) {
  const r = dia.resumo;
  definir("rDia", String(dia.n));
  definir("rDestino", dia.para);
  campos.rDist.innerHTML = `${km(r.dist)}<i>km</i>`;
  campos.rGanho.innerHTML = `${metros(r.ganho)}<i>m</i>`;
  campos.rPerda.innerHTML = `${metros(r.perda)}<i>m</i>`;
  campos.rEleMax.innerHTML = `${metros(r.eleMax)}<i>m</i>`;
  campos.rMov.textContent = duracao(r.mov);
  campos.rFcMed.innerHTML = `${r.fcMed}<i>bpm</i>`;
  campos.rFcMax.innerHTML = `${r.fcMax}<i>bpm</i>`;
  campos.rKcal.innerHTML = `${metros(r.kcal)}<i>kcal</i>`;
  definir("rProximo", ehUltima ? "Rever a travessia" : `Seguir para ${proxima}`);
}
