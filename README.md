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

## Estado das mídias

| Etapa | Fotos | Vídeos | No repositório | No bucket R2 |
|-------|-------|--------|----------------|--------------|
| 1 · Braies → Sennes | 88 | 38 | 60 MB | 247 MB |
| 2 · Sennes → Fanes | 69 | — | 50 MB | — |
| 3 a 6 | — | — | — | — |

### Quando o arquivo perdeu a data

Alguns aplicativos reexportam a mídia e apagam tudo — o **DJI Mimo** é um
deles: o `creation_time` do arquivo exportado é a hora da exportação, e não
sobra nenhum vestígio da gravação, nem nos bytes, nem nos atributos do
macOS, nem na Fototeca.

Para esses casos, crie `midias/_datas.json` com o instante real de cada um:

```json
{
  "1790947806725.MOV": "2026-09-20T12:34:56+02:00",
  "1790948047577.MOV": "2026-09-20T12:41:10+02:00"
}
```

Essa tabela tem prioridade sobre qualquer metadado embutido. O próprio
script imprime um esqueleto dela ao final, listando o que não conseguiu
ancorar.

**Para preencher a tabela sozinho**, se você ainda tiver os arquivos crus:

```bash
python3 scripts/datar_por_originais.py --originais /Volumes/DJI/DCIM
python3 scripts/datar_por_originais.py --originais /Volumes/DJI/DCIM --aplicar
```

O script acha, para cada vídeo editado, qual original tem o mesmo conteúdo,
e copia dali a data de gravação. Compara a **imagem**, não a duração, então
funciona mesmo com cortes e mudança de velocidade: cada quadro vira uma
assinatura de 256 bits (dHash sobre 16×16 em tons de cinza, com equalização
de histograma para tolerar correção de cor).

Quem decide é a **margem** sobre o segundo colocado, não a distância
absoluta — recompressão afasta todo mundo por igual. O que ficar em dúvida
é listado em vez de adivinhado. Ao final ele ainda confere se a ordem de
exportação bate com a de gravação, o que é um segundo indício, independente
da imagem.

Os originais são lidos onde estiverem; nada é copiado para o projeto.

> **Fotos vindas do WhatsApp não têm EXIF nenhum** — o aplicativo apaga tudo,
> inclusive a data. Para elas o script lê o horário do **nome do arquivo**
> (`PHOTO-AAAA-MM-DD-HH-MM-SS.jpg`), interpretado no fuso desta máquina, que
> foi quem exportou. Vale conferir uma ou outra pelo conteúdo: se a foto não
> combinar com a altitude da legenda, o fuso do nome é outro.

Bucket: `https://pub-b469c0ff44ae40a6b799c069e44960ef.r2.dev`

## Rodar na sua máquina

