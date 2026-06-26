"""
Sistema de moradia — onde o piloto mora afeta finanças, reputação e XP.

Custo descontado por corrida (proporcional ao salário mensal).
Imposto de renda varia por país — Mônaco = 0%, Inglaterra = 40%.
"""

HOUSING_OPTIONS = {
    "origin": {
        "name":           "País de Origem",
        "flag":           "🏠",
        "monthly_cost":   1_200,
        "tax_rate":       0.275,   # Brasil ~27,5% | média países em desenvolvimento
        "rep_bonus":      0,
        "xp_bonus":       0,
        "travel_penalty": 2,
        "description":    "Familiar e confortável. Impostos do seu país de origem.",
        "pros":  ["Sem custo de adaptação", "Família e amigos por perto"],
        "cons":  ["Imposto ~27,5%", "Viagens longas para corridas europeias (-2 XP)"],
    },
    "spain": {
        "name":           "Espanha (Barcelona)",
        "flag":           "🇪🇸",
        "monthly_cost":   2_500,
        "tax_rate":       0.47,    # Espanha: 45% federal + ~2% regional = 47% topo
        "rep_bonus":      3,
        "xp_bonus":       0,
        "travel_penalty": 1,
        "description":    "Hub de pilotos. Clima bom, mas imposto altíssimo.",
        "pros":  ["Clima excelente", "Perto das fábricas europeias", "+3 reputação"],
        "cons":  ["Imposto 47% (maior da lista)", "Custo moderado (€2.500/mês)"],
    },
    "uk": {
        "name":           "Inglaterra (Oxfordshire)",
        "flag":           "🇬🇧",
        "monthly_cost":   4_500,
        "tax_rate":       0.45,    # UK: 45% acima de £125k (Additional Rate)
        "rep_bonus":      6,
        "xp_bonus":       2,
        "travel_penalty": 0,
        "description":    "Coração do automobilismo. 7 equipes F1 baseadas aqui.",
        "pros":  ["+2 XP/corrida (simulador)", "+6 reputação", "7 equipes F1 na vizinhança"],
        "cons":  ["Aluguel alto (€4.500/mês)", "Imposto 45%", "Clima terrível"],
    },
    "italy": {
        "name":           "Itália (Maranello/Milão)",
        "flag":           "🇮🇹",
        "monthly_cost":   2_800,
        "tax_rate":       0.43,    # Itália: 43% federal topo + 1-3% regional ≈ 43%
        "rep_bonus":      8,
        "xp_bonus":       1,
        "travel_penalty": 1,
        "description":    "Terra do automobilismo. Ideal para pilotos Ferrari/Haas.",
        "pros":  ["+8 reputação", "+1 XP/corrida", "Cultura motorsport"],
        "cons":  ["Imposto 43%", "Burocracia italiana", "Viagens leves (-1 XP)"],
    },
    "switzerland": {
        "name":           "Suíça (Cantão de Zug)",
        "flag":           "🇨🇭",
        "monthly_cost":   5_500,
        "tax_rate":       0.22,    # Zug: cantão mais baixo da Suíça ~22% (federal+cantonal+municipal)
        "rep_bonus":      10,
        "xp_bonus":       0,
        "travel_penalty": 0,
        "description":    "Cantão de Zug — menor imposto da Europa central (22%).",
        "pros":  ["Imposto 22% (Zug)", "+10 reputação", "Privacidade e estabilidade"],
        "cons":  ["Custo de vida alto (€5.500/mês)", "Distante das fábricas"],
    },
    "monaco": {
        "name":           "Mônaco",
        "flag":           "🇲🇨",
        "monthly_cost":   15_000,
        "tax_rate":       0.00,    # Mônaco: 0% imposto de renda para residentes
        "rep_bonus":      20,
        "xp_bonus":       0,
        "travel_penalty": 0,
        "description":    "Sem imposto de renda. Status máximo. Absurdamente caro.",
        "pros":  ["0% imposto de renda", "+20 reputação", "Status máximo"],
        "cons":  ["€15.000/mês de aluguel", "Só compensa com salário F1+"],
    },
}


def net_per_race(salary: int, housing_key: str, races_in_season: int) -> int:
    """
    Renda líquida por corrida após imposto e moradia.
    gross_per_race = salary / races
    net = gross*(1-tax) - monthly_cost*12/races
    """
    opt = HOUSING_OPTIONS.get(housing_key, HOUSING_OPTIONS["origin"])
    races = max(1, races_in_season)
    gross_per_race = salary / races
    tax_cut = gross_per_race * opt["tax_rate"]
    housing_per_race = (opt["monthly_cost"] * 12) / races
    return int(gross_per_race - tax_cut - housing_per_race)


def annual_breakdown(salary: int, housing_key: str) -> dict:
    """Retorna detalhamento anual para exibição na UI."""
    opt = HOUSING_OPTIONS.get(housing_key, HOUSING_OPTIONS["origin"])
    annual_housing = opt["monthly_cost"] * 12
    annual_tax     = int(salary * opt["tax_rate"])
    net            = salary - annual_housing - annual_tax
    return {
        "gross":    salary,
        "housing":  annual_housing,
        "tax":      annual_tax,
        "net":      net,
        "tax_rate": opt["tax_rate"],
        "xp_bonus": opt["xp_bonus"],
        "travel_penalty": opt["travel_penalty"],
        "rep_bonus": opt["rep_bonus"],
    }
