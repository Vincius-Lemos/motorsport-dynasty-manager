# 🏁 Motorsport Dynasty Manager

Um jogo de **carreira de automobilismo** em Python, com interface gráfica em `pygame`.
Comece no kart/Fórmula 4 e construa sua dinastia até a Fórmula 1 — como **piloto**
ou como **chefe de equipe**.

> Protótipo jogável em desenvolvimento ativo. Projeto caseiro, conteúdo inspirado em
> categorias reais usado apenas para fins de estudo/diversão.

---

## ✨ Destaques

- **Dois modos de carreira separados**
  - **Piloto** — você *é* o piloto: assina contratos, acumula Super Licença, entra em
    academias, sofre lesões, evolui suas habilidades.
  - **Gerente** — você *gerencia* a equipe: orçamento, instalações, desenvolvimento do
    carro, mercado de pilotos, patrocinadores.
- **Escada completa** F4 → Fórmula Regional → F3 → F2 → F1, com promoção por mérito.
- **Transições de carreira** — piloto pode se aposentar e virar chefe; chefe pode
  (raramente) tentar virar piloto, com travas realistas de idade.
- **Super Licença FIA** — 40 pontos + 18 anos + 2 temporadas em monopostos, com teto
  de pontos por categoria (você precisa de fato subir de nível).
- **Ecossistema vivo** — os pilotos da IA têm Super Licença coerente com a categoria,
  então a Fórmula 1 nunca fica sem pilotos elegíveis.
- **Simulador de corrida por seed** — pneus, desgaste, pit stops, safety car, falhas
  mecânicas, furos e batidas.
- **Resultado de corrida completo e rolável** — toda a grade, gap para o vencedor,
  volta mais rápida, estratégia de pneus, e um log do que aconteceu na pista.
- **Interface gráfica escalável** de 720p a 4K (e tela cheia), com tema dark, ícones
  vetoriais e animações.

---

## 🚀 Como rodar

Requer **Python 3.11+**.

```bash
# 1. Instale as dependências
pip install -r requirements.txt

# 2. Rode o jogo (interface gráfica)
python play.py
```

No menu você ajusta a **resolução** (720p, 1080p, 2K, 4K) e alterna **tela cheia** com `F11`.

> Também existe uma versão de terminal legada em `main.py` (`python main.py`), mantida
> apenas como referência. A experiência principal é a gráfica (`play.py`).

---

## 🎮 Como jogar

1. **Nova carreira** → escolha **Piloto** ou **Gerente**.
2. Defina nome, idade e nacionalidade e a **categoria inicial**.
3. Escolha a equipe.
4. No painel:
   - **Correr Próxima** simula a próxima corrida (com tela animada e resultado completo).
   - A barra inferior dá acesso às telas do modo:
     - **Piloto:** Classificação, Super Licença, Academia, Aposentar.
     - **Gerente:** Desenvolvimento (instalações + carro), Transferências, Equipe, Virar Piloto.
5. Ao fim da temporada, **Encerrar Temporada** mostra o balanço, a evolução de
   habilidades e eventuais promoções/propostas.
6. **Salvar** a qualquer momento; **Carregar Jogo** no menu inicial.

Dica: nas tabelas de **resultado** e **classificação**, role com a **roda do mouse**
para ver a grade inteira.

---

## 📂 Estrutura do projeto

```
Race/
├── play.py              # ponto de entrada da interface gráfica (pygame)
├── main.py              # versão de terminal legada (referência)
├── requirements.txt
├── game/                # núcleo de regras (sem dependência de UI)
│   ├── models.py            # Driver, Team, Season, RaceResult, ...
│   ├── player_profile.py    # estado central do jogador + transições de modo
│   ├── career.py            # utilidades compartilhadas, carregamento de dados
│   ├── driver_career.py     # carreira de piloto
│   ├── manager_career.py    # carreira de gerente
│   ├── race_engine.py       # simulador de corrida por seed
│   ├── super_licence.py     # regras da Super Licença FIA
│   ├── academies.py         # academias de pilotos / FP1
│   ├── injuries.py          # sistema de lesões
│   ├── offers.py            # ofertas de contrato dinâmicas
│   ├── transfer_market.py   # mercado de transferências
│   └── save_load.py         # save/load em JSON
├── gui/                 # interface gráfica (pygame)
│   ├── app.py               # laço principal + pilha de cenas + escala de resolução
│   ├── theme.py             # cores, fontes, métricas
│   ├── widgets.py           # botões, listas, barras, ícones vetoriais
│   └── scenes.py            # todas as telas do jogo
├── data/                # conteúdo externo em JSON (pilotos, equipes, pistas, regras)
└── docs/design.txt      # documento técnico de design (referência)
```

---

## 🗺️ Roadmap

**Concluído**
- Dois modos de carreira separados + transições piloto ↔ gerente
- Super Licença rebalanceada (teto por categoria, gate de 2 temporadas, FP1 raro)
- Ecossistema com Super Licença para a IA (F1 sempre com elegíveis)
- Progressão de habilidade com XP por corrida
- Salários realistas por categoria
- Tabelas roláveis com gaps e log de eventos da corrida
- Interface gráfica escalável (720p–4K) com animações

**Próximo (P1)**
- Classificação antes da corrida (Q1/Q2/Q3 na F1, quali curta nas bases)
- Sprint Race + Feature Race nas categorias de base
- Tela de proposta comparando situação atual × nova (com multa de quebra)
- Demissão imediata × não-renovação + efeito cascata no mercado
- FP1 com resultado completo da sessão
- Painel de notícias

**Futuro (P2)**
- Pit stop e estratégia ao vivo
- Background/RPG do piloto (origem social afeta dinheiro, salário, oportunidades)
- Categorias paralelas (reserva F1 + endurance/Indy/DTM/NASCAR)
- Lesão tira o titular e o reserva assume a vaga
- Mercado global mais profundo

---

## 🛠️ Stack

- **Python 3.11+**
- **pygame** — interface gráfica
- **rich** — versão de terminal legada
- Dados de conteúdo em **JSON** (fáceis de editar/expandir)

---

## 📄 Licença

Projeto pessoal/educacional. Sem fins comerciais.