```bash
cd docs
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

## Marcar um ponto no meio da etapa

Partida e chegada são rotuladas automaticamente. Para nomear algo no meio do
caminho — um refúgio por onde se passou sem dormir, por exemplo — acrescente
em `scripts/build_trail.py`:

```python
MARCOS = {
    "2026-09-19": [("Rifugio Biella", 46.6656312, 12.0845833)],
}
```

As coordenadas saem do OpenStreetMap. O script procura o ponto do trajeto
mais próximo, calcula o tempo de caminhada até ali e **avisa se o ponto cair
a mais de 120 m da trilha** — sinal de coordenada errada. Depois é só rodar
`build_trail.py` de novo.

## Reprocessar o trajeto

```bash
python3 scripts/build_trail.py
```

Só é necessário se os GPX mudarem. Exige `relogio/export.xml`, que **não está
no repositório** (tem 329 MB, acima do limite do GitHub) — reexporte do app
Saúde se precisar.

---

## Publicar

O site mora em `docs/`, que é uma das pastas que o GitHub Pages publica
direto. Para ligar, uma única vez:

**Settings → Pages → Source: Deploy from a branch → Branch: `main` / `/docs`
→ Save**

Daí em diante, todo push na `main` republica o site sozinho. Sem GitHub
Actions, sem configuração extra, sem nada que possa quebrar.

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
   `.gitignore`. Só os derivados otimizados de `docs/media/` são versionados.
   Isso importa porque o Git guarda todas as versões para sempre: um HEIC de
   5 MB commitado por engano pesa no clone de todo mundo, para sempre.

2. **Fotos viram WebP a 2000 px** — cerca de 200 KB cada, contra 340 KB em
   JPEG e 3 a 5 MB no original. Mesmo com 300 fotos, dá uns 60 MB.

3. **Vídeos viram MP4 h264 a 1080p.** São eles que pesam: algo entre 3 e
   8 MB por minuto. O `build_media.py` imprime o total ao final e avisa se
   algum arquivo passar de 60 MB ou se o conjunto passar de 700 MB.

> **Git LFS não resolve.** O GitHub Pages não baixa os objetos do LFS: ele
> entrega o arquivo-ponteiro em texto, e o vídeo simplesmente não toca.

### Vídeos fora do repositório

Para bastante vídeo em alta qualidade, o caminho é tirá-los do Git. Diga uma
vez onde eles vão morar:

```bash
python3 scripts/build_media.py --videos-em "https://seu-bucket.r2.dev/dolomitas"
```

A partir daí o script passa a:

- converter os vídeos para `videos_para_subir/` em vez de `docs/media/`;
- gerar o **poster** de cada vídeo em `docs/media/` (poucos KB, fica no Git,
  e é o que aparece enquanto o vídeo carrega);
- apontar o `src` do `media.json` para a sua URL.

Depois é só subir o conteúdo de `videos_para_subir/` para o bucket. O
endereço fica guardado em `scripts/config.json`; `--videos-aqui` desfaz e
volta tudo para dentro do repositório.

**Onde hospedar.** O [Cloudflare R2][r2] é a melhor opção para este caso:
10 GB de armazenamento na camada gratuita e, o que mais importa aqui,
**sem cobrança de banda de saída** — vídeo é justamente onde a banda pesa. O
[Backblaze B2][b2] também serve.

> **O endereço da API S3 não serve aqui.** O que o painel do R2 mostra como
> *S3 API* (`https://<conta>.r2.cloudflarestorage.com/<bucket>`) exige
> requisição assinada; o navegador não assina nada ao carregar um `<video>`,
> e a resposta é `400 InvalidArgument: Authorization`. O endereço que o site
> precisa é um destes dois:
>
> - **Domínio público de desenvolvimento** — no bucket, em
>   *Settings → Public Development URL → Enable*. Sai algo como
>   `https://pub-<hash>.r2.dev`. Serve para começar, mas a Cloudflare
>   limita a taxa e desaconselha para uso definitivo.
> - **Domínio próprio** — *Settings → Custom Domains*, apontando por exemplo
>   `midias.seusite.com` para o bucket. É o caminho recomendado: sem limite
>   de taxa e com cache da CDN.
>
> Com o endereço em mãos, basta reapontar; nada é reconvertido:
> ```bash
> python3 scripts/build_media.py --videos-em "https://pub-xxxx.r2.dev"
> ```

Em qualquer hospedagem, libere o **CORS** para o domínio do site, senão o
navegador recusa o vídeo.

### Subir os vídeos

Os arquivos ficam prontos em `videos_para_subir/`, com os nomes exatos que
o `media.json` espera. Eles vão na **raiz do bucket**, sem subpasta.

Para um lote só, o painel da Cloudflare resolve: abra o bucket, *Upload →
Select files*, selecione tudo e confirme.

Para repetir a cada etapa, vale instalar o [rclone][rc]:

```bash
brew install rclone
rclone config          # tipo: s3 → provedor: Cloudflare R2 → suas chaves
rclone copy videos_para_subir/ r2:dolomitas --progress
```

As chaves de API saem em *R2 → Manage API Tokens*. Elas ficam só na sua
máquina — não entram no repositório.

Se um vídeo ainda não estiver no bucket, o site mostra o poster com uma
explicação, em vez de um quadro preto. Dá para publicar antes de terminar
o upload.

[rc]: https://rclone.org/s3/#cloudflare-r2

Se um vídeo não carregar, o site mostra o poster com uma explicação em vez
de um quadro preto.

[r2]: https://developers.cloudflare.com/r2/
[b2]: https://www.backblaze.com/cloud-storage

---

## Como funciona

```
relogio/*.gpx + export.xml ──▶ scripts/build_trail.py ──▶ site/data/days.json
midias/*                   ──▶ scripts/build_media.py ──▶ site/data/media.json
                                                          docs/media/*
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
relogio/          GPX e export do Apple Health (fonte)
midias/           suas fotos e vídeos originais (não versionado)
videos_para_subir/  vídeos convertidos, prontos para o bucket (não versionado)
scripts/          processamento em Python, sem dependências externas
docs/             o site publicado — é esta pasta que o GitHub Pages serve
  ├── data/       JSON gerado
  └── media/      fotos otimizadas
```
