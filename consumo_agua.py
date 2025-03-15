import streamlit as st
import pandas as pd
import requests
from datetime import datetime

SUPABASE_URL = "https://hufpveshgntnrwwfazjb.supabase.co"
SUPABASE_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1ZnB2ZXNoZ250bnJ3d2ZhempiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDIwMDEyMDEsImV4cCI6MjA1NzU3NzIwMX0.ez1VOEHgTbCWEgsEihgDUx4_WCENVcMm4KpN5rJkzM8"
SUPABASE_TABLE = "consumo_agua"

HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
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

quantidade = st.number_input("Quantos ml você bebeu agora?", min_value=50, step=50)
if st.button("Registrar"):
    if registrar_consumo(quantidade):
        st.success("Consumo registrado com sucesso!")
    else:
        st.error("Erro ao registrar consumo.")

st.subheader("📊 Histórico de Consumo")
historico = obter_historico()

if not historico.empty:
    historico['data_hora'] = pd.to_datetime(historico['data_hora'])
    historico = historico.sort_values(by="data_hora", ascending=False)
    st.dataframe(historico)

    # Estatísticas
    st.subheader("📈 Estatísticas")
    total_hoje = historico[historico["data_hora"].dt.date == datetime.today().date()]["quantidade_ml"].sum()
    st.metric("Total consumido hoje", f"{total_hoje} ml")
else:
    st.write("Nenhum registro encontrado.")
