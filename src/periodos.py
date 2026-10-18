"""Períodos de análise (mandatos e subperíodos) e regras de calendário das séries.

Regra de atribuição: uma observação pertence ao período em que o seu período de referência
termina. Assim 2016T3 (jul-set) cai em Temer e o trimestre móvel jun-jul-ago/2016 em Dilma 2.
Séries anuais só são atribuídas a períodos que cobrem anos civis inteiros.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.config import carregar_periodos

# alias do pandas para gerar os fins de período esperados em cada frequência
_FIM_ESPERADO = {"mensal": "ME", "trimestral_movel": "ME", "trimestral": "QE", "anual": "YE"}


@dataclass(frozen=True)
class Periodo:
    id: str
    nome: str
    inicio: pd.Timestamp
    fim: pd.Timestamp | None          # None = mandato em curso
    pai: str | None = None            # id do mandato, quando é subperíodo
    nota: str = ""

    @property
    def em_curso(self) -> bool:
        return self.fim is None

    @property
    def anos_inteiros(self) -> bool:
        """True se começa em 1º/jan e termina em 31/dez (ou está em curso a partir de 1º/jan)."""
        comeca = self.inicio.month == 1 and self.inicio.day == 1
        termina = self.fim is None or (self.fim.month == 12 and self.fim.day == 31)
        return comeca and termina


def listar_periodos(cfg: dict | None = None) -> list[Periodo]:
    """Mandatos na ordem de periodos.yaml, cada um seguido dos seus subperíodos."""
    cfg = cfg or carregar_periodos()
    saida = []
    for m in cfg["mandatos"]:
        fim = pd.Timestamp(m["fim"]) if m.get("fim") else None
        saida.append(Periodo(m["id"], m["nome"], pd.Timestamp(m["inicio"]), fim,
                             nota=(m.get("nota") or "").strip()))
        for s in m.get("subperiodos", []):
            saida.append(Periodo(s["id"], s["nome"], pd.Timestamp(s["inicio"]),
                                 pd.Timestamp(s["fim"]), pai=m["id"]))
    return saida


def fim_do_periodo(datas: pd.Series, frequencia: str) -> pd.Series:
    """Último dia do período de referência de cada `data` (convenção do projeto)."""
    datas = pd.to_datetime(datas)
    if frequencia in ("mensal", "trimestral_movel"):
        return datas + pd.offsets.MonthEnd(0)
    if frequencia == "trimestral":
        return datas + pd.DateOffset(months=3) - pd.Timedelta(days=1)
    if frequencia == "anual":
        return datas + pd.offsets.YearEnd(0)
    if frequencia == "diaria":
        return datas
    raise ValueError(f"frequência desconhecida: {frequencia}")


def n_esperado(inicio: pd.Timestamp, fim: pd.Timestamp, frequencia: str) -> int:
    """Quantos períodos da frequência terminam dentro de [inicio, fim]."""
    return len(pd.date_range(inicio, fim, freq=_FIM_ESPERADO[frequencia]))
