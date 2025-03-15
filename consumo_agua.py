import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime
from PIL import Image
from io import BytesIO

# Configurações iniciais
st.set_page_config(page_title="Pedrito, o Fiscal da Hidratação", page_icon="💧")

# URL da imagem do Pedrito no GitHub
IMG_URL = "https://raw.githubusercontent.com/fredprada/consumo_agua/main/pedrito.jpg"

# Baixa e exibe a imagem do Pedrito
response = requests.get(IMG_URL)
if response.status_code == 200:
    pedrito_img = Image.open(BytesIO(response.content))
    st.image(pedrito_img, width=150)

st.title("💧 Pedrito, o Fiscal da Hidratação")

# Configurações do Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_API_KEY = st.secrets["SUPABASE_API_KEY"]
SUPABASE_TABLE = "consumo_agua"

HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
}

# Conversão de medidas para ml
MEDIDAS = {
    "Gole (30ml)": 30,
    "Copo pequeno (100ml)": 100,
    "Copo grande (200ml)": 200,
    "Garrafa pequena (500ml)": 500,
    "Garrafa grande (1L)": 1000,
    "Mililitros (digite abaixo)": None,
}

# Função para registrar consumo
def registrar_consumo(quantidade_ml):
    data = {
        "data_hora": datetime.now().isoformat(),
        "quantidade_ml": quantidade_ml,
    }
    response = requests.post(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}", json=data, headers=HEADERS)
    return response.status_code == 201

# Função para obter histórico
def obter_historico():
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?select=*", headers=HEADERS)
    if response.status_code == 200:
        return pd.DataFrame(response.json())
    return pd.DataFrame()

# **Interface do App**
st.subheader("📝 Registrar Consumo")

# Inputs para registrar consumo
quantidade = st.number_input("Quantas unidades você tomou?", min_value=1, step=1, value=1)
medida = st.selectbox("Selecione a medida:", list(MEDIDAS.keys()))

# Se o usuário escolheu "Mililitros", permitir entrada manual
if MEDIDAS[medida] is None:
    quantidade_ml = st.number_input("Digite a quantidade em ml:", min_value=1, step=1)
else:
    quantidade_ml = quantidade * MEDIDAS[medida]

if st.button("Registrar"):
    if registrar_consumo(quantidade_ml):
        st.success(f"Registrado: {quantidade_ml}ml!")
    else:
        st.error("Erro ao registrar consumo.")

# **Obter histórico**
st.subheader("📊 Histórico de Consumo")
historico = obter_historico()

if not historico.empty:
    historico['data_hora'] = pd.to_datetime(historico['data_hora'])
    historico = historico.sort_values(by="data_hora", ascending=False)
    
    # Adicionar coluna de data
    historico["data"] = historico["data_hora"].dt.date

    # Dias ofensivos (acima de 3 litros)
    consumo_diario = historico.groupby("data")["quantidade_ml"].sum()
    dias_ofensivos = consumo_diario[consumo_diario > 3000].index
    st.subheader("🔥 Dias de Ofensiva (Acima de 3L)")
    st.write(dias_ofensivos if not dias_ofensivos.empty else "Nenhum dia ofensivo registrado.")

    # Exibir histórico
    st.dataframe(historico)

    # **Gráficos**
    st.subheader("📈 Gráficos de Consumo")

    # Total consumido por dia (gráfico de linha)
    fig_dia = px.line(consumo_diario, x=consumo_diario.index, y="quantidade_ml", title="Total Consumido por Dia")
    st.plotly_chart(fig_dia)

    # Ajustando consumo por hora para garantir todas as horas do dia
    historico["hora"] = historico["data_hora"].dt.hour
    consumo_hora = historico.groupby("hora")["quantidade_ml"].sum()

    # Garante que todas as horas de 0 a 23 apareçam
    horas_completas = pd.Series(0, index=range(24))
    consumo_hora = horas_completas.add(consumo_hora, fill_value=0)

    # Gráfico de consumo por hora (gráfico de linha)
    fig_hora = px.line(consumo_hora, x=consumo_hora.index, y="quantidade_ml", title="Total Consumido por Hora")
    st.plotly_chart(fig_hora)

    # Média de consumo diário
    media_diaria = consumo_diario.mean()
    st.metric("📌 Média de Consumo Diário", f"{media_diaria:.2f} ml")

    # Média de consumo por hora
    media_horaria = consumo_hora.mean()
    
    # Gráfico de barras para média de consumo por hora
    fig_media_hora = px.bar(consumo_hora, x=consumo_hora.index, y="quantidade_ml", title="Média de Consumo por Hora")
    st.plotly_chart(fig_media_hora)

else:
    st.write("Nenhum registro encontrado.")
