# 🏁 Motorsport Dynasty Manager

Um jogo de **carreira de automobilismo** em Python, com interface gráfica em `pygame`.
Comece na Fórmula 4 e construa sua dinastia até a Fórmula 1 — como **piloto** ou como
**chefe de equipe** — num mundo vivo, com classificação, sprint/feature, estratégia de
corrida, mercado de pilotos, notícias e três idiomas.

> Protótipo jogável em desenvolvimento ativo. Projeto caseiro; conteúdo inspirado em
> categorias reais, usado apenas para estudo/diversão.

---

## ✨ Destaques

- **Dois modos de carreira separados**
  - **Piloto** — você *é* o piloto: contratos, Super Licença, academias, lesões,
    economia pessoal e evolução de habilidades.
  - **Gerente** — você *gerencia* a equipe: orçamento, instalações, desenvolvimento
    do carro, mercado de pilotos e patrocinadores.
- **Escada completa** F4 → Fórmula Regional → F3 → F2 → F1, com promoção por mérito.
- **Classificação** antes das corridas (Q1/Q2/Q3 na F1, sessão única nas bases).
- **Sprint + Feature** nos fins de semana de F2/F3 (sprint com grid invertido e
  pontuação própria), 2 corridas na Regional/F4.
- **Estratégia de corrida**: escolha o **nº de paradas** (0/1/2), o **pneu de cada
  stint** e o **ritmo** (atacar / normal / conservar) — cada escolha tem efeito real.
- **Mundo vivo**: pilotos da IA evoluem e persistem entre temporadas; a F1 nunca fica
  sem pilotos elegíveis.
- **Mercado e contratos**: ofertas dinâmicas, busca ativa de vaga (verde/laranja/
  vermelho por chance), **dispensa imediata com multa**, negociação de contrato.
- **Super Licença FIA**: 40 pts + 18 anos + temporadas em monopostos, com teto por
  categoria e FP1 raro.
- **Painel de notícias** com os acontecimentos do mundo.
- **Economia do piloto**: salário, custo de vida, viagens, empresário e impostos —
  com escolha de **onde morar** (Mônaco sem imposto, etc.).
- **3 idiomas**: Português, Inglês e Alemão (seletor no menu).
- **Interface escalável** de 720p a 4K (e tela cheia com `F11`).

---

## 🚀 Como rodar

### Opção A — código-fonte (Python 3.11+)
```bash
pip install -r requirements.txt
python play.py
```

### Opção B — executável (Windows, sem instalar Python)
```
dist/MotorsportDynasty.exe
```

No menu você escolhe o **idioma** e a **resolução** (720p, 1080p, 2K, 4K) e alterna
**tela cheia** com `F11`.

> Há também uma versão de terminal legada em `main.py`, mantida só como referência.
> A experiência principal é a gráfica (`play.py` / `.exe`).

---

## 🎮 Como jogar

1. **Nova carreira** → escolha **Piloto** ou **Gerente**, nome, idade, nacionalidade e
   a categoria inicial.
2. No painel, **Correr Próxima** leva ao fim de semana: **Classificação → Estratégia →
   Corrida → Resultado** (na F2/F3, sprint e depois feature).
3. A barra inferior dá acesso às telas do modo:
   - **Piloto:** Perfil, Classificação, Super Licença, Academia, **Buscar Vaga**,
     Negociar, Moradia, Notícias, Aposentar.
   - **Gerente:** Perfil, Desenvolvimento, Transferências, Equipe, Classificação,
     Notícias, Virar Piloto.
4. **Encerrar Temporada** mostra o balanço, a evolução de habilidades e promoções.
5. Salve a qualquer momento; **Carregar Jogo** no menu inicial.

Dica: nas tabelas de **resultado** e **classificação**, role com a roda do mouse.

---

## 📂 Estrutura do projeto

```
game/                      # regras puras (sem pygame)
  models.py                  # Driver, Team, Season, SeasonRound, RaceResult, NewsItem
  player_profile.py          # PlayerProfile + economia/residência
  career.py                  # utilitários: dados, calendário, sprint/feature, salários
  driver_career.py           # carreira de piloto
  manager_career.py          # carreira de gerente
  race_engine.py             # simulador de corrida (pneus, paradas, ritmo, grid)
  qualifying.py              # classificação (Q1/Q2/Q3 e sessão única)
  super_licence.py           # regras da Super Licença FIA
  academies.py               # academias / FP1
  injuries.py                # lesões
  offers.py                  # ofertas de contrato dinâmicas
  job_search.py              # busca ativa de vagas (Buscar Vaga)
  housing.py                 # residência e custos de vida
  transfer_market.py         # mercado de transferências (gerente)
  i18n.py                    # internacionalização (PT/EN/DE)
  save_load.py               # save/load em JSON
gui/
  app.py                     # laço principal, pilha de cenas, escala de resolução
  theme.py / widgets.py      # tema, fontes, botões, ícones, bandeiras
  scenes.py                  # todas as telas
data/
  drivers/ teams/ series/ tracks/   # conteúdo por categoria (JSON)
  lang/ pt_BR.json en_US.json de_DE.json
  academies.json
docs/
  design.txt                 # especificação original
  CODEX_HANDOFF.md           # handoff técnico para IA/colaboradores
play.py                      # entrypoint da interface gráfica
dist/MotorsportDynasty.exe   # build distribuível (Windows)
```

---

## 🗺️ Roadmap

**Concluído**
- Dois modos de carreira + transições piloto ↔ gerente
- Classificação, sprint + feature, estratégia de corrida (pneus/paradas/ritmo)
- Mundo vivo com NPCs persistentes e Super Licença para a IA
- Mercado, busca de vaga, dispensa imediata, negociação de contrato
- Economia do piloto + residência; notícias; i18n (PT/EN/DE)
- Interface escalável (720p–4K) + executável Windows

**Próximo**
- FP1 com tela de sessão completa
- Lesão → reserva assume a vaga
- Pit stop / estratégia ao vivo durante a corrida
- Categorias paralelas (reserva F1 + endurance/Indy/DTM/NASCAR)
- Background/RPG do piloto na criação

---

## 🛠️ Stack

- **Python 3.11+**, **pygame** (interface), **rich** (terminal legado)
- Conteúdo e traduções em **JSON** (fáceis de editar/expandir)

## 📄 Licença

Projeto pessoal/educacional. Sem fins comerciais.
