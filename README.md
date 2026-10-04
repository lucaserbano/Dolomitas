# Alta Via 1 — Dolomitas

Mapa de terreno 3D com a travessia de seis dias pela Alta Via 1
(19 a 24 de setembro de 2026), montado a partir dos dados do Apple Watch.

**76,1 km · +4.252 m de subida · −4.157 m de descida · 925 m a 2.731 m de altitude**

| Etapa | Trajeto | Distância | Subida | Descida |
|-------|---------|-----------|--------|---------|
| 1 · 19/09 | Lago di Braies → Rifugio Sennes | 10,1 km | +971 m | −335 m |
| 2 · 20/09 | Rifugio Sennes → Rifugio Fanes | 10,4 km | +565 m | −630 m |
| 3 · 21/09 | Rifugio Fanes → Rifugio Valparola | 15,6 km | +1.212 m | −495 m |
| 4 · 22/09 | Rifugio Valparola → Malga Giau | 9,8 km | +469 m | −593 m |
| 5 · 23/09 | Malga Giau → Passo Staulanza | 14,7 km | +666 m | −914 m |
| 6 · 24/09 | Passo Staulanza → Borca di Cadore | 15,4 km | +369 m | −1.190 m |

> **A etapa 3 não termina onde o relógio parou.** A atividade foi encerrada no
> alto do Lagazuoi, mas o dia seguiu: teleférico até o Passo Falzarego e mais
> 2,4 km de trilha até o Rifugio Valparola. Esse pedaço não tem GPS e está
> traçado à mão — veja [Trechos sem registro do relógio](#trechos-sem-registro-do-relógio).
>
> **E a 4 não começa onde o relógio ligou.** O dia saiu do Rifugio Valparola,
> mas de ônibus até o início da trilha; o GPX só começa 2,5 km adiante, ao lado
> do Passo Falzarego. É a única emenda da travessia em que a linha do mapa dá
> um salto — nas outras cinco, o fim de uma etapa e o começo da seguinte ficam
> a menos de 400 m um do outro.

---

## Estado das mídias

| Etapa | Fotos | Vídeos | No repositório | No bucket R2 |
|-------|-------|--------|----------------|--------------|
| 1 · Braies → Sennes | 88 | 38 | 56 MB | 247 MB |
| 2 · Sennes → Fanes | 71 | 15 | 54 MB | 79 MB |
| 3 · Fanes → Valparola | 91 | 36 | 52 MB | 168 MB |
| 4 · Valparola → Malga Giau | 67 | 27 | 30 MB | 135 MB |
| 5 · Malga Giau → Staulanza | 62 | 22 | 31 MB | 144 MB |
| 6 · Staulanza → Borca | 48 | 9 | 23 MB | 163 MB |
| **total** | **427** | **147** | **245 MB** | **936 MB** |

Três fotos do dia 24 têm data de 25/09 e ficaram de fora: ou são do dia
seguinte, ou perderam o EXIF. Para entrarem, é só dar a hora em `_hora_real`.

### Quando o arquivo perdeu a data

Alguns aplicativos reexportam a mídia e apagam tudo — o **DJI Mimo** é um
deles: o `creation_time` do arquivo exportado é a hora da exportação, e não
sobra nenhum vestígio da gravação, nem nos bytes, nem nos atributos do
macOS, nem na Fototeca.

Para esses casos, crie `midias/_datas.json` com o instante real de cada um:

```json
{
  "_ajuste_minutos": -54,
  "_relogio_da_camera": {
    "1790947806725.MOV": "2026-09-20T12:34:56+02:00",
    "1790948047577.MOV": "2026-09-20T12:41:10+02:00"
  },
  "_hora_real": {
    "PHOTO-2026-09-21-15-48-00.jpg": "2026-09-21T11:08:00+02:00"
  }
}
```

São duas seções porque as horas não vêm todas da mesma fonte.
`_relogio_da_camera` são as lidas do nome do clipe no cartão — e o relógio
da câmera pode estar adiantado, então só essas andam com `_ajuste_minutos`.
`_hora_real` é hora já conferida por outro caminho, e não se mexe nela.

Essa tabela tem prioridade sobre qualquer metadado embutido. O próprio
script imprime um esqueleto dela ao final, listando o que não conseguiu
ancorar.

**Para parear à mão**, que é o caminho que funciona com a Osmo 360:

```bash
python3 scripts/parear_osmo.py --dia 3 \
    --exportados "midias/D3 Fanes-Valparola" \
    --cartao /Volumes/Untitled/DCIM/CAM_001
```

`--exportados` também aceita o caminho de um disco externo, e `--saida`
escolhe onde a página é escrita — útil para montar uma etapa por vez.

Isso monta uma página em `pareamento/` com os exportados de um lado e os
clipes do cartão do outro, cada um com três quadros, a hora já corrigida e
o ponto da trilha onde você estava. O exportado em foco fica grande no alto
da coluna, grudado ali enquanto a lista rola — é dele que se procura o par.
Clicar num e depois no outro monta o `_datas.json` inteiro, pronto para
copiar. Como a exportação respeita a ordem da gravação, a página apaga os
clipes que não cabem entre os vizinhos já pareados — sem travar nada, só para
o olho ir direto ao que interessa.

> **Os quadros do cartão são desentortados antes de virar miniatura.** O cru
> da Osmo 360 é um par de olhos de peixe lado a lado; encolhido vira duas
> bolhas em que não se enxerga nada. O filtro `v360` do ffmpeg reprojeta para
> equirretangular, e um corte vertical joga fora o zênite, que é só céu, e o
> nadir, que é o bastão:
>
> ```
> v360=dfisheye:e:ih_fov=193:iv_fov=193:w=960:h=480,crop=960:300:0:90
> ```
>
> Sobram 56° para cima e para baixo, onde estão os picos e a trilha. As fotos
> `.JPG` do cartão já saem costuradas da câmera e só levam o corte.

A segunda aba, **Sem data**, recebe tudo que não tem hora de captura em lugar
nenhum — fotos do WhatsApp e arquivos que perderam o EXIF —, com as mídias
que têm hora própria servindo de referência: clicar numa delas empresta a
hora. Uma data fora da janela da travessia é descartada em vez de aceita: o
Spotlight devolve a data do sistema de arquivos quando não há metadado algum,
e isso é a hora em que o arquivo foi copiado, não em que a foto foi feita.

Publicar essa página como artifact é o jeito mais confortável de usá-la;
`pareamento/` fica fora do repositório.

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

> **O que é "um exportado" não se decide pelo nome.** O Mimo já trocou de
> padrão mais de uma vez: nas etapas 2 a 4 os clipes saíram como
> `1791053951232.MOV`, o instante da exportação em milissegundos; nas etapas 5
> e 6, como `D5_0000_V1-0001.mov`. O que define um exportado é não ter hora de
> captura em lugar nenhum — e, sendo vídeo, o cartão é o único lugar onde essa
> hora sobrou. É assim que a página os separa.

> **O cruzamento automático não funciona com fonte 360.** Foi testado contra
> o cartão da Osmo 360 e falhou: o cru é dual fisheye e o exportado é um
> recorte reenquadrado dele, então as assinaturas ficam em 0,39–0,44 quando
> o acaso é 0,50. Pior, a atribuição muda conforme os parâmetros — sinal de
> que nada está decidindo. Vinte e três clipes do mesmo dia, mesma luz e
> mesmas campinas são genuinamente parecidos demais. Para esses casos o
> caminho é parear à mão e preencher o `_datas.json`.

> **Fotos vindas do WhatsApp não têm EXIF nenhum** — o aplicativo apaga tudo,
> inclusive a data. Para elas o script lê o horário do **nome do arquivo**
> (`PHOTO-AAAA-MM-DD-HH-MM-SS.jpg`), interpretado no fuso desta máquina, que
> foi quem salvou.
>
> **Mas esse horário é o da mensagem, não o da foto.** O nome bate, ao
> segundo, com o `birthtime` do arquivo lido no fuso de São Paulo: é a hora
> em que a mensagem chegou ao Mac, e o Mac estava em horário de Brasília.
> Quando o grupo troca as fotos do dia só à noite — como no dia 21, em que
> as 26 fotos chegaram entre 20h16 e 20h49 de Roma, com a imagem em pleno
> sol — o nome marca o jantar, e não o trecho da trilha.
>
> Quando as duas horas coincidirem, o nome serve. Quando não, a foto entra
> em `_hora_real`, com a hora tirada de uma foto da Canon do mesmo trecho —
> é o que a página do `parear_osmo.py` faz.

> **HEIC do iPhone: o `sips` antes do Spotlight.** A Pillow não abre HEIC sem
> plugin, então a data desses arquivos vinha do `mdls`. Os dois leem o mesmo
> EXIF, mas o Spotlight carimba nele o fuso **desta máquina** — para uma foto
> feita na Europa e copiada no Brasil são cinco horas de erro, o bastante para
> jogá-la no trecho errado da etapa. O `sips`, que também já vem no macOS,
> devolve a hora como ela está no arquivo, sem fuso, e aí vale o `--fuso`.

Bucket: `https://pub-b469c0ff44ae40a6b799c069e44960ef.r2.dev`

## A capa

A foto de abertura é `docs/img/capa-2400.webp` (e a de 1200 px para telas
pequenas), gerada da original com:

```python
from PIL import Image
im = Image.open("sua-foto.jpg").convert("RGB")
for larg, q in ((2400, 80), (1200, 78)):
    c = im.copy(); c.thumbnail((larg, larg * 10), Image.LANCZOS)
    c.save(f"docs/img/capa-{larg}.webp", "WEBP", quality=q, method=6)
```

Por cima dela vão dois gradientes: um de cima para baixo, que fecha o céu — a
área mais clara da foto, e justo onde o título cai — e volta a fechar no
rodapé; e um da esquerda para a direita, que dá chão ao texto sem apagar o
assunto da imagem, que está à direita. Sobre a foto a linha da rota e os
rótulos dos números sobem para o tom da pedra: os tons apagados do painel não
se sustentam ali. Com isso o pior caso de contraste medido é 5,1:1, acima do
mínimo de 4,5:1 — e isso antes de contar a sombra do texto.

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

> **Se os originais não couberem no disco, não os copie.** Uma etapa dá uns
> 5 GB, e `--de` lê de onde eles estiverem — um disco externo, por exemplo.
> Nada é copiado para o projeto; só os derivados otimizados são gravados.
>
> ```bash
> python3 scripts/build_media.py \
>     --de "/Volumes/@enxerga/Dolomitas/Site/D5 Malga Giau-Passo Staulanza" \
>     --de "/Volumes/@enxerga/Dolomitas/Site/D6 Passo Staulanza-Borca di Cadore"
> ```
>
> A tabela de datas continua sendo lida de `midias/_datas.json`, que é do
> projeto e não da pasta de origem.

Cada arquivo é posicionado **pelo horário em que foi capturado**, cruzado
com a série temporal do dia. Isso é mais confiável do que o GPS da foto,
que erra feio entre paredes de rocha.

> **Ao exportar do app Fotos, use "Exportar Original Não Modificado".**
> A exportação comum apaga o EXIF de GPS e pode reescrever a data — sem
> isso o script não consegue ancorar a mídia, e ela fica de fora.

O script avisa, ao final, quais arquivos não puderam ser posicionados e por quê.
Ele pode ser rodado quantas vezes quiser: o que já foi convertido é reaproveitado.

> **Pode esvaziar `midias/` entre as etapas.** O `media.json` é reescrito a cada
> rodada, mas o que já foi publicado continua nele: toda entrada antiga cuja
> miniatura ainda exista em `docs/media/` é mantida. É isso que permite tirar os
> originais da etapa 1 do disco sem que ela suma do mapa. Para remover uma mídia
> de verdade, apague também o arquivo dela em `docs/media/`.
>
> **O que foi mantido é recolocado no trajeto a cada rodada.** O arquivo
> original já se foi, mas o dia e o relógio ficaram gravados na própria
> entrada, e isso basta para refazer a conta — é o que mantém as fotos no lugar
> certo quando uma etapa muda de traçado, como a 3 mudou ao ganhar o trecho até
> o Valparola. Dentro do trajeto o instante exato está no próprio `t`; fora
> dele, só na hora da legenda, com precisão de minuto.

Opções úteis:

| Opção | Para quê |
|-------|----------|
| `--de PASTA` | Lê os originais onde eles estiverem, em vez de `midias/` (pode repetir) |
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

## Atividades fora da travessia

Nem tudo o que foi feito nos Dolomitas pertence à Alta Via. O passeio de
bicicleta até San Vito e a caminhada pelo pé das Três Cimas estão no site para
que as mídias deles tenham onde morar — mas **não entram na quilometragem, na
subida nem na contagem de etapas**, e não têm dado de saúde nenhum: não houve
atividade gravada no relógio.

Cada uma é um arquivo em `extras/`, com o nome começando pela data:

```json
{
  "data": "2026-09-27",
  "modo": "a_pe",
  "de": "Rifugio Auronzo",
  "para": "Forcella Col di Mezzo",
  "saida":   "2026-09-27T09:34:00+02:00",
  "chegada": "2026-09-27T13:05:00+02:00",
  "idaevolta": true,
  "pontos": [[46.612205, 12.296095, 2324.0], ["..."]]
}
```

`modo` é `a_pe` ou `bicicleta`, e muda o verbo das legendas e o aviso do
painel. `idaevolta` repete os pontos em ordem inversa: o destino declarado
passa a ser o ponto da meia-volta — é ele que leva o nome no mapa — e a
chegada volta a ser a partida.

A geometria e as altitudes saem de onde saíram as dos trechos sem registro
(OpenStreetMap e o DEM do Mapterhorn), e os horários, das próprias mídias.

No site essas etapas entram no fim do trilho, atrás de um risco que separa a
travessia do resto, com a faixa recuada. O cartão de fim de etapa esconde
frequência e energia em vez de mostrar zero, e o "acumulado" vira um traço:
não há acumulado de que falar.

## Trechos sem registro do relógio

Às vezes a etapa continua depois que a atividade foi encerrada. Foi o que
aconteceu no dia 21: o relógio parou no alto do Lagazuoi, e dali ainda houve
o teleférico até o Passo Falzarego e 2,4 km de trilha até o Rifugio Valparola.
Não há GPS nenhum desses dois trechos.

Para emendá-los na etapa, ponha um arquivo em `trechos/` com o nome começando
pela data:

```json
{
  "data": "2026-09-21",
  "trechos": [
    {
      "modo": "teleferico",
      "nome": "Funivia Lagazuoi",
      "saida":   "2026-09-21T16:18:00+02:00",
      "chegada": "2026-09-21T16:24:00+02:00",
      "pontos": [
        [46.527592, 12.010160, 2729.7],
        [46.527506, 12.008922, 2728.6]
      ]
    }
  ]
}
```

Cada ponto é `[latitude, longitude, altitude]`, e o primeiro do primeiro
trecho é o último ponto do GPX, para a linha não ter emenda visível. Vale
densificar até uns 15 m entre pontos: com vértices muito afastados a linha
atravessa o relevo em vez de se deitar sobre ele. O tempo é repartido pelo
comprimento, entre a saída e a chegada declaradas; o que passar entre um
trecho e o seguinte entra como parada, e não infla o tempo em movimento.

O nome da chegada continua saindo da tabela `ETAPAS`, em `build_trail.py` —
foi lá que a etapa 3 passou a terminar no Rifugio Valparola.

**`modo` decide o que conta.** `a_pe` entra na distância e no desnível do dia;
`teleferico` não entra em nenhum dos dois — ele desloca, não caminha. Por isso
a etapa 3 fecha em 15,6 km e +1.212 m, sem os 625 m que a cabine desceu.

De onde tirar cada coisa:

- **a geometria**, das trilhas do OpenStreetMap — vale traçar pelo caminho que
  se andou de verdade, e não pelo mais curto;
- **as altitudes**, do mesmo modelo de relevo que o mapa usa
  (`https://tiles.mapterhorn.com/{z}/{x}/{y}.webp`, codificação *terrarium*:
  `altitude = R·256 + G + B/256 − 32768`). Convém passar uma média móvel
  curta antes de gravar: o degrau do modelo, sozinho, vira subida falsa. Num
  teleférico a altitude é a reta entre as duas estações, não o terreno
  embaixo;
- **os horários**, das próprias mídias. No dia 21 o vídeo de dentro da cabine
  é de 16h22, um da trilha é de 16h55, outro de 17h21 e a primeira foto dentro
  do refúgio é de 17h46 — isso prende as duas pontas com folga de minutos.

No site essa parte da linha sai no mesmo matiz do dia, mas puxada para o tom
do contorno: quanto menos foi caminhada, mais apagada. O perfil de elevação a
desenha tracejada, o painel avisa enquanto se passa por ali e o cartão de fim
de etapa diz quantos quilômetros foram traçados à mão.

## Reprocessar o trajeto

```bash
python3 scripts/build_trail.py
```

Só é necessário se os GPX ou os arquivos de `trechos/` mudarem. Para ler os
dados de saúde do zero é preciso `relogio/export.xml`, que **não está no
repositório** (tem 329 MB, acima do limite do GitHub) — reexporte do app Saúde
se precisar. Enquanto `docs/data/.health_cache.json` existir, ele não é
necessário: a varredura já foi feita e o resultado não muda.

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
trechos/*.json             ──▶         ″
extras/*.json              ──▶         ″
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
`line-gradient`, que corta a linha via `line-progress`. É a mesma expressão
que apaga os trechos sem registro do relógio: em vez de uma cor só, ela ganha
um degrau em cada troca de modo. Nenhuma camada a mais.

A régua desse avanço é o comprimento do traçado, medido no carregamento, e não
a distância percorrida — onde houve deslocamento sem caminhada, a distância
fica parada e o desenho ficaria para trás do trilheiro. É também o eixo do
perfil de elevação, para o teleférico aparecer como uma rampa e não como uma
queda vertical.

**Modo teatro.** Por padrão a foto abre num painel de canto e o mapa continua
sendo o assunto. O botão de cantos no alto da mídia — ou a tecla `T` — inverte
isso: a mídia passa a ocupar o palco, uma tira com as miniaturas da etapa
aparece embaixo dela e o mapa vira uma faixa no rodapé, com um divisor que se
arrasta. É o arranjo do Street View, e serve para quando se está olhando as
fotos, não percorrendo o trajeto.

O palco troca de uma moldura com coisas soltas por cima para uma grade de
quatro linhas, e cada elemento é preso à sua linha pelo nome — a ordem no HTML
é outra, porque fora do teatro a mídia flutua. Fechar a mídia sai do teatro:
sem foto ele não teria assunto.

O interruptor **Mídias** vale no teatro como em qualquer lugar: a travessia
para em cada foto e vídeo do trecho. A diferença é que lá não há o "X" para
liberar o caminho — a próxima mídia simplesmente toma o lugar da anterior, e
quem retoma a caminhada é o play.

A roda da bússola e o "seguir o trilheiro" continuam no ar, agora pendurados
na borda de cima da faixa do mapa em vez da do palco: são absolutos, e sem
reancorar iriam parar sobre a foto. A roda encolhe para 60 px, o menor disco
em que a agulha e o N ainda não se encostam.

Dados de relevo: [Mapterhorn][mt] (sem necessidade de chave de API).

[ml]: https://maplibre.org/maplibre-gl-js/docs/
[mt]: https://mapterhorn.com/

### Arquivos

```
relogio/          GPX e export do Apple Health (fonte)
trechos/          pedaços andados fora do registro do relógio, traçados à mão
extras/           atividades que não são da travessia, traçadas à mão
midias/           suas fotos e vídeos originais (não versionado)
videos_para_subir/  vídeos convertidos, prontos para o bucket (não versionado)
pareamento/       página de pareamento manual, gerada sob demanda (não versionado)
scripts/          processamento em Python, sem dependências externas
docs/             o site publicado — é esta pasta que o GitHub Pages serve
  ├── data/       JSON gerado
  └── media/      fotos otimizadas
```
