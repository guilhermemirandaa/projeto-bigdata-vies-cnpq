import pandas as pd
import glob
import os

caminho_arquivos = 'dados_brutos/*.csv'
lista_arquivos = glob.glob(caminho_arquivos)

dados_anuais = []
print("A iniciar a extração dos ficheiros do CNPq/CAPES...")

for arquivo in lista_arquivos:

    df_temp = pd.read_csv(arquivo, sep='\t', encoding='utf-16')
    dados_anuais.append(df_temp)
    print(f"Ficheiro {os.path.basename(arquivo)} carregado com sucesso.")

df_completo = pd.concat(dados_anuais, ignore_index=True)

colunas_importantes = [
    'Ano de Exercício', 
    'Unidade Federação', 
    'Grande Area', 
    'Modalidade', 
    'Sexo', 
    'Cor ou Raça', 
    'Valor em Real (R$)'
]
df_filtrado = df_completo[colunas_importantes].copy()

df_filtrado = df_filtrado.dropna(subset=['Sexo', 'Cor ou Raça'])
df_filtrado = df_filtrado[
    (df_filtrado['Cor ou Raça'] != 'Não Informado') & 
    (df_filtrado['Cor ou Raça'] != 'Não desejo declarar')
]

df_filtrado['Valor em Real (R$)'] = (
    df_filtrado['Valor em Real (R$)']
    .astype(str)
    .str.replace('R$ ', '', regex=False)  
    .str.replace('.', '', regex=False)    
    .str.replace(',', '.', regex=False)   
    .astype(float)                        
)

df_agrupado = df_filtrado.groupby(
    ['Ano de Exercício', 'Unidade Federação', 'Grande Area', 'Modalidade', 'Sexo', 'Cor ou Raça']
)['Valor em Real (R$)'].sum().reset_index()


caminho_exportacao = 'dados_brutos/fomento_limpo_para_banco.csv'
df_agrupado.to_csv(caminho_exportacao, index=False)

print(f"\nETL Concluído com sucesso! Os dados foram limpos, agregados e guardados em: {caminho_exportacao}")