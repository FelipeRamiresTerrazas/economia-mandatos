# Economia por mandato: indicadores do Brasil, 2003 até hoje

Projeto reprodutível que coleta indicadores econômicos oficiais (IBGE, Banco Central, IPEADATA,
ANP e Banco Mundial) e os organiza por mandato presidencial, com as mesmas fórmulas para todos os
governos. O objetivo é informar o debate, não defender governo nenhum; as regras estão em
[CLAUDE.md](CLAUDE.md).

**Relatório:** https://feliperamiresterrazas.github.io/economia-mandatos/

O relatório é `reports/relatorio.html`, gerado por `python -m src.main` e republicado no site a
cada atualização no `master`.

## Instalação

Requer Python 3.11 ou superior.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -e ".[dev]"
```

## Como rodar

```bash
python -m src.main            # coleta -> tratamento -> analise -> relatorio
python -m src.main coleta     # só a coleta
python -m src.main analise relatorio   # recalcula e regera o relatório sem coletar
pytest                        # testes
```

O comando termina com código de saída 1 se alguma série falhar. A falha fica registrada em
`data/processed/coleta_resumo.csv` e a série aparece como "indisponível", sem valor aproximado
no lugar.

## Como atualizar os dados

A coleta usa cache: se `data/raw/<fonte>/<id>.json` já existe, ele é reaproveitado e nada é
baixado. Para buscar dados novos:

```bash
python -m src.main coleta --forcar                              # baixa tudo de novo
python -m src.main coleta --forcar --series ipca_indice selic_meta   # só algumas séries
```

Depois de atualizar, confira em `git diff data/` o que mudou. As fontes revisam dados passados,
principalmente PIB trimestral e Banco Mundial, então valores antigos também podem mudar.

Para incluir uma série nova, adicione uma entrada em `config/series.yaml` com o código confirmado
na API da fonte. Nenhum código de série fica fixo no Python.

## Estrutura

```
config/periodos.yaml     mandatos, subperíodos (Dilma 2 / Temer) e ano-base da deflação
config/series.yaml       catálogo: fonte, código, unidade, frequência e ressalvas de cada série
config/indicadores.yaml  séries derivadas, indicadores do relatório (série + métrica) e pares
src/coleta/              um coletor por fonte: ibge, bcb, ipeadata, worldbank, anp
src/tratamento/          séries derivadas (fim de ano, médias mensais, Selic real, deflação pelo IPCA)
src/analise/             métricas por período e regras de cobertura/quebra
src/visualizacao/        relatório HTML com gráficos SVG
data/raw/<fonte>/        respostas brutas das APIs + <id>.meta.json (URLs, data de download, SHA-256)
data/processed/series/   séries normalizadas (data, valor[, pais])
data/processed/derivadas/          séries calculadas pelo tratamento
data/processed/analise/            indicadores_por_periodo.csv e pares_por_mandato.csv
data/processed/coleta_resumo.csv   status, cobertura e data de download de cada série
reports/relatorio.html             relatório final
tests/                   testes offline
```

### Rastreabilidade

Cada `data/raw/<fonte>/<id>.meta.json` registra a fonte, o código, as URLs exatas requisitadas, a
data e hora do download e o hash SHA-256 do arquivo bruto. Se o bruto for editado à mão, a próxima
execução acusa a diferença de hash e para.

### Convenção de datas

`data` é o primeiro dia do período de referência: mês, trimestre (2012T2 = 2012-04-01) ou ano
(2023 = 2023-01-01). No trimestre móvel da PNAD Contínua, `data` é o último mês do trimestre
(jan-fev-mar/2012 = 2012-03-01).

## Fontes

| Fonte | API |
|---|---|
| IBGE / SIDRA | `https://apisidra.ibge.gov.br/values/...` |
| Banco Central / SGS | `https://api.bcb.gov.br/dados/serie/bcdata.sgs.<codigo>/dados` |
| IPEADATA | `http://www.ipeadata.gov.br/api/odata4` |
| Banco Mundial | `https://api.worldbank.org/v2` |
| ANP | série mensal da ANP republicada pelo IPEADATA (o portal da ANP não oferece API estável) |

## Como contribuir

Correções, novas séries e novos indicadores são bem-vindos. Leia [CONTRIBUTING.md](CONTRIBUTING.md)
antes: indicadores novos são discutidos numa issue antes do pull request, sem olhar os resultados
por mandato.

## Licença

Código sob [MIT](LICENSE). Relatório, tabelas calculadas e textos sob
[CC BY 4.0](LICENSE-CONTEUDO.md). Os dados brutos seguem os termos das fontes oficiais.
