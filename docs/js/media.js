/**
 * Fotos e vídeos ancorados no trajeto.
 *
 * Com o interruptor ligado, a travessia pausa sozinha ao alcançar cada mídia
 * e só continua quando o "X" é clicado. Desligado, os pinos seguem no mapa
 * e podem ser abertos a qualquer momento sem interromper o fluxo.
 *
 * Os pinos são uma camada do mapa (ver adicionarPinosMidia): marcador HTML
 * ignora a altitude e flutua fora da trilha quando o relevo 3D está ligado.
 */

import { filtrarPinos } from "./map.js";

export class Galeria {
  constructor(mapa, midias, ganchos = {}) {
    this.mapa = mapa;
    this.midias = midias;
    this.ganchos = ganchos;
    this.ativa = null;
    this.vistas = new Set();
    // A travessia começa mostrando só o trajeto; o interruptor "Mídias"
    // é quem liga as paradas automáticas. main.js sincroniza com a caixa.
    this.automatico = false;
    this.diaAtual = undefined;

    this.painel = document.getElementById("midia");
    this.conteudo = document.getElementById("midia-conteudo");
    this.quadro = this.painel.querySelector(".midia-quadro");
    this.hora = document.querySelector('[data-campo="mHora"]');
    this.legenda = document.querySelector('[data-campo="mLegenda"]');
    this.contador = document.querySelector('[data-campo="mContador"]');

    // Modo teatro: a mídia toma o palco e o mapa vira faixa embaixo.
    this.teatro = false;
    this.palco = document.getElementById("palco");
    this.tira = document.getElementById("tira");
    this.botaoTeatro = document.getElementById("midia-teatro");
    this.botaoTeatro.addEventListener("click", () => this.alternarTeatro());
    this.instalarDivisor();

    document.getElementById("midia-fechar")
      .addEventListener("click", () => this.fechar());

    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && this.ativa) {
        ev.preventDefault();
        this.fechar();
      }
    });
    document.getElementById("midia-ant")
      .addEventListener("click", () => this.passar(-1));
    document.getElementById("midia-prox")
      .addEventListener("click", () => this.passar(1));

    this.ligarPinos();
  }

  /** Clique e ponteiro sobre a camada de pinos. */
  ligarPinos() {
    const abrirDoMapa = (ev) => {
      const f = ev.features?.[0];
      if (!f) return;
      this.abrir(this.midias[f.properties.indice], true);
    };
    this.mapa.on("click", "midias", abrirDoMapa);
    this.mapa.on("mouseenter", "midias", () => {
      this.mapa.getCanvas().style.cursor = "pointer";
    });
    this.mapa.on("mouseleave", "midias", () => {
      this.mapa.getCanvas().style.cursor = "";
    });
  }

  /** Só a etapa em curso mostra pinos. */
  ajustarPinos(diaAtual = this.diaAtual) {
    this.diaAtual = diaAtual;
    filtrarPinos(this.mapa, diaAtual);
    if (this.teatro) this.montarTira();
  }

  /* ---------------------------------------------------------- teatro */

  alternarTeatro(ligado = !this.teatro) {
    if (ligado === this.teatro) return;
    this.teatro = ligado;
    this.palco.classList.toggle("teatro", ligado);
    this.botaoTeatro.setAttribute("aria-pressed", String(ligado));
    this.botaoTeatro.setAttribute(
      "aria-label", ligado ? "Sair da tela cheia" : "Ver em tela cheia");

    if (ligado) {
      this.montarTira();
      this.reajustarFaixa();
    } else {
      this.tira.replaceChildren();
    }

    // A mídia foi medida para o painel de canto; no teatro quem manda é a grade.
    if (this.ativa) this.ajustarLargura(this.ativa);
    this.ganchos.aoTeatro?.(ligado);
  }

  /**
   * Tira de miniaturas da etapa, na ordem em que as mídias foram feitas.
   * É a única maneira de ver o que existe sem percorrer o dia inteiro.
   */
  montarTira() {
    const lista = this.doDia;
    this.tira.replaceChildren(...lista.map((m) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = m.tipo === "video" ? "tira-item tira-video" : "tira-item";
      b.setAttribute("aria-current", String(this.ativa?.id === m.id));
      b.dataset.id = m.id;

      const img = document.createElement("img");
      img.src = m.thumb;
      img.alt = "";
      img.loading = "lazy";       // uma etapa tem mais de cem miniaturas
      img.decoding = "async";

      const hora = document.createElement("span");
      hora.className = "tira-hora";
      hora.textContent = m.hora;

      b.append(img, hora);
      b.addEventListener("click", () => {
        if (this.ativa?.id === m.id) return;
        this.abrir(m, true);
        this.ganchos.aoPular?.(m);
      });
      return b;
    }));
    this.realcarTira();
  }

  /** Marca a miniatura em exibição e a traz para a vista. */
  realcarTira() {
    if (!this.teatro) return;
    let alvo = null;
    for (const b of this.tira.children) {
      const eu = b.dataset.id === this.ativa?.id;
      b.setAttribute("aria-current", String(eu));
      if (eu) alvo = b;
    }
    alvo?.scrollIntoView({ block: "nearest", inline: "center",
                           behavior: "smooth" });
  }

  /**
   * Divisor entre a tira e o mapa. A altura vive numa variável do palco,
   * para o CSS continuar dono da grade; o mapa só precisa ser avisado.
   */
  instalarDivisor() {
    const divisor = document.getElementById("divisor");
    const limites = () => {
      const alturaPalco = this.palco.getBoundingClientRect().height;
      return [110, Math.max(140, alturaPalco * 0.6)];
    };
    const aplicar = (px) => {
      const [min, max] = limites();
      this.palco.style.setProperty(
        "--mapa-alt", `${Math.round(Math.min(max, Math.max(min, px)))}px`);
      this.mapa.resize();
    };
    /* A altura arrastada fica em pixels e sobrevive à janela mudando de
       tamanho. Numa janela menor ela sufocaria a mídia, então o teatro
       reaplica o valor pelo mesmo limite ao entrar e a cada redimensionamento. */
    this.reajustarFaixa = () => {
      const guardado = this.palco.style.getPropertyValue("--mapa-alt");
      if (guardado) aplicar(parseFloat(guardado));
    };

    let arrastando = false;
    divisor.addEventListener("pointerdown", (ev) => {
      if (!this.teatro) return;
      arrastando = true;
      divisor.setPointerCapture(ev.pointerId);
      this.palco.classList.add("redimensionando");
      ev.preventDefault();
    });
    divisor.addEventListener("pointermove", (ev) => {
      if (!arrastando) return;
      aplicar(this.palco.getBoundingClientRect().bottom - ev.clientY);
    });
    const soltar = () => {
      if (!arrastando) return;
      arrastando = false;
      this.palco.classList.remove("redimensionando");
    };
    divisor.addEventListener("pointerup", soltar);
    divisor.addEventListener("pointercancel", soltar);

    // Teclado: o divisor é um separator, e setas são o gesto esperado dele.
    divisor.addEventListener("keydown", (ev) => {
      if (!this.teatro) return;
      const passo = ev.key === "ArrowUp" ? 24 : ev.key === "ArrowDown" ? -24 : 0;
      if (!passo) return;
      ev.preventDefault();
      ev.stopPropagation();
      aplicar(this.mapa.getContainer().getBoundingClientRect().height + passo);
    });
  }

  /** Mídias da etapa em curso, na ordem em que foram feitas. */
  get doDia() {
    return this.midias.filter((m) => m.dia === this.diaAtual);
  }

  /**
   * Procura a mídia que acabou de ser alcançada nesta etapa.
   * A janela de meio minuto evita que um salto grande de tempo pule o item.
   */
  verificar(dia, tempo) {
    /* Fora do teatro, a mídia aberta é quem segura a travessia: só o "X"
       libera o caminho, e procurar a próxima com uma ainda na tela abriria
       duas ao mesmo tempo. No teatro não existe esse estado — há sempre uma
       mídia em cartaz —, e manter a trava fazia a travessia passar reto por
       todas as seguintes. Lá a próxima simplesmente toma o lugar da anterior. */
    if (!this.automatico || (this.ativa && !this.teatro)) return;
    const achado = this.midias.find(
      (m) => m.dia === dia.n &&
             // As mídias feitas antes de partir e já no refúgio ficam presas
             // à ponta do trajeto. Se abrissem sozinhas, as cinco do café da
             // manhã se enfileirariam em t=0 e a caminhada nunca começaria.
             // Continuam acessíveis pelas setas e pelos pinos.
             m.fase === "trajeto" &&
             !this.vistas.has(m.id) &&
             tempo >= m.t &&
             tempo - m.t < 30,
    );
    if (achado) this.abrir(achado, false);
  }

  /** Avança ou retrocede para a mídia vizinha dentro da etapa. */
  passar(direcao) {
    const lista = this.doDia;
    if (!lista.length) return;
    const atual = this.ativa ? lista.findIndex((m) => m.id === this.ativa.id) : -1;
    const proximo = atual < 0
      ? (direcao > 0 ? 0 : lista.length - 1)
      : Math.min(lista.length - 1, Math.max(0, atual + direcao));
    if (proximo === atual) return;
    this.abrir(lista[proximo], true);
    // leva a travessia até o ponto da foto, para o mapa acompanhar
    this.ganchos.aoPular?.(lista[proximo]);
  }

  abrir(m, manual) {
    if (this.ativa?.id === m.id) return;
    const anterior = this.ativa;
    this.ativa = m;
    this.vistas.add(m.id);

    // o painel reserva a proporção exata antes de a mídia chegar
    if (m.w && m.h) this.quadro.style.setProperty("--prop", `${m.w} / ${m.h}`);
    else this.quadro.style.removeProperty("--prop");

    this.conteudo.replaceChildren(this.montar(m));
    this.hora.textContent = m.hora;
    this.legenda.textContent = m.legenda;
    this.painel.hidden = false;
    this.ajustarLargura(m);        // depois de visível: precisa medir o painel

    const lista = this.doDia;
    const pos = lista.findIndex((x) => x.id === m.id);
    this.contador.textContent = pos >= 0 ? `${pos + 1}/${lista.length}` : "";
    document.getElementById("midia-ant").disabled = pos <= 0;
    document.getElementById("midia-prox").disabled = pos >= lista.length - 1;

    this.realcar(anterior, false);
    this.realcar(m, true);
    this.realcarTira();
    this.ganchos.aoAbrir?.(m, manual);
  }

  /**
   * Em tela larga o painel encolhe para caber a mídia sem tarja ao lado.
   * Uma foto em pé ocuparia só o meio de um painel largo; o resto seria
   * fundo escuro à toa. Em retrato o painel é uma folha de largura cheia.
   */
  ajustarLargura(m) {
    this.painel.style.removeProperty("width");
    this.quadro.style.removeProperty("height");
    // No teatro a mídia preenche a célula da grade: medir em pixels aqui só
    // serviria para brigar com o CSS.
    if (this.teatro || !m.w || !m.h) return;

    const proporcao = m.w / m.h;
    const folha = window.matchMedia(
      "(orientation: portrait), (max-width: 760px)").matches;

    /* A altura do quadro é fixada em pixels, e não deixada à mercê do
       aspect-ratio: numa foto em pé a proporção pedia mais altura do que o
       painel tem, a grade transbordava e a imagem saía cortada, levando as
       setas de navegação para fora da tela junto. */
    const legenda = this.painel.querySelector(".midia-legenda");
    const passos = this.painel.querySelector(".midia-passos");
    const cromo = legenda.offsetHeight + passos.offsetHeight;

    // O teto vem do palco, não do max-height do CSS: aquele valor é uma
    // expressão min() e não se deixa ler como número.
    const palco = this.mapa.getContainer().getBoundingClientRect();
    // Num celular deitado sobra largura e falta altura: se o painel ficasse
    // com a mesma fatia de sempre, a foto viraria uma miniatura.
    const fatia = window.innerHeight < 520 ? 0.86 : 0.56;
    const teto = folha
      ? Math.min(window.innerHeight * 0.62, window.innerHeight - 24)
      : palco.height * fatia;
    const maxQuadro = Math.max(150, teto - cromo);

    if (folha) {
      const largura = this.painel.clientWidth || window.innerWidth - 16;
      this.quadro.style.height =
        `${Math.round(Math.min(maxQuadro, largura / proporcao))}px`;
      return;
    }

    const maxLargura = Math.min(window.innerWidth * 0.3, 380);
    const altura = Math.min(maxQuadro, maxLargura / proporcao);
    this.quadro.style.height = `${Math.round(altura)}px`;
    // piso de largura para a legenda não quebrar em várias linhas
    this.painel.style.width = `${Math.round(Math.max(260, altura * proporcao))}px`;
  }

  /** Destaca (ou apaga) o pino correspondente na camada. */
  realcar(m, ligado) {
    if (!m || !this.mapa.getSource("midias")) return;
    const i = this.midias.indexOf(m);
    if (i >= 0) this.mapa.setFeatureState({ source: "midias", id: i }, { ativa: ligado });
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
    // Sem mídia o teatro não tem assunto: fechar é sair dele.
    if (this.teatro) this.alternarTeatro(false);
    this.painel.hidden = true;
    this.conteudo.replaceChildren();
    this.realcar(fechada, false);
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
