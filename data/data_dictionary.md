# Dicionário de Dados

Metadados das tabelas brutas e tratadas do projeto **Cartão na Mesa** (Brasileirão Série A, 2020–2023).

| Item | Valor |
|---|---|
| Fonte primária | [brasileirao_cartoes_20-23 — Kaggle (Lucas Bral)](https://www.kaggle.com/datasets/lucasbral/brasileirao-cartoes-20-23) |
| Origem dos registros | Súmulas estatísticas Opta / Stats Perform |
| Licença da fonte | CC0 1.0 (domínio público) |
| Licença dos dados derivados | CC-BY 4.0 |
| Cobertura | Série A, temporadas 2020, 2021, 2022 e 2023 (380 partidas cada) |
| Período das partidas | 08/08/2020 a 06/12/2023 |
| Codificação | UTF-8 |
| Gerado por | `python -m src.etl` |

## Arquivos

| Arquivo | Granularidade | Linhas | Formato |
|---|---|---|---|
| `data/raw/partidas_20_23.csv` | 1 linha por partida | 1.520 | CSV, separador `,`, UTF-8, listas JSON em texto |
| `data/processed/partidas.parquet` / `partidas.csv.gz` | 1 linha por partida | 1.520 | Parquet (snappy) / CSV gzip |
| `data/processed/eventos.parquet` / `eventos.csv.gz` | 1 linha por cartão ou gol | 11.558 | Parquet (snappy) / CSV gzip |
| `data/processed/relatorio_etl.json` | 1 objeto por etapa do pipeline | — | JSON |

---

## 1. Arquivo bruto — `data/raw/partidas_20_23.csv`

Todas as colunas são lidas como texto (`str`) pelo pipeline.

| Coluna | Significado | Formato observado |
|---|---|---|
| `home_team` | Nome do clube mandante | Texto, ex.: `CR Flamengo` |
| `away_team` | Nome do clube visitante | Texto |
| `home_team_score` | Gols do mandante | Inteiro |
| `away_team_score` | Gols do visitante | Inteiro |
| `game_date` | Data e hora da partida | Texto por extenso: `25 de fevereiro de 2021 21:30` |
| `stadium` | Estádio | Texto |
| `public` | Público pagante | Texto com ponto como separador de milhar (`12.089`) ou `No data` |
| `ref` | Árbitro principal | Texto |
| `yellow_cards_home` / `yellow_cards_away` | Primeiros amarelos de cada lado | Lista JSON `[{"player": str, "minute": "17'"}]` |
| `sec_card_home` / `sec_card_away` | Segundos amarelos (expulsão) | Lista JSON, mesmo formato |
| `red_cards_home` / `red_cards_away` | Vermelhos diretos | Lista JSON, mesmo formato |
| `gols_home` / `gols_away` | Gols creditados a cada lado | Lista JSON `[{"player", "minute", "cont": 0/1, "penal": 0/1}]` |
| `link` | URL da súmula na fonte | Texto; contém a temporada (`série-a-2020`) e o ID da partida |

Os minutos usam o formato `N'` ou `N+M'` (acréscimo), ex.: `45+2'`, `90+12'`.

---

## 2. Tabela tratada — `partidas`

| Variável | Significado | Tipo | Formato / domínio |
|---|---|---|---|
| `partida_id` | Identificador da partida extraído da URL da fonte | `string` | 25 caracteres alfanuméricos, único |
| `temporada` | Edição do campeonato (não o ano da data) | `Int16` | 2020–2023 |
| `data_hora` | Data e hora local da partida | `datetime64[ns]` | `AAAA-MM-DD HH:MM:SS` |
| `mandante` | Clube mandante, nome curto padronizado | `category` | 26 clubes, ex.: `Flamengo` |
| `visitante` | Clube visitante, nome curto padronizado | `category` | idem |
| `mandante_nome_oficial` | Nome do mandante como na fonte | `string` | ex.: `CR Flamengo` |
| `visitante_nome_oficial` | Nome do visitante como na fonte | `string` | idem |
| `estadio` | Estádio | `category` | 37 valores |
| `arbitro` | Árbitro principal | `category` | 63 valores |
| `publico` | Público pagante | `float64` | 79–69.997; `NaN` quando ausente na fonte |
| `torcida` | Condição de público | `category` | `com_publico` (público registrado); `portoes_fechados` (sem registro em 2020–2021); `desconhecido` (sem registro em 2022–2023) |
| `gols_mandante` | Gols do mandante | `Int8` | ≥ 0 |
| `gols_visitante` | Gols do visitante | `Int8` | ≥ 0 |
| `saldo_gols` | `gols_mandante − gols_visitante` | `Int8` | −7 a 7 |
| `resultado` | Resultado do ponto de vista do mandante | `category` | `vitoria_mandante`, `empate`, `vitoria_visitante` |
| `amarelos_mandante` / `amarelos_visitante` | Total de amarelos (primeiros + segundos) | `int16` | ≥ 0 |
| `vermelhos_diretos_mandante` / `_visitante` | Vermelhos diretos | `int16` | ≥ 0 |
| `segundos_amarelos_mandante` / `_visitante` | Expulsões por segundo amarelo | `int16` | ≥ 0 |
| `expulsoes_mandante` / `expulsoes_visitante` | Vermelhos diretos + segundos amarelos | `int16` | ≥ 0 |
| `cartoes_mandante` / `cartoes_visitante` | Amarelos + vermelhos diretos | `int16` | ≥ 0 |
| `cartoes_total` | Cartões dos dois lados | `int16` | 0–16 |
| `amarelos_total` | Amarelos dos dois lados | `int16` | ≥ 0 |
| `expulsoes_total` | Expulsões dos dois lados | `int16` | ≥ 0 |
| `dif_amarelos_vis_mand` | Amarelos do visitante − amarelos do mandante | `int16` | positivo = visitante mais punido |
| `link_fonte` | URL da súmula original | `string` | URL |

---

## 3. Tabela tratada — `eventos`

Uma linha por cartão ou gol, extraída das listas JSON.

| Variável | Significado | Tipo | Formato / domínio |
|---|---|---|---|
| `partida_id` | Chave para `partidas.partida_id` | `string` | — |
| `temporada` | Edição do campeonato | `int16` | 2020–2023 |
| `tipo` | Tipo de evento | `category` | `amarelo` (primeiro amarelo), `segundo_amarelo`, `vermelho` (direto), `gol` |
| `lado` | Lado ao qual o evento é atribuído | `category` | `mandante`, `visitante`. Para gols, o lado beneficiado (inclui gol contra) |
| `time` | Nome curto do clube do `lado` | `category` | — |
| `jogador` | Jogador que recebeu o cartão ou marcou o gol | `string` | Nome completo, normalizado em NFC |
| `minuto_texto` | Minuto como na fonte | `string` | `N'` ou `N+M'` |
| `minuto_base` | Minuto regulamentar | `int64` | 1–90 |
| `acrescimo` | Minutos de acréscimo | `int64` | 0–18 |
| `gol_contra` | Gol contra (só para `tipo = gol`) | `boolean` | `True`/`False`; nulo para cartões |
| `penalti` | Gol de pênalti (só para `tipo = gol`) | `boolean` | `True`/`False`; nulo para cartões |
| `tempo` | Tempo de jogo | `int8` | 1 (`minuto_base` ≤ 45) ou 2 |
| `minuto_ordenacao` | Chave cronológica: `minuto_base + acrescimo/100` | `float64` | ex.: `90+3'` → 90,03 |
| `em_acrescimo` | Evento ocorreu nos acréscimos | `bool` | — |
| `placar_mandante_antes` | Gols do mandante antes do minuto do evento | `int64` | ≥ 0 |
| `placar_visitante_antes` | Gols do visitante antes do minuto do evento | `int64` | ≥ 0 |
| `saldo_time_antes` | Saldo do time do `lado` antes do evento | `int8` | −7 a 6 |
| `situacao_placar` | Situação do time do `lado` antes do evento | `category` ordenada | `perdendo` < `empatando` < `vencendo` |

---

## 4. Regras de tratamento e rastreabilidade

| Regra | Decisão |
|---|---|
| Valores `No data` em `public` | Convertidos em `NaN`, sem imputação |
| Público fora do padrão `\d{1,3}(\.\d{3})*` | Convertido em `NaN` (nenhum caso encontrado) |
| Data fora do padrão por extenso | `NaT` e linha descartada, com registro no relatório (nenhum caso) |
| Partidas duplicadas por `partida_id` | Descartadas, com registro no relatório (nenhum caso) |
| Coerência placar × lista de gols | Verificada; 0 divergências |
| Outliers de cartões (Tukey 1,5 × IQR) | Mantidos e sinalizados na análise (6 partidas) |
| Gols no mesmo minuto de um cartão | Não entram no `placar_*_antes` daquele cartão |

As contagens de cada etapa ficam em `data/processed/relatorio_etl.json`.
