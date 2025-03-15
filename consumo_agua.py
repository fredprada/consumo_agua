import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime
from PIL import Image

# Configuração da página e ícone
st.set_page_config(
    page_title="Pedrito, o Fiscal da Hidratação",
    page_icon="🚰",
    layout="wide"
)

# Carregar imagem do Pedrito e exibir no topo
pedrito_img = Image.open("pedrito.jpg")
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
    "Mililitros (digite abaixo)": None,  # O usuário informará o valor manualmente
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

# Input de consumo
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

# Obter histórico
st.subheader("📊 Histórico de Consumo")
historico = obter_historico()

if not historico.empty:
    historico['data_hora'] = pd.to_datetime(historico['data_hora'])
    historico = historico.sort_values(by="data_hora", ascending=False)
    
    # Adicionar coluna de data
    historico["data"] = historico["data_hora"].dt.date

    # Criar index de horas para garantir que todas as horas do dia apareçam no gráfico
    todas_horas = pd.DataFrame({"hora": list(range(24))})

    # **Consumo por dia (gráfico de linha)**
    consumo_diario = historico.groupby("data")["quantidade_ml"].sum().reset_index()
    fig_dia = px.line(consumo_diario, x="data", y="quantidade_ml", title="Total Consumido por Dia")
    st.plotly_chart(fig_dia)

    # **Consumo por hora (gráfico de linha)**
    historico["hora"] = historico["data_hora"].dt.hour
    consumo_hora = historico.groupby("hora")["quantidade_ml"].sum().reset_index()
    consumo_hora = todas_horas.merge(consumo_hora, on="hora", how="left").fillna(0)  # Garantir todas as horas de 0 a 23
    fig_hora = px.line(consumo_hora, x="hora", y="quantidade_ml", title="Total Consumido por Hora")
    st.plotly_chart(fig_hora)

    # **Média de consumo por hora (gráfico de barras)**
    media_horaria = historico.groupby("hora")["quantidade_ml"].mean().reset_index()
    media_horaria = todas_horas.merge(media_horaria, on="hora", how="left").fillna(0)
    fig_media_hora = px.bar(media_horaria, x="hora", y="quantidade_ml", title="Média de Consumo por Hora")
    st.plotly_chart(fig_media_hora)

    # **Dias ofensivos (acima de 3L)**
    dias_ofensivos = consumo_diario[consumo_diario["quantidade_ml"] > 3000]["data"]
    st.subheader("🔥 Dias de Ofensiva (Acima de 3L)")
    st.write(dias_ofensivos.tolist() if not dias_ofensivos.empty else "Nenhum dia ofensivo registrado.")

    # Exibir histórico completo em tabela
    st.dataframe(historico)

else:
    st.write("Nenhum registro encontrado.")
