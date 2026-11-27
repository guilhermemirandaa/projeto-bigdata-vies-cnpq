"""Dashboard: Auditoria de Viés Étnico-Gênero no Fomento do CNPq."""
import os

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine

st.set_page_config(page_title="Viés Étnico-Gênero no CNPq", layout="wide")

NEGRAS = ["Preta", "Parda"]  # regra do IBGE: população negra = pretos + pardos
DIMENSOES = {"Ano": "ano", "Região": "regiao", "Grande área": "grande_area", "Linha de fomento": "linha_fomento"}
DRILL = {"ano": "regiao", "regiao": "uf", "grande_area": "area", "linha_fomento": "modalidade"}
METRICAS = ["Total investido (R$)", "Beneficiários", "Valor médio por beneficiário (R$)",
            "Mediana do valor por concessão (R$)"]


@st.cache_data(ttl=3600)
def carregar():
    load_dotenv()
    url = os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1)
    df = pd.read_sql("SELECT * FROM vw_fomento", create_engine(url))
    textos = df.columns.drop(["ano", "beneficiarios", "valor_reais"])
    df[textos] = df[textos].astype("category")
    return df


def calcular(df, por, metrica):
    """Regra de negócio de cada métrica, agrupada pelas colunas em `por`."""
    g = df.groupby(por, observed=True)
    if metrica == "Total investido (R$)":
        s = g["valor_reais"].sum()
    elif metrica == "Beneficiários":
        s = g["beneficiarios"].sum()
    elif metrica == "Valor médio por beneficiário (R$)":
        s = g["valor_reais"].sum() / g["beneficiarios"].sum()
    else:
        s = g["valor_reais"].median()
    return s.reset_index(name="valor")


def media_por_benef(df):
    b = df["beneficiarios"].sum()
    return df["valor_reais"].sum() / b if b else float("nan")


def brl(v):
    return f"R$ {v:,.0f}".replace(",", ".")


df = carregar()

# ---------- Filtros cruzados ----------
st.sidebar.header("Filtros")
filtros = {"ano": "Ano", "regiao": "Região", "sexo": "Sexo", "cor_raca": "Cor ou raça", "grande_area": "Grande área"}
for col, rotulo in filtros.items():
    opcoes = sorted(df[col].unique())
    escolha = st.sidebar.multiselect(rotulo, opcoes, placeholder="Todos")
    if escolha:
        df = df[df[col].isin(escolha)]

st.title("Auditoria de Viés Étnico-Gênero no Fomento à Pesquisa (CNPq)")
st.caption("Fonte: Painel de Dados Abertos de Fomento do CNPq, 2020–2026 (2026 parcial). ODS 5 e ODS 18.")

if df.empty:
    st.warning("Nenhum registro para os filtros escolhidos.")
    st.stop()

# ---------- KPIs ----------
mulher_negra = df[(df["sexo"] == "Feminino") & df["cor_raca"].isin(NEGRAS)]
homem_branco = df[(df["sexo"] == "Masculino") & (df["cor_raca"] == "Branca")]
gap = (media_por_benef(mulher_negra) / media_por_benef(homem_branco) - 1) * 100
part_mn = mulher_negra["beneficiarios"].sum() / df["beneficiarios"].sum() * 100

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total investido", brl(df["valor_reais"].sum()))
k2.metric("Beneficiários", f"{df['beneficiarios'].sum():,.0f}".replace(",", "."))
k3.metric("Valor médio por beneficiário", brl(media_por_benef(df)))
k4.metric("Mulheres negras entre beneficiários", f"{part_mn:.1f}%")
k5.metric("Gap: mulher negra vs. homem branco", "—" if pd.isna(gap) else f"{gap:+.1f}%",
          help="Diferença do valor médio por beneficiário de mulheres negras em relação a homens brancos.")

# ---------- Gráfico principal com seletores ----------
c1, c2 = st.columns(2)
metrica = c1.selectbox("Métrica", METRICAS)
dim_rotulo = c2.selectbox("Eixo / dimensão", list(DIMENSOES))
dim = DIMENSOES[dim_rotulo]

dados = calcular(df, [dim, "sexo", "cor_raca"], metrica)
fig = px.bar(dados, x=dim, y="valor", color="cor_raca", facet_col="sexo", barmode="group",
             labels={"valor": metrica, dim: dim_rotulo, "cor_raca": "Cor ou raça", "sexo": "Sexo"})
st.plotly_chart(fig, width="stretch")

# ---------- Matriz interseccional Sexo x Raça ----------
st.subheader(f"Matriz interseccional: {metrica}")
matriz = calcular(df, ["sexo", "cor_raca"], metrica).pivot(index="sexo", columns="cor_raca", values="valor")
st.plotly_chart(px.imshow(matriz, text_auto=",.0f", aspect="auto", color_continuous_scale="Blues",
                          labels={"color": metrica, "x": "Cor ou raça", "y": "Sexo"}),
                width="stretch")

# ---------- Drill-down ----------
filho = DRILL[dim]
st.subheader(f"Detalhar um(a) {dim_rotulo.lower()}")
valor_escolhido = st.selectbox(dim_rotulo, sorted(df[dim].unique()))
detalhe = calcular(df[df[dim] == valor_escolhido], [filho, "cor_raca"], metrica)
st.plotly_chart(px.bar(detalhe, x="valor", y=filho, color="cor_raca", orientation="h",
                       labels={"valor": metrica, filho: "", "cor_raca": "Cor ou raça"}),
                width="stretch")
