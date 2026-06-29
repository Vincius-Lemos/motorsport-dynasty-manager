# Motorsport Dynasty Manager — Handoff técnico (para Codex/IA)

Documento de contexto para um agente de código continuar o desenvolvimento.
Leia também `docs/design.txt` (especificação original do jogo).

---

## 1. Visão geral

Jogo de **carreira de automobilismo** em **Python 3.11** com interface gráfica em
**pygame**. O jogador segue a escada **F4 → Fórmula Regional → F3 → F2 → F1**, em
dois modos de carreira **separados**:

- **Piloto** (`DriverCareer`): o jogador *é* o piloto.
- **Gerente** (`ManagerCareer`): o jogador *gerencia* uma equipe (2 pilotos).

Há transições entre modos (aposentar → virar chefe; chefe → virar piloto, com
travas de idade).

### Rodar
```bash
pip install -r requirements.txt
python play.py          # interface gráfica (principal)
python main.py          # versão terminal legada (referência, NÃO é a principal)
```

---

## 2. Arquitetura

Separação rígida entre **núcleo de regras** (`game/`, sem pygame) e **interface**
(`gui/`, pygame). O núcleo nunca importa `gui`.

```
game/                      # regras puras, testável sem UI
  models.py                # dataclasses: Driver, Team, Season, SeasonRound, RaceResult...
  player_profile.py        # PlayerProfile (estado central) + RESIDENCES + custos
  career.py                # utilitários compartilhados: carregar dados, calendário,
                           #   WEEKEND_FORMAT, POINTS_BY_TYPE, derive_grid, laps_for,
                           #   SALARY_BAND/realistic_salary, NPC seeding
  driver_career.py         # DriverCareer
  manager_career.py        # ManagerCareer
  race_engine.py           # simulate_race() — sim por seed, lap a lap
  qualifying.py            # classificação (Q1/Q2/Q3 na F1, sessão única nas bases)
  super_licence.py         # regras da Super Licença FIA
  academies.py             # academias / FP1
  injuries.py              # lesões
  offers.py                # ofertas de contrato dinâmicas
  transfer_market.py       # mercado de transferências (modo gerente)
  save_load.py             # save/load JSON (com fallbacks p/ saves antigos)

gui/
  app.py                   # App: laço principal, pilha de cenas, escala de resolução
  theme.py                 # cores, fontes, RESOLUTIONS
  widgets.py               # Button, SelectList, TextInput, draw_icon, draw_country_flag
  scenes.py                # TODAS as telas (cenas)

data/                      # conteúdo externo em JSON
  drivers/ teams/ series/ tracks/   # por categoria
  academies.json
docs/
  design.txt               # especificação original
  CODEX_HANDOFF.md         # este arquivo
play.py                    # entrypoint da GUI
```

### Fluxo de dados de uma carreira
1. `new_career(series_id, team_id, ...)` carrega o "mundo" (`_load_world`) a partir
   dos JSONs e cria a `Season` via `build_season`.
2. Cada corrida: `run_qualifying()` → `StrategyScene` → `simulate_next_race()`.
3. `end_of_season()` retorna um dict de relatório; `start_new_season(promote)` avança.

> **Importante:** o mundo é **recarregado do JSON a cada temporada**. Os NPCs não
> persistem individualmente entre temporadas — são *re-seedados* com Super Licença
> coerente por categoria e envelhecidos por offset de ano (`_seed_npc` em
> `career.py`). Isso garante que a F1 nunca fique sem pilotos elegíveis, mas um
> ecossistema com NPCs realmente persistentes ainda não existe (ver Roadmap P2).

---

## 3. Sistemas implementados (com arquivos)

| Sistema | Onde | Notas |
|---|---|---|
| Dois modos + transições | `driver_career.py`, `manager_career.py`, `player_profile.py` | piloto↔gerente |
| Simulador de corrida | `race_engine.py` | pneus, desgaste, pits, safety car, DNFs, `grid_order`, `player_pace`, `scoring` |
| **Classificação** | `qualifying.py`, `QualifyingScene` | F1 = Q1/Q2/Q3; bases = sessão única |
| **Sprint + Feature** | `career.py` (`WEEKEND_FORMAT`, `POINTS_BY_TYPE`, `derive_grid`) | F2/F3 sprint(top10/12 invertido)+feature; Regional/F4 = 2 corridas (2ª top8 invertido); F1 = única |
| **Estratégia de corrida** | `StrategyScene`, `race_engine.player_pace` | nº de paradas por `pit_rules(série, tipo)`; sprint=0 paradas/1 pneu; ritmo atacar/normal/conservar |
| Super Licença | `super_licence.py` | 40 pts + 18 anos + 2 temporadas; teto por categoria; FP1 = 1 pt (máx 10) |
| Ecossistema (parcial) | `career._seed_npc` | NPCs com SL por categoria; F1 sempre com elegíveis |
| Progressão de skill | `models.Driver.age_up`, `gain_race_xp` | XP por corrida/quali/FP1; deltas mostrados na UI |
| Salários | `career.SALARY_BAND/realistic_salary` | faixa realista por categoria |
| Economia do piloto | `driver_career` + `player_profile.RESIDENCES` | custo de vida/viagem/empresário por corrida; imposto por residência (Mônaco 0%) |
| FP1 raro | `academies.roll_fp1_session` | raríssimo nas bases; nulo p/ titular de F1 |
| **Demissão imediata** | `driver_career.fire_player/sign_midseason/switch_series_midseason`, `FiringScene` | efeito imediato; equipe paga multa = salário × corridas restantes |
| Ofertas + multa | `offers.py`, `OfferScene` | colunas A (atual) × B (nova); sem vaga = contrato p/ o ano corrente (entra já); com vaga = próxima temporada |
| Buscar Vaga | `SeekRideScene` | botão verde/amarelo/cinza por chance relativa à categoria |
| Regra campeão F2 | `driver_career.end_of_season`, `Driver.barred_series` | campeão da F2 não corre F2 de novo |
| Corridas realistas | `career.laps_for` | voltas = distância-alvo / comprimento da pista |
| Ultrapassagem por pista | `race_engine` (`overtaking_index`) | Mônaco/Imola: pole vence ~89%; Monza: ~67% |
| Perfil do jogador | `PerfilScene` | habilidades, histórico, categorias, equipes |
| Save/Load | `save_load.py` | JSON; fallbacks p/ saves antigos |
| UI escalável | `app.py` | tela virtual 1280×720 escalada p/ 720p–4K + tela cheia (F11) |

