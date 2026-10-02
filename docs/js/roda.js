/**
 * Roda de bússola para girar a câmera à mão.
 *
 * Serve para contornar uma crista que esconde o traçado: gira-se a cena até
 * a trilha reaparecer. Arrastar a roda solta o rumo automático — a câmera
 * continua acompanhando o caminhante, só para de girar sozinha.
 */

const PASSO_TECLADO = 5;      // graus por toque de seta
const PASSO_RODA = 4;         // graus por entalhe da roda do mouse

export function instalarRoda(mapa, aoGirarManualmente) {
  const roda = document.getElementById("roda");
  const disco = roda.querySelector(".roda-disco");
  const valor = roda.querySelector(".roda-valor");

  const mostrar = () => {
    const b = mapa.getBearing();
    // O disco gira ao contrário do rumo: assim o "N" aponta mesmo para o
    // norte da cena, como numa bússola de verdade.
    disco.style.rotate = `${-b}deg`;
    const graus = Math.round((b + 360) % 360);
    valor.textContent = `${graus}°`;
    roda.setAttribute("aria-valuenow", String(graus));
  };

  const anguloDoPonteiro = (ev) => {
    const r = roda.getBoundingClientRect();
    return Math.atan2(ev.clientY - (r.top + r.height / 2),
                      ev.clientX - (r.left + r.width / 2)) * 180 / Math.PI;
  };

  let anguloInicial = 0;
  let rumoInicial = 0;

  roda.addEventListener("pointerdown", (ev) => {
    ev.preventDefault();
    roda.setPointerCapture(ev.pointerId);
    roda.classList.add("girando");
    anguloInicial = anguloDoPonteiro(ev);
    rumoInicial = mapa.getBearing();
    aoGirarManualmente?.();
  });

  roda.addEventListener("pointermove", (ev) => {
    if (!roda.hasPointerCapture(ev.pointerId)) return;
    // Subtrai porque é a rosa dos ventos que segue o dedo, não a câmera.
    mapa.setBearing(rumoInicial - (anguloDoPonteiro(ev) - anguloInicial));
  });

  const soltar = (ev) => {
    if (roda.hasPointerCapture(ev.pointerId)) roda.releasePointerCapture(ev.pointerId);
    roda.classList.remove("girando");
  };
  roda.addEventListener("pointerup", soltar);
  roda.addEventListener("pointercancel", soltar);

  roda.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    aoGirarManualmente?.();
    mapa.setBearing(mapa.getBearing() + Math.sign(ev.deltaY) * PASSO_RODA);
  }, { passive: false });

  // Teclado: a roda é um slider, então setas giram e Home volta ao norte.
  roda.addEventListener("keydown", (ev) => {
    const giro = { ArrowLeft: -PASSO_TECLADO, ArrowRight: PASSO_TECLADO,
                   ArrowDown: -PASSO_TECLADO, ArrowUp: PASSO_TECLADO }[ev.key];
    if (giro === undefined && ev.key !== "Home") return;
    ev.preventDefault();
    ev.stopPropagation();
    aoGirarManualmente?.();
    mapa.setBearing(ev.key === "Home" ? 0 : mapa.getBearing() + giro);
  });

  // Dois toques devolvem o norte para cima, que é a referência de leitura.
  roda.addEventListener("dblclick", (ev) => {
    ev.preventDefault();
    aoGirarManualmente?.();
    mapa.easeTo({ bearing: 0, duration: 420 });
  });

  mapa.on("rotate", mostrar);
  mostrar();
  return { mostrar };
}
