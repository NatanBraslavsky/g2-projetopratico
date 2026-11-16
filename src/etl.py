from __future__ import annotations

import argparse
import io
import json
import re
import unicodedata
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
RAW_FILE = RAW_DIR / "partidas_20_23.csv"

KAGGLE_URL = (
    "https://www.kaggle.com/api/v1/datasets/download/"
    "lucasbral/brasileirao-cartoes-20-23"
)

MESES = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

NOMES_CURTOS = {
    "América FC (Minas Gerais)": "América-MG",
    "Atlético Goianiense": "Atlético-GO",
    "Avai FC": "Avaí",
    "Botafogo FR": "Botafogo",
    "CR Flamengo": "Flamengo",
    "CR Vasco da Gama": "Vasco",
    "Ceará SC": "Ceará",
    "Chapecoense AF": "Chapecoense",
    "Club Athletico Paranaense": "Athletico-PR",
    "Clube Atlético Mineiro": "Atlético-MG",
    "Coritiba FBC": "Coritiba",
    "Cruzeiro EC": "Cruzeiro",
    "Cuiabá EC": "Cuiabá",
    "EC Bahia": "Bahia",
    "EC Juventude": "Juventude",
    "Fluminense FC": "Fluminense",
    "Fortaleza EC": "Fortaleza",
    "Goiás EC": "Goiás",
    "Grêmio FB Porto Alegrense": "Grêmio",
    "Red Bull Bragantino": "Bragantino",
    "SC Corinthians Paulista": "Corinthians",
    "SC Internacional": "Internacional",
    "SC do Recife": "Sport",
    "SE Palmeiras": "Palmeiras",
    "Santos FC Sao Paulo": "Santos",
    "São Paulo FC": "São Paulo",
}

EVENTOS = {
    "yellow_cards": "amarelo",
    "sec_card": "segundo_amarelo",
    "red_cards": "vermelho",
    "gols": "gol",
}

LADOS = {"home": "mandante", "away": "visitante"}

COLUNAS_RAW = [
    "home_team",
    "away_team",
    "home_team_score",
    "away_team_score",
    "game_date",
    "stadium",
    "public",
    "ref",
    "yellow_cards_home",
    "red_cards_home",
    "gols_home",
    "yellow_cards_away",
    "red_cards_away",
    "gols_away",
    "sec_card_home",
    "sec_card_away",
    "link",
]


