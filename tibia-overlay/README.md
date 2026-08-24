# Tibia Overlay

Espelho de regiões da tela no estilo [TibiaVision](https://tibiavision.com):
você seleciona pedaços da janela do cliente Tibia (cooldowns, hotkeys, vida do
party…) e eles são replicados em janelinhas flutuantes always-on-top em
qualquer lugar do monitor. Funciona em **macOS**, Windows e Linux (X11).

## Por que é seguro (compliance)

A ferramenta é **100% passiva e externa** — a mesma categoria do OBS ou do
overlay do Discord:

- **Só lê pixels da tela** (captura de tela via API do sistema operacional).
- **Só desenha janelas próprias** por cima.
- **Não** lê nem escreve memória do processo do Tibia.
- **Não** injeta DLL/código no cliente.
- **Não** envia nenhum input (clique, tecla) ao jogo — nem tem código para isso.

O BattlEye e as regras da CipSoft miram ferramentas que interagem com o
cliente (leitura de memória, injeção, automação). Um espelho de tela não toca
no processo do Tibia em nada.

## Instalação (macOS)

```bash
cd tibia-overlay
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python overlay.py
```

Na **primeira execução** o macOS vai pedir permissão de **Gravação de Tela**
para o Terminal (ou iTerm): Ajustes do Sistema → Privacidade e Segurança →
Gravação de Tela e Áudio do Sistema → habilite o Terminal e rode de novo.
Sem essa permissão a captura vem preta.

No Windows/Linux é o mesmo comando (`python` em vez de `python3` no Windows),
sem etapa de permissão.

## Uso

1. **Nova região** → a tela escurece → arraste um retângulo sobre a parte do
   cliente que você quer espelhar (Esc cancela).
2. A janela-espelho aparece ao lado. **Arraste com o botão esquerdo** para
   posicionar onde quiser.
3. **Botão direito** na janela-espelho: travar (o clique passa a atravessar a
   janela — essencial para não roubar cliques durante a hunt), mudar o
   tamanho (50–200%) ou remover. Destravar é pelo painel de controle.
4. **Salvar/Carregar layout** grava as regiões num JSON — dá para ter um
   layout por hunt (ex.: `layout-werelions.json`).
5. O spinner de **FPS** controla a taxa de atualização (20 é suficiente para
   cooldowns; suba para 30–60 se quiser mais fluidez, custa mais CPU).

### Editar o recorte depois de criado

- **Botão direito → "Reajustar recorte…"** reabre o seletor e troca a região
  de origem daquela janela-espelho (posição e tamanho do espelho ficam).
- **Ajuste fino pelo teclado** (clique na janela-espelho antes, destravada):
  **setas** movem o recorte 1px na tela (Shift = 10px); **Option+setas**
  mudam a largura/altura do recorte (Shift = 10px). Ideal para alinhar
  slots de equipamento e contadores de item pixel a pixel.

### Ícone na barra de menus e Spaces

- O app põe um **ícone na barra de menus** (duas telinhas) com menu rápido:
  mostrar painel, ocultar/mostrar todos os espelhos, travar/destravar todas
  e Sair.
- **Fechar o painel não encerra o app** — só o esconde; os espelhos
  continuam. Para encerrar de verdade, use "Sair" no ícone da barra.
- Espelhos **e** painel aparecem em **todos os desktops/Spaces** (inclusive
  sobre apps em fullscreen nativo) — mude de janela à vontade que o overlay
  acompanha.

### Sobre a permissão de "áudio"

O aviso do macOS fala em "gravar a tela **e o áudio**" porque o sistema
juntou as duas coisas numa categoria única de permissão — o texto é do
próprio macOS. O app não tem nenhum código de áudio e **nunca pede
microfone** (confira: ele não aparece em Privacidade → Microfone).

Para testar **sem o Tibia aberto**: espelhe qualquer coisa que se mova
(o relógio do sistema, um vídeo) e confira que a janelinha replica em tempo
real.

## Virar um app do macOS (sem Terminal)

```bash
cd tibia-overlay
bash make_app.sh
```

Isso gera `dist/Tibia Overlay.app` — arraste para `/Applications` e abra
pelo Launchpad como qualquer app. O macOS vai pedir a permissão de Gravação
de Tela **para o app** (separada da do Terminal) na primeira captura.
Layouts salvos pelo app vão por padrão para `~/Documents`.

Depois de mudar o `overlay.py`, rode o `make_app.sh` de novo para
regenerar o app (ele não se atualiza sozinho).

## Limitações conhecidas

- **Rode o Tibia em modo janela**, não fullscreen nativo — no macOS o
  fullscreen vira um Space separado e as janelas-espelho não aparecem por
  cima dele.
- Não posicione o espelho **em cima da própria região de origem** — cria um
  efeito de túnel infinito (o espelho captura a si mesmo).
- A captura é por **coordenadas de tela**, não pela janela do cliente: se
  você mover/redimensionar a janela do Tibia, re-selecione as regiões (ou
  mantenha o cliente sempre na mesma posição, que é o uso típico).
- Sem timers de áudio ainda (o "TibiaAudio" do TibiaVision) — dá para
  adicionar depois com detecção de pixel na região capturada.
