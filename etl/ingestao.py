"""ETL do Painel de Fomento do CNPq: extrai os CSVs anuais, limpa, anonimiza e carrega no PostgreSQL (modelo estrela)."""
import glob
import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PASTA_DADOS = os.path.join(os.path.dirname(__file__), "..", "dados_brutos")

# Colunas que entram no banco, já com nome padronizado (snake_case).
# LGPD: Naturalidade, Nacionalidade, Instituição, Cidade e Município ficam de fora.
# Combinadas com raça e sexo, elas poderiam identificar um pesquisador.
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
    """'R$ 1.600,00' -> 1600.0 ; '-R$ 472,93' (estorno) -> -472.93 ; '0,5' -> 0.5"""
    return pd.to_numeric(
        serie.str.replace("R$", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False),
        errors="coerce",
    )


def tratar_arquivo(caminho):
    """Lê UM arquivo anual por vez (processamento em lotes), para não carregar ~380 MB de uma vez na memória."""
    df = pd.read_csv(caminho, sep="\t", encoding="utf-16", dtype=str)

    # Duplicatas: comparadas na linha inteira, ANTES de descartar colunas.
    # Depois disso, duas bolsas diferentes poderiam parecer iguais.
    df = df.drop_duplicates()

    # O arquivo exportado termina com uma linha "Total". Se ela ficasse, o total do ano seria contado duas vezes.
    df = df[df["Ano de Exercício"] != "Total"]

    df = df[list(COLUNAS)].rename(columns=COLUNAS)

    # Conversão de tipos
    df["ano"] = df["ano"].astype(int)
    df["valor_reais"] = texto_para_numero(df["valor_reais"])
    df["beneficiarios"] = texto_para_numero(df["beneficiarios"])

    # Nulos: sem valor não há o que analisar; texto vazio vira "Não informado".
    df = df.dropna(subset=["valor_reais"])
    df["beneficiarios"] = df["beneficiarios"].fillna(0)
    textos = df.columns.drop(["ano", "valor_reais", "beneficiarios"])
    df[textos] = df[textos].fillna("Não informado")

    # Padroniza a categoria de quem não declarou raça (ela é mantida porque também é um dado: taxa de não declaração).
    df["cor_raca"] = df["cor_raca"].replace("Não desejo declarar", "Não declarada")
    return df


def criar_dimensao(fato, colunas, nome_id):
    """Separa colunas de texto repetitivas numa tabela de dimensão e deixa só o id na tabela fato."""
    dim = fato[colunas].drop_duplicates().sort_values(colunas).reset_index(drop=True)
    dim.insert(0, nome_id, dim.index + 1)
    fato = fato.merge(dim, on=colunas).drop(columns=colunas)
    return fato, dim


def main():
    load_dotenv()
    url = os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1)  # Aiven usa "postgres://"

    arquivos = sorted(glob.glob(os.path.join(PASTA_DADOS, "Tab_extrator_dados_Painel_Fomento*.csv")))
    if not arquivos:
        raise SystemExit(f"Nenhum CSV encontrado em {PASTA_DADOS}")

    lotes = []
    for arquivo in arquivos:
        lote = tratar_arquivo(arquivo)
        print(f"{os.path.basename(arquivo)}: {len(lote):,} linhas tratadas")
        lotes.append(lote)
    fato = pd.concat(lotes, ignore_index=True)

    # Modelo estrela: 1 tabela fato + 3 dimensões
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

        # A view junta a estrela numa tabela só, que o dashboard lê.
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