---

## 4. Convenções (IMPORTANTE seguir)

- **Núcleo sem UI:** nada em `game/` importa `gui/` ou `pygame`.
- **Idioma:** comentários e textos de UI em **PT-BR**.
- **Sem emojis em fontes pygame:** as fontes do Windows não têm glifos de emoji →
  use ícones vetoriais (`gui/widgets.draw_icon`) ou texto. Nunca renderize `▶`, `★`,
  `🏁` etc. com `draw_text`.
- **Cores:** use as constantes de `gui/theme.py`. Verde = positivo, vermelho =
  negativo/erro, dourado = dinheiro/destaque. Evite cinza-escuro em fundo escuro
  (contraste ruim — `TEXT_DIM` já foi clareado).
- **Coordenadas das cenas:** sempre relativas à tela virtual `T.WIDTH × T.HEIGHT`
  (1280×720). A `App` escala para a janela real e converte os cliques.
- **Novos campos em dataclasses** (`Driver`, `Team`, `SeasonRound`): adicione default
  E atualize os `setdefault(...)` em `save_load._driver_defaults`,
  `career.load_drivers_for_series` (e equivalentes de team) para não quebrar saves.
- **Pontos de corrida** vêm de `career.points_for_type(race_type)`; volta rápida só
  conta fora da sprint (`fastest_lap_point`).

### Padrão de teste (headless smoke tests)
Não há suíte formal. O padrão usado é um script temporário rodado com driver de
vídeo dummy, validando lógica E renderização de cenas sem abrir janela:

```python
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
from gui.app import App
from gui import scenes as S
# ... instanciar carreira, rodar lógica, e:
app = App(); surf = app.canvas
sc = S.AlgumaScene(app); sc.on_enter(); sc.update(0.1); surf.fill((0,0,0)); sc.draw(surf)
```
Sempre rode um smoke test antes de commitar uma mudança de gameplay/UI.

### Ambiente (Windows)
- Shell é **PowerShell**; `python - << EOF` (heredoc) NÃO funciona — escreva um
  arquivo `.py` temporário e rode, depois remova.
- Git pode avisar LF→CRLF; é inofensivo.

---

## 5. Estado atual

Tudo da tabela da seção 3 está implementado e testado. O jogo é jogável ponta a
ponta nos dois modos, com classificação, sprint/feature, estratégia, mercado,
demissões, economia e progressão.

Repositório: `Vincius-Lemos/motorsport-dynasty-manager` (branch de trabalho:
`docs-readme-cleanup`).

---

## 6. Roadmap (pendente)

**P1 — alta prioridade**
- **FP1 com tela de sessão**: hoje o FP1 dá pontos de SL sem nenhuma tela. Falta
  mostrar tempos da sessão, posição, voltas, comparação com o titular, se bateu/
  quebrou/ficou preso no box, se foi bem/mal.
- **Lesão → reserva**: quando o piloto se machuca (abaixo de ~75% de condição), o
  reserva da equipe deve assumir aquela rodada; hoje o piloto só fica de fora.
- **Painel de notícias**: feed do mundo (FP1, demissões, campeão da F2 sem vaga,
  lesões, aposentadorias). Dá vida ao ecossistema.

**P2 — roadmap**
- **Ecossistema persistente de verdade**: NPCs que sobem/descem/aposentam entre
  temporadas mantendo estado individual (hoje são re-seedados do JSON por ano).
- **Pit stop / estratégia ao vivo** durante a corrida (undercut/overcut, ordens).
- **Categorias paralelas**: reserva de F1 + endurance/Indy/DTM/NASCAR (o
  `data/universe.json` da versão JS, citado no design, tem 25 categorias prontas
  como referência de conteúdo).
- **RPG/background do piloto** na criação (origem social afeta dinheiro, salário,
  oportunidades, academia).
- **Instalador/.exe** (PyInstaller) para distribuir sem Python.

---

## 7. Pontos de atenção / dívidas técnicas

- O mundo recarrega do JSON por temporada (ver seção 2). Antes de implementar o
  ecossistema persistente (P2), será preciso introduzir um `World` que sobreviva
  entre temporadas e seja serializado no save.
- `main.py` (terminal) está defasado em relação à GUI; trate como referência, não
  como caminho ativo.
- Saves antigos podem faltar campos novos; `save_load` tem fallbacks, mas ao
  adicionar campos siga a convenção da seção 4.
