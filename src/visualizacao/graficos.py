"""Gráficos de linha em SVG inline, sem dependências, com cores por variáveis CSS (tema claro e
escuro definidos em relatorio.css) e dados de hover embutidos para o script do relatório.

As faixas dos mandatos usam o mesmo cinza neutro para todos os governos, alternando apenas a
intensidade para separar períodos vizinhos.
"""
from __future__ import annotations

import html
import json
import math

import pandas as pd

from src.periodos import Periodo

LARGURA, ALTURA = 760, 300
MARGEM = {"esq": 56, "dir": 16, "topo": 30, "base": 28}
MARGEM_DIR_ROTULOS = 132


def numero(v: float, casas: int = 1, sinal: bool = False) -> str:
    """Formato brasileiro: 1.234,5 (sinal + opcional)."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    s = f"{v:+,.{casas}f}" if sinal else f"{v:,.{casas}f}"
    return s.replace(",", " ").replace(".", ",").replace(" ", ".").replace("-", "−")


def _ticks(vmin: float, vmax: float, alvo: int = 5) -> list[float]:
    if vmin == vmax:
        vmin, vmax = vmin - 1, vmax + 1
    bruto = (vmax - vmin) / alvo
    mag = 10 ** math.floor(math.log10(bruto))
    passo = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= bruto)
    ini = math.floor(vmin / passo) * passo
    fim = math.ceil(vmax / passo) * passo
    n = round((fim - ini) / passo)
    return [ini + i * passo for i in range(n + 1)]


def _casas_tick(ticks: list[float]) -> int:
    passo = ticks[1] - ticks[0] if len(ticks) > 1 else 1
    return 0 if passo >= 1 else (1 if passo >= 0.1 else 2)


def grafico_linhas(gid: str, series: list[dict], mandatos: list[Periodo], subcortes: list[pd.Timestamp],
                   x_ini: pd.Timestamp, x_fim: pd.Timestamp, unidade: str, casas: int = 1,
                   titulo: str = "", quebras: list[pd.Timestamp] | None = None, rotulo_data=None) -> str:
    """series: [{"nome", "df" (data, valor), "slot" (1-8), "marcadores" (bool)}]."""
    quebras = quebras or []
    multi = len(series) > 1
    dir_ = MARGEM_DIR_ROTULOS if multi else MARGEM["dir"]
    x0, x1 = MARGEM["esq"], LARGURA - dir_
    y0, y1 = MARGEM["topo"], ALTURA - MARGEM["base"]

    dfs = [s["df"][(s["df"]["data"] >= x_ini) & (s["df"]["data"] <= x_fim)].dropna() for s in series]
    todos = pd.concat([d["valor"] for d in dfs if not d.empty])
    vmin, vmax = float(todos.min()), float(todos.max())
    if vmin > 0 and vmin < 0.35 * vmax:
        vmin = 0.0  # inclui o zero quando ele está perto da faixa dos dados
    ticks = _ticks(vmin, vmax)
    t0, t1 = ticks[0], ticks[-1]

    span = (x_fim - x_ini).total_seconds()

    def px(ts):
        return x0 + (pd.Timestamp(ts) - x_ini).total_seconds() / span * (x1 - x0)

    def py(v):
        return y1 - (v - t0) / (t1 - t0) * (y1 - y0)

    partes = [f'<svg viewBox="0 0 {LARGURA} {ALTURA}" role="img" aria-labelledby="{gid}-t" '
              f'class="grafico-svg"><title id="{gid}-t">{html.escape(titulo)}</title>']
    # faixas dos mandatos (neutras)
    for i, m in enumerate(mandatos):
        a = max(px(m.inicio), x0)
        b = min(px(m.fim if m.fim is not None else x_fim), x1)
        if b <= a:
            continue
        classe = "faixa-a" if i % 2 == 0 else "faixa-b"
        partes.append(f'<rect class="{classe}" x="{a:.1f}" y="{y0}" width="{b - a:.1f}" height="{y1 - y0}"/>')
        partes.append(f'<text class="rot-mandato" x="{(a + b) / 2:.1f}" y="{y0 - 10}" '
                      f'text-anchor="middle">{html.escape(m.nome)}</text>')
    for c in subcortes:
        x = px(c)
        partes.append(f'<line class="subcorte" x1="{x:.1f}" x2="{x:.1f}" y1="{y0}" y2="{y1}"/>')
    # grade e eixo y
    ct = _casas_tick(ticks)
    for t in ticks:
        y = py(t)
        classe = "zero" if abs(t) < 1e-12 and t0 < 0 else "grade"
        partes.append(f'<line class="{classe}" x1="{x0}" x2="{x1}" y1="{y:.1f}" y2="{y:.1f}"/>')
        partes.append(f'<text class="tick" x="{x0 - 8}" y="{y + 4:.1f}" text-anchor="end">{numero(t, ct)}</text>')
    # eixo x: inícios de mandato
    for m in mandatos:
        x = px(m.inicio)
        if x0 <= x <= x1:
            partes.append(f'<text class="tick" x="{x:.1f}" y="{y1 + 18}" text-anchor="middle">{m.inicio.year}</text>')
    for q in quebras:
        x = px(q)
        partes.append(f'<line class="quebra" x1="{x:.1f}" x2="{x:.1f}" y1="{y0}" y2="{y1}"/>')
        partes.append(f'<text class="rot-quebra" x="{x + 4:.1f}" y="{y1 - 6}">quebra metodológica</text>')

    dados_hover = []
    finais = []
    for s, d in zip(series, dfs):
        if d.empty:
            continue
        pts = [(px(t), py(v)) for t, v in zip(d["data"], d["valor"])]
        # lacuna maior que 1,6x o intervalo típico da série interrompe a linha (dado ausente não é ligado)
        passos = d["data"].diff()
        lacuna = (passos > passos.median() * 1.6).to_numpy()
        caminho = " ".join(f"{'M' if i == 0 or lacuna[i] else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
        partes.append(f'<path class="linha s{s["slot"]}" d="{caminho}"/>')
        if s.get("marcadores"):
            partes += [f'<circle class="ponto s{s["slot"]}" cx="{x:.1f}" cy="{y:.1f}" r="4"/>' for x, y in pts]
        finais.append([pts[-1][1], s])
        dados_hover.append({
            "nome": s["nome"], "slot": s["slot"],
            "p": [[round(x, 1), round(y, 1), rotulo_data(t) if rotulo_data else str(t.date()), numero(v, casas)]
                  for (x, y), t, v in zip(pts, d["data"], d["valor"])],
        })
    # rótulos diretos no fim das linhas (com afastamento mínimo)
    if multi:
        finais.sort(key=lambda f: f[0])
        for i in range(1, len(finais)):
            finais[i][0] = max(finais[i][0], finais[i - 1][0] + 13)
        for y, s in finais:
            partes.append(f'<text class="rot-serie" x="{x1 + 8}" y="{y + 4:.1f}">{html.escape(s["nome"])}</text>')
    partes.append(f'<line class="cruz" x1="0" x2="0" y1="{y0}" y2="{y1}" visibility="hidden"/>')
    partes.append(f'<rect class="alvo" x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}"/>')
    partes.append("</svg>")
    # "<\/" evita que um "</script>" dentro dos dados feche o bloco
    dados = json.dumps({"unidade": unidade, "series": dados_hover}, ensure_ascii=False).replace("</", "<\\/")
    legenda = ""
    if multi:
        itens = "".join(f'<span class="item"><i class="chip s{s["slot"]}"></i>{html.escape(s["nome"])}</span>'
                        for s in series)
        legenda = f'<div class="legenda">{itens}</div>'
    return (f'{legenda}<div class="grafico" id="{gid}">{"".join(partes)}'
            f'<div class="tooltip" hidden></div>'
            f'<script type="application/json" class="dados">{dados}</script></div>')
