# Alta Via 1 — Dolomitas

Mapa de terreno 3D com a travessia de seis dias pela Alta Via 1
(19 a 24 de setembro de 2026), montado a partir dos dados do Apple Watch.

**73,6 km · +4.135 m de subida · −4.099 m de descida · 925 m a 2.731 m de altitude**

| Etapa | Trajeto | Distância | Subida | Descida |
|-------|---------|-----------|--------|---------|
| 1 · 19/09 | Lago di Braies → Rifugio Sennes | 10,1 km | +971 m | −335 m |
| 2 · 20/09 | Rifugio Sennes → Rifugio Fanes | 10,4 km | +565 m | −630 m |
| 3 · 21/09 | Rifugio Fanes → Rifugio Lagazuoi | 13,2 km | +1.095 m | −437 m |
| 4 · 22/09 | Rifugio Lagazuoi → Malga Giau | 9,8 km | +469 m | −593 m |
| 5 · 23/09 | Malga Giau → Passo Staulanza | 14,7 km | +666 m | −914 m |
| 6 · 24/09 | Passo Staulanza → Borca di Cadore | 15,4 km | +369 m | −1.190 m |

---

## Rodar na sua máquina

```bash
cd site
python3 -m http.server 8777
```

Abra <http://localhost:8777>. Precisa ser por HTTP — abrir o `index.html`
direto pelo Finder não funciona, porque o navegador bloqueia a leitura dos
arquivos de dados.

## Adicionar fotos e vídeos

1. Coloque os arquivos em `midias/` (subpastas são percorridas também).
2. Rode `python3 scripts/build_media.py`.

Cada arquivo é posicionado **pelo horário em que foi capturado**, cruzado
com a série temporal do dia. Isso é mais confiável do que o GPS da foto,
que erra feio entre paredes de rocha.

> **Ao exportar do app Fotos, use "Exportar Original Não Modificado".**
> A exportação comum apaga o EXIF de GPS e pode reescrever a data — sem
> isso o script não consegue ancorar a mídia, e ela fica de fora.

O script avisa, ao final, quais arquivos não puderam ser posicionados e por quê.
Ele pode ser rodado quantas vezes quiser: o que já foi convertido é reaproveitado.

Opções úteis:

| Opção | Para quê |
|-------|----------|
| `--fuso +02:00` | Fuso das fotos sem fuso declarado (padrão: CEST, o dos Dolomitas em setembro) |
| `--crf 30` | Comprime mais os vídeos (padrão 26; quanto maior, menor o arquivo) |
| `--altura 720` | Reduz a resolução dos vídeos (padrão 1080) |
| `--forcar` | Refaz todas as conversões do zero |

## Reprocessar o trajeto

```bash
python3 scripts/build_trail.py
```

Só é necessário se os GPX mudarem. Exige `relogio/export.xml`, que **não está
no repositório** (tem 329 MB, acima do limite do GitHub) — reexporte do app
Saúde se precisar.

---

## Publicar

O repositório já traz `.github/workflows/pages.yml`, que publica a pasta
`site/` a cada push na `main`. Para ligar, uma única vez:

**Settings → Pages → Source: GitHub Actions**

O workflow confere se `site/data/days.json` existe antes de publicar, para o
site não ir ao ar sem dados.

### Sobre o peso dos arquivos

Esta é a parte que exige atenção. Os limites do GitHub:

| Limite | Valor | Rigor |
|--------|-------|-------|
| Arquivo individual | 100 MB | **bloqueia o push** |
| Site publicado | 1 GB | recomendado |
| Repositório | 1 GB | recomendado |
| Banda | 100 GB/mês | limite flexível |

Três decisões já embutidas no projeto para caber nisso com folga:

1. **As mídias originais nunca entram no repositório.** `midias/` está no
   `.gitignore`. Só os derivados otimizados de `site/media/` são versionados.
   Isso importa porque o Git guarda todas as versões para sempre: um HEIC de
   5 MB commitado por engano pesa no clone de todo mundo, para sempre.

2. **Fotos viram WebP a 2000 px** — cerca de 200 KB cada, contra 340 KB em
   JPEG e 3 a 5 MB no original. Mesmo com 300 fotos, dá uns 60 MB.

3. **Vídeos viram MP4 h264 a 1080p.** São eles que pesam: algo entre 3 e
   8 MB por minuto. O `build_media.py` imprime o total ao final e avisa se
   algum arquivo passar de 60 MB ou se o conjunto passar de 700 MB.

**Se os vídeos estourarem o orçamento**, nesta ordem:

- `--crf 30 --altura 720` costuma cortar o tamanho pela metade;
- se ainda assim não couber, hospede os vídeos fora (YouTube não listado,
  Cloudflare R2, Backblaze B2) e troque o `src` no `media.json`.

> **Git LFS não resolve.** O GitHub Pages não baixa os objetos do LFS: ele
> entrega o arquivo-ponteiro em texto, e o vídeo simplesmente não toca.

---

## Como funciona

```
relogio/*.gpx + export.xml ──▶ scripts/build_trail.py ──▶ site/data/days.json
midias/*                   ──▶ scripts/build_media.py ──▶ site/data/media.json
                                                          site/media/*
```

### Tratamento dos dados

O GPS grava a 1 Hz: 129.266 pontos ao todo. Dois cuidados no processamento:

- **Altitudes inválidas.** Quando o altímetro falha, o relógio grava
  `vAcc="-1"` e `ele="0"`. Sem filtrar isso, o ganho de elevação do dia 23
  dava 5.236 m — impossível. Esses pontos têm a altitude descartada e
  interpolada; as coordenadas continuam válidas.
- **Ganho e perda** usam uma referência móvel com limiar de 3 m, sobre a
  elevação já suavizada, para que o ruído do altímetro não vire subida falsa.

Os 129 mil pontos são reduzidos a cerca de 15 mil (≈180 KB comprimidos),
unindo os vértices do Douglas–Peucker (ε = 2,5 m, preserva as curvas
fechadas) a uma amostra a cada 10 s (dá resolução à frequência cardíaca).

### Frontend

HTML, CSS e JavaScript puros, sem build. [MapLibre GL JS][ml] v6 carregado
como módulo ESM.

O relevo não é imagem de satélite: a altitude é colorida por uma camada
`color-relief` na paleta do projeto, com um `hillshade` por cima dando
textura. O terreno fica em tons frios e dessaturados justamente para que as
trilhas quentes sobressaiam.

A linha cresce sem recriar geometria — o avanço só reescreve a expressão de
`line-gradient`, que corta a linha via `line-progress`.

Dados de relevo: [Mapterhorn][mt] (sem necessidade de chave de API).

[ml]: https://maplibre.org/maplibre-gl-js/docs/
[mt]: https://mapterhorn.com/

### Arquivos

```
relogio/          GPX e export do Apple Health (fonte; não versionado)
midias/           suas fotos e vídeos (não versionado)
scripts/          processamento em Python, sem dependências externas
site/             o site publicado
  ├── data/       JSON gerado
  └── media/      fotos e vídeos otimizados
```
