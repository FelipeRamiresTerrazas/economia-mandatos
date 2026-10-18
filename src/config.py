"""Caminhos do projeto e leitura dos arquivos de configuração."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SERIES_DIR = PROCESSED_DIR / "series"
REPORTS_DIR = ROOT / "reports"


def _ler_yaml(nome: str) -> dict:
    with open(CONFIG_DIR / nome, encoding="utf-8") as f:
        return yaml.safe_load(f)


def carregar_catalogo() -> dict:
    """Retorna o conteúdo de config/series.yaml (chaves `padroes` e `series`)."""
    catalogo = _ler_yaml("series.yaml")
    ids = [s["id"] for s in catalogo["series"]]
    duplicados = {i for i in ids if ids.count(i) > 1}
    if duplicados:
        raise ValueError(f"ids duplicados em series.yaml: {sorted(duplicados)}")
    return catalogo


def carregar_periodos() -> dict:
    """Retorna o conteúdo de config/periodos.yaml."""
    return _ler_yaml("periodos.yaml")

