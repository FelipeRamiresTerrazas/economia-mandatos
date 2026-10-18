# Regras do projeto: indicadores econômicos do Brasil por mandato

Projeto reprodutível em Python que compara indicadores econômicos do Brasil por mandato
presidencial. O objetivo é informar o debate com dados oficiais, não defender governo nenhum.

## Princípios (valem para todo o projeto)

- **Neutralidade.** Os mesmos indicadores, as mesmas fórmulas e os mesmos gráficos para todos os
  governos. Nada de escolher métricas depois de ver o resultado.
- **Dados oficiais e rastreáveis.** Todo número do relatório deve vir de um arquivo em `data/`
  gerado pelo código, nunca digitado à mão ou lembrado de memória. Cada série registra fonte,
  código, URL/API e data de download (`data/raw/<fonte>/<id>.meta.json`).
- **Correlação não é causalidade.** O relatório nunca afirma que um governo "causou" um resultado.
  Descreve o que aconteceu, mostra o contexto externo e lista limitações.
- **Valores reais e per capita.** Valores monetários deflacionados pelo IPCA (ano-base explícito em
  `config/periodos.yaml`) e, quando fizer sentido, divididos pela população.
- **Comparação com pares.** Cada indicador comparável é confrontado com América Latina e Caribe,
  renda média-alta e média mundial (Banco Mundial).
- **Transparência sobre incerteza.** Quebras metodológicas, revisões e dados faltantes são
  registrados no relatório.

## Restrições

- Não inventar valores. Dado indisponível aparece como "indisponível", com explicação.
- Sem adjetivos políticos nem conclusões do tipo "o governo X foi melhor/pior".
- Sem previsões; o mandato em curso não é extrapolado nem anualizado.
- Pipeline reprodutível com um único comando: `python -m src.main`.
- Nunca editar à mão arquivos em `data/raw/`.
- Não emendar séries com quebra metodológica (ex.: dívida bruta antes/depois de 2008); usar cada
  uma no seu trecho e registrar a quebra.

## Convenções de código

- Catálogo de séries em `config/series.yaml`; períodos em `config/periodos.yaml`. Nenhum código
  de série ou data de mandato fica fixo no código Python.
- Um módulo de coleta por fonte em `src/coleta/`. Cada coletor separa `baixar` (rede) de
  `parsear` (função pura, testável offline).
- Séries normalizadas em `data/processed/series/<id>.csv` com colunas `data, valor` (+ `pais` no
  Banco Mundial). `data` é o primeiro dia do período (mês, trimestre ou ano); no trimestre móvel
  da PNAD Contínua é o último mês do trimestre.
- Testes com `pytest`, usando casos simples calculados à mão.
