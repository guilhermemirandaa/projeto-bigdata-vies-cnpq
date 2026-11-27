import glob
import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PASTA_DADOS = os.path.join(os.path.dirname(__file__), "..", "dados_brutos")

# LGPD: naturalidade, nacionalidade, instituição e cidade não são carregadas
COLUNAS = {
    "Ano de Exercício": "ano",
    "Região": "regiao",
    "Unidade Federação": "uf",
    "Grande Area": "grande_area",
    "Area": "area",
    "Linha de Fomento": "linha_fomento",
    "Modalidade": "modalidade",
    "Sexo": "sexo",
    "Cor ou Raça": "cor_raca",
    "Benef. Modal / Ano": "beneficiarios",
    "Valor em Real (R$)": "valor_reais",
}


def texto_para_numero(serie):
    return pd.to_numeric(
        serie.str.replace("R$", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False),
        errors="coerce",
    )


def tratar_arquivo(caminho):
    df = pd.read_csv(caminho, sep="\t", encoding="utf-16", dtype=str)

    df = df.drop_duplicates()
    # o arquivo termina com uma linha de total
    df = df[df["Ano de Exercício"] != "Total"]

    df = df[list(COLUNAS)].rename(columns=COLUNAS)

    df["ano"] = df["ano"].astype(int)
    df["valor_reais"] = texto_para_numero(df["valor_reais"])
    df["beneficiarios"] = texto_para_numero(df["beneficiarios"])

    df = df.dropna(subset=["valor_reais"])
    df["beneficiarios"] = df["beneficiarios"].fillna(0)
    textos = df.columns.drop(["ano", "valor_reais", "beneficiarios"])
    df[textos] = df[textos].fillna("Não informado")
    df["cor_raca"] = df["cor_raca"].replace("Não desejo declarar", "Não declarada")
    return df


def criar_dimensao(fato, colunas, nome_id):
    dim = fato[colunas].drop_duplicates().sort_values(colunas).reset_index(drop=True)
    dim.insert(0, nome_id, dim.index + 1)
    fato = fato.merge(dim, on=colunas).drop(columns=colunas)
    return fato, dim


def main():
    load_dotenv()
    url = os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1)

    arquivos = sorted(glob.glob(os.path.join(PASTA_DADOS, "Tab_extrator_dados_Painel_Fomento*.csv")))
    if not arquivos:
        raise SystemExit(f"Nenhum CSV encontrado em {PASTA_DADOS}")

    lotes = []
    for arquivo in arquivos:
        lote = tratar_arquivo(arquivo)
        print(f"{os.path.basename(arquivo)}: {len(lote):,} linhas tratadas")
        lotes.append(lote)
    fato = pd.concat(lotes, ignore_index=True)

    fato, dim_local = criar_dimensao(fato, ["regiao", "uf"], "id_local")
    fato, dim_area = criar_dimensao(fato, ["grande_area", "area"], "id_area")
    fato, dim_modalidade = criar_dimensao(fato, ["linha_fomento", "modalidade"], "id_modalidade")

    engine = create_engine(url)
    with engine.begin() as con:
        con.execute(text("DROP VIEW IF EXISTS vw_fomento"))
        for nome, tabela in [("dim_local", dim_local), ("dim_area", dim_area),
                             ("dim_modalidade", dim_modalidade), ("fato_fomento", fato)]:
            tabela.to_sql(nome, con, if_exists="replace", index=False, chunksize=10_000)
            print(f"Tabela {nome}: {len(tabela):,} linhas carregadas")

        con.execute(text("""
            CREATE VIEW vw_fomento AS
            SELECT f.ano, l.regiao, l.uf, a.grande_area, a.area, m.linha_fomento, m.modalidade,
                   f.sexo, f.cor_raca, f.beneficiarios, f.valor_reais
            FROM fato_fomento f
            JOIN dim_local l      ON l.id_local = f.id_local
            JOIN dim_area a       ON a.id_area = f.id_area
            JOIN dim_modalidade m ON m.id_modalidade = f.id_modalidade
        """))
    print("ETL concluído.")


if __name__ == "__main__":
    main()
