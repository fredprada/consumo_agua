import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime
from PIL import Image

# Carregar credenciais do Supabase dos secrets
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_API_KEY = st.secrets["SUPABASE_API_KEY"]
SUPABASE_TABLE = "consumo_agua"

HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
}

# Configuração do Streamlit
st.set_page_config(
    page_title="Pedrito, o Fiscal da Hidratação",
    page_icon="pedrito.jpg",  # Atualizado para o nome correto da imagem
    layout="wide"
)

# Carregar imagem do Pedrito no topo
pedrito_img = Image.open("pedrito.jpg")  # Nome correto do arquivo
st.image(pedrito_img, width=150)
st.title("🚰 Pedrito, o Fiscal da Hidratação")

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

# Interface do App
st.subheader("📌 Registre seu Consumo de Água")

# Input de consumo
quantidade = st.number_input("Quantas unidades você tomou?", min_value=1, step=1, value=1)
medida = st.selectbox("Selecione a medida:", list(MEDIDAS.keys()))

# Se o usuário escolheu "Mililitros", permitir entrada manual
if MEDIDAS[medida] is None:
    quantidade_ml = st.number_input("Digite a quantidade em ml:", min_value=1, step=1)
else:
    quantidade_ml = quantidade * MEDIDAS[medida]

if st.button("Registrar 🚀"):
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

    # Dias ofensivos (acima de 3 litros)
    consumo_diario = historico.groupby("data")["quantidade_ml"].sum()
    dias_ofensivos = consumo_diario[consumo_diario > 3000].index
    st.subheader("🔥 Dias de Ofensiva (Acima de 3L)")
    st.write(dias_ofensivos if not dias_ofensivos.empty else "Nenhum dia ofensivo registrado.")

    # Exibir histórico
    st.dataframe(historico)

    # **Gráficos**
    st.subheader("📈 Gráficos de Consumo")

    # Total consumido por dia
    fig_dia = px.bar(consumo_diario, x=consumo_diario.index, y="quantidade_ml", title="Total Consumido por Dia")
    st.plotly_chart(fig_dia, use_container_width=True)

    # Total consumido por hora
    historico["hora"] = historico["data_hora"].dt.hour
    consumo_hora = historico.groupby("hora")["quantidade_ml"].sum()
    fig_hora = px.bar(consumo_hora, x=consumo_hora.index, y="quantidade_ml", title="Total Consumido por Hora")
    st.plotly_chart(fig_hora, use_container_width=True)

    # Média de consumo diário
    media_diaria = consumo_diario.mean()
    st.metric("📌 Média de Consumo Diário", f"{media_diaria:.2f} ml")

    # Média de consumo por hora
    media_horaria = consumo_hora.mean()
    st.metric("⏳ Média de Consumo por Hora", f"{media_horaria:.2f} ml")

else:
    st.info("Nenhum consumo registrado ainda.")