@dataclass
class Relatorio:
    etapas: list[dict] = field(default_factory=list)

    def registrar(self, etapa: str, **detalhes) -> None:
        self.etapas.append({"etapa": etapa, **detalhes})

    def salvar(self, caminho: Path) -> None:
        caminho.write_text(
            json.dumps(self.etapas, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )


def baixar_dados_brutos(destino: Path = RAW_FILE, url: str = KAGGLE_URL) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as resposta:
        conteudo = resposta.read()
    with zipfile.ZipFile(io.BytesIO(conteudo)) as arquivo_zip:
        with arquivo_zip.open(destino.name) as csv:
            destino.write_bytes(csv.read())
    return destino


def carregar_bruto(caminho: Path = RAW_FILE) -> pd.DataFrame:
    if not caminho.exists():
        baixar_dados_brutos(caminho)
    df = pd.read_csv(caminho, encoding="utf-8", sep=",", dtype=str, keep_default_na=False)
    faltantes = set(COLUNAS_RAW) - set(df.columns)
    if faltantes:
        raise ValueError(f"Colunas ausentes no arquivo bruto: {sorted(faltantes)}")
    return df


def normalizar_texto(valor: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", valor)).strip()


def converter_data(valor: str) -> pd.Timestamp:
    padrao = re.fullmatch(r"(\d{1,2}) de (\w+) de (\d{4}) (\d{1,2}):(\d{2})", valor.strip())
    if padrao is None:
        return pd.NaT
    dia, mes, ano, hora, minuto = padrao.groups()
    numero_mes = MESES.get(mes.lower())
    if numero_mes is None:
        return pd.NaT
    return pd.Timestamp(int(ano), numero_mes, int(dia), int(hora), int(minuto))


def converter_publico(valor: str) -> float:
    texto = valor.strip()
    if texto in {"", "No data"}:
        return np.nan
    if not re.fullmatch(r"\d{1,3}(\.\d{3})*", texto):
        return np.nan
    return float(texto.replace(".", ""))


def extrair_temporada(link: str) -> int | None:
    padrao = re.search(r"s%C3%A9rie-a-(\d{4})", link)
    return int(padrao.group(1)) if padrao else None


def converter_minuto(valor: str) -> tuple[int, int]:
    padrao = re.fullmatch(r"(\d+)(?:\+(\d+))?'", valor.strip())
    if padrao is None:
        raise ValueError(f"Minuto em formato inesperado: {valor!r}")
    base = int(padrao.group(1))
    acrescimo = int(padrao.group(2) or 0)
    return base, acrescimo


def ler_lista_json(valor: str) -> list[dict]:
    texto = valor.strip()
    if not texto:
        return []
    return json.loads(texto)


def classificar_torcida(temporada: int, publico: float) -> str:
    if not np.isnan(publico):
        return "com_publico"
    if temporada in (2020, 2021):
        return "portoes_fechados"
    return "desconhecido"


def construir_partidas(bruto: pd.DataFrame, relatorio: Relatorio) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = bruto.copy()
    relatorio.registrar("leitura", linhas=len(df), colunas=len(df.columns))

    for coluna in ["home_team", "away_team", "stadium", "ref"]:
        df[coluna] = df[coluna].map(normalizar_texto)

    df["partida_id"] = df["link"].str.extract(r"/match/view/([a-z0-9]+)")[0]
    df["temporada"] = df["link"].map(extrair_temporada).astype("Int16")
    df["data_hora"] = df["game_date"].map(converter_data)
    df["publico"] = df["public"].map(converter_publico)
    df["gols_mandante"] = pd.to_numeric(df["home_team_score"], errors="coerce").astype("Int8")
    df["gols_visitante"] = pd.to_numeric(df["away_team_score"], errors="coerce").astype("Int8")

    relatorio.registrar(
        "conversao_tipos",
        datas_invalidas=int(df["data_hora"].isna().sum()),
        temporadas_invalidas=int(df["temporada"].isna().sum()),
        publico_ausente=int(df["publico"].isna().sum()),
        publico_valor_textual_no_data=int((df["public"] == "No data").sum()),
    )

    duplicadas = df.duplicated(subset="partida_id", keep="first")
    relatorio.registrar("remocao_duplicatas", removidas=int(duplicadas.sum()))
    df = df.loc[~duplicadas].copy()

    invalidas = df[["partida_id", "temporada", "data_hora", "gols_mandante", "gols_visitante"]].isna().any(axis=1)
    relatorio.registrar(
        "descarte_linhas_invalidas",
        removidas=int(invalidas.sum()),
        partida_ids=df.loc[invalidas, "partida_id"].tolist(),
    )
    df = df.loc[~invalidas].copy()

    contagens = {}
    for origem, evento in EVENTOS.items():
        for lado_en, lado_pt in LADOS.items():
            listas = df[f"{origem}_{lado_en}"].map(ler_lista_json)
            contagens[f"{evento}_{lado_pt}"] = listas.map(len).astype("int16")
    df = df.assign(**contagens)

    divergentes = (df["gol_mandante"] != df["gols_mandante"]) | (df["gol_visitante"] != df["gols_visitante"])
    relatorio.registrar("checagem_placar_vs_lista_gols", divergentes=int(divergentes.sum()))

    for lado in LADOS.values():
        df[f"amarelos_{lado}"] = df[f"amarelo_{lado}"] + df[f"segundo_amarelo_{lado}"]
        df[f"expulsoes_{lado}"] = df[f"vermelho_{lado}"] + df[f"segundo_amarelo_{lado}"]
        df[f"cartoes_{lado}"] = df[f"amarelos_{lado}"] + df[f"vermelho_{lado}"]

    df["cartoes_total"] = df["cartoes_mandante"] + df["cartoes_visitante"]
    df["amarelos_total"] = df["amarelos_mandante"] + df["amarelos_visitante"]
    df["expulsoes_total"] = df["expulsoes_mandante"] + df["expulsoes_visitante"]
    df["dif_amarelos_vis_mand"] = df["amarelos_visitante"] - df["amarelos_mandante"]
    df["saldo_gols"] = (df["gols_mandante"] - df["gols_visitante"]).astype("Int8")
    df["resultado"] = np.select(
        [df["saldo_gols"] > 0, df["saldo_gols"] < 0],
        ["vitoria_mandante", "vitoria_visitante"],
        default="empate",
    )
    df["torcida"] = [classificar_torcida(t, p) for t, p in zip(df["temporada"], df["publico"])]

    partidas = pd.DataFrame(
        {
            "partida_id": df["partida_id"],
            "temporada": df["temporada"],
            "data_hora": df["data_hora"],
            "mandante": df["home_team"].map(NOMES_CURTOS).fillna(df["home_team"]),
            "visitante": df["away_team"].map(NOMES_CURTOS).fillna(df["away_team"]),
            "mandante_nome_oficial": df["home_team"],
            "visitante_nome_oficial": df["away_team"],
            "estadio": df["stadium"],
            "arbitro": df["ref"],
            "publico": df["publico"],
            "torcida": df["torcida"],
            "gols_mandante": df["gols_mandante"],
            "gols_visitante": df["gols_visitante"],
            "saldo_gols": df["saldo_gols"],
            "resultado": df["resultado"],
            "amarelos_mandante": df["amarelos_mandante"],
            "amarelos_visitante": df["amarelos_visitante"],
            "vermelhos_diretos_mandante": df["vermelho_mandante"],
            "vermelhos_diretos_visitante": df["vermelho_visitante"],
            "segundos_amarelos_mandante": df["segundo_amarelo_mandante"],
            "segundos_amarelos_visitante": df["segundo_amarelo_visitante"],
            "expulsoes_mandante": df["expulsoes_mandante"],
            "expulsoes_visitante": df["expulsoes_visitante"],
            "cartoes_mandante": df["cartoes_mandante"],
            "cartoes_visitante": df["cartoes_visitante"],
            "cartoes_total": df["cartoes_total"],
            "amarelos_total": df["amarelos_total"],
            "expulsoes_total": df["expulsoes_total"],
            "dif_amarelos_vis_mand": df["dif_amarelos_vis_mand"],
            "link_fonte": df["link"],
        }
    )

    for coluna in ["mandante", "visitante", "estadio", "arbitro", "torcida", "resultado"]:
        partidas[coluna] = partidas[coluna].astype("category")

    partidas = partidas.sort_values(["temporada", "data_hora", "mandante"]).reset_index(drop=True)
    relatorio.registrar(
        "partidas_final",
        linhas=len(partidas),
        por_temporada={int(k): int(v) for k, v in partidas["temporada"].value_counts().sort_index().items()},
        por_torcida=partidas["torcida"].value_counts().to_dict(),
    )
    return partidas, df


def construir_eventos(df: pd.DataFrame, relatorio: Relatorio) -> pd.DataFrame:
    registros = []
    for linha in df.itertuples(index=False):
        for origem, evento in EVENTOS.items():
            for lado_en, lado_pt in LADOS.items():
                for item in ler_lista_json(getattr(linha, f"{origem}_{lado_en}")):
                    base, acrescimo = converter_minuto(item["minute"])
                    registros.append(
                        {
                            "partida_id": linha.partida_id,
                            "temporada": linha.temporada,
                            "tipo": evento,
                            "lado": lado_pt,
                            "time": NOMES_CURTOS.get(linha.home_team if lado_en == "home" else linha.away_team),
                            "jogador": normalizar_texto(item["player"]),
                            "minuto_texto": item["minute"],
                            "minuto_base": base,
                            "acrescimo": acrescimo,
                            "gol_contra": bool(item.get("cont", 0)) if evento == "gol" else pd.NA,
                            "penalti": bool(item.get("penal", 0)) if evento == "gol" else pd.NA,
                        }
                    )

    eventos = pd.DataFrame(registros)
    eventos["tempo"] = np.where(eventos["minuto_base"] <= 45, 1, 2).astype("int8")
    eventos["minuto_ordenacao"] = eventos["minuto_base"] + eventos["acrescimo"] / 100
    eventos["em_acrescimo"] = eventos["acrescimo"] > 0
    eventos = eventos.sort_values(["partida_id", "minuto_ordenacao", "tipo"]).reset_index(drop=True)
    eventos = adicionar_placar_momentaneo(eventos)

    for coluna in ["tipo", "lado", "time"]:
        eventos[coluna] = eventos[coluna].astype("category")
    eventos["gol_contra"] = eventos["gol_contra"].astype("boolean")
    eventos["penalti"] = eventos["penalti"].astype("boolean")

    relatorio.registrar(
        "eventos_final",
        linhas=len(eventos),
        por_tipo=eventos["tipo"].value_counts().to_dict(),
        em_acrescimo=int(eventos["em_acrescimo"].sum()),
    )
    return eventos


def adicionar_placar_momentaneo(eventos: pd.DataFrame) -> pd.DataFrame:
    eventos = eventos.copy()
    gols = eventos["tipo"] == "gol"
    eventos["_gm"] = (gols & (eventos["lado"] == "mandante")).astype(int)
    eventos["_gv"] = (gols & (eventos["lado"] == "visitante")).astype(int)
    chave = ["partida_id", "minuto_ordenacao"]
    por_minuto = eventos.groupby(chave, sort=True)[["_gm", "_gv"]].sum()
    acumulado = por_minuto.groupby(level=0).cumsum() - por_minuto
    acumulado.columns = ["placar_mandante_antes", "placar_visitante_antes"]
    eventos = eventos.merge(acumulado.reset_index(), on=chave, how="left")
    saldo = eventos["placar_mandante_antes"] - eventos["placar_visitante_antes"]
    saldo_do_time = np.where(eventos["lado"] == "mandante", saldo, -saldo)
    eventos["saldo_time_antes"] = saldo_do_time.astype("int8")
    eventos["situacao_placar"] = pd.Categorical(
        np.select([saldo_do_time > 0, saldo_do_time < 0], ["vencendo", "perdendo"], default="empatando"),
        categories=["perdendo", "empatando", "vencendo"],
        ordered=True,
    )
    return eventos.drop(columns=["_gm", "_gv"])


def salvar(df: pd.DataFrame, nome: str) -> list[Path]:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    parquet = PROCESSED_DIR / f"{nome}.parquet"
    csv_gz = PROCESSED_DIR / f"{nome}.csv.gz"
    df.to_parquet(parquet, index=False, engine="pyarrow", compression="snappy")
    df.to_csv(csv_gz, index=False, encoding="utf-8", compression={"method": "gzip", "mtime": 0})
    return [parquet, csv_gz]


def executar_pipeline(baixar: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    if baixar:
        baixar_dados_brutos()
    relatorio = Relatorio()
    bruto = carregar_bruto()
    partidas, intermediario = construir_partidas(bruto, relatorio)
    eventos = construir_eventos(intermediario, relatorio)
    arquivos = salvar(partidas, "partidas") + salvar(eventos, "eventos")
    relatorio.registrar("persistencia", arquivos=[str(a.relative_to(ROOT)) for a in arquivos])
    relatorio.salvar(PROCESSED_DIR / "relatorio_etl.json")
    return partidas, eventos


def carregar_processados() -> tuple[pd.DataFrame, pd.DataFrame]:
    partidas = pd.read_parquet(PROCESSED_DIR / "partidas.parquet")
    eventos = pd.read_parquet(PROCESSED_DIR / "eventos.parquet")
    return partidas, eventos


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline ETL do Brasileirão Série A 2020-2023")
    parser.add_argument("--baixar", action="store_true", help="baixa novamente o arquivo bruto do Kaggle")
    args = parser.parse_args()
    partidas, eventos = executar_pipeline(baixar=args.baixar)
    print(f"partidas: {len(partidas)} linhas | eventos: {len(eventos)} linhas")
    print(f"saída em {PROCESSED_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
