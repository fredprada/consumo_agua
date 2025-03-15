import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime

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
    "Mililitros (digite abaixo)": None,  # O usuário informará o valor
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
st.title("💧 Monitor de Consumo de Água")

# Input de consumo
medida = st.selectbox("Selecione a medida:", list(MEDIDAS.keys()))
quantidade = st.number_input("Quantidade:", min_value=1, step=1) if MEDIDAS[medida] is None else 1

# Calcular ml real
quantidade_ml = quantidade * (MEDIDAS[medida] if MEDIDAS[medida] else 1)

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
    st.plotly_chart(fig_dia)

    # Total consumido por hora
    historico["hora"] = historico["data_hora"].dt.hour
    consumo_hora = historico.groupby("hora")["quantidade_ml"].sum()
    fig_hora = px.bar(consumo_hora, x=consumo_hora.index, y="quantidade_ml", title="Total Consumido por Hora")
    st.plotly_chart(fig_hora)

    # Média de consumo diário
    media_diaria = consumo_diario.mean()
    st.metric("📌 Média de Consumo Diário", f"{media_diaria:.2f} ml")

    # Média de consumo por hora
    media_horaria = consumo_hora.mean()
    st.metric("⏳ Média de Consumo por Hora", f"{media_horaria:.2f} ml")

else:
    st.write("Nenhum registro encontrado.")
