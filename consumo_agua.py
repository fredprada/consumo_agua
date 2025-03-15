import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta
from PIL import Image
import pytz

# Configuração da página
st.set_page_config(
    page_title="Pedrito, o Fiscal da Hidratação",
    page_icon="🚰",
    layout="wide"
)

# Exibir imagem do Pedrito
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

# Fuso horário UTC-3 (Brasil)
UTC_MINUS_3 = pytz.timezone("America/Sao_Paulo")

# Conversão de medidas
MEDIDAS = {
    "Gole (30ml)": 30,
    "Copo pequeno (100ml)": 100,
    "Copo grande (200ml)": 200,
    "Garrafa pequena (500ml)": 500,
    "Garrafa grande (1L)": 1000,
    "Mililitros (digite abaixo)": None,
}

# Registrar consumo
def registrar_consumo(quantidade_ml):
    agora_utc = datetime.now(pytz.utc)
    agora_local = agora_utc.astimezone(UTC_MINUS_3)
    data = {
        "data_hora": agora_local.isoformat(),
        "quantidade_ml": quantidade_ml,
    }
    response = requests.post(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}", json=data, headers=HEADERS)
    return response.status_code == 201

# Obter histórico
def obter_historico():
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?select=*", headers=HEADERS)
    if response.status_code == 200:
        return pd.DataFrame(response.json())
    return pd.DataFrame()

# Entrada do usuário
quantidade = st.number_input("Quantas unidades você tomou?", min_value=1, step=1, value=1)
medida = st.selectbox("Selecione a medida:", list(MEDIDAS.keys()))

if MEDIDAS[medida] is None:
    quantidade_ml = st.number_input("Digite a quantidade em ml:", min_value=1, step=1)
else:
    quantidade_ml = quantidade * MEDIDAS[medida]

if st.button("Registrar"):
    if registrar_consumo(quantidade_ml):
        st.success(f"Registrado: {quantidade_ml}ml!")
    else:
        st.error("Erro ao registrar consumo.")

# Histórico de consumo
historico = obter_historico()

if not historico.empty:
    historico['data_hora'] = pd.to_datetime(historico['data_hora']).dt.tz_convert(UTC_MINUS_3)
    historico = historico.sort_values(by="data_hora", ascending=False)

    # Criar colunas de data e hora já convertidas para UTC-3
    historico["data"] = historico["data_hora"].dt.date
    historico["hora"] = historico["data_hora"].dt.hour

    # Data de hoje e ontem
    hoje = datetime.now(UTC_MINUS_3).date()
    ontem = hoje - timedelta(days=1)

    # Criar index de horas para garantir que todas as horas do dia apareçam no gráfico
    todas_horas = pd.DataFrame({"hora": list(range(24))})

    # **Cálculos para indicadores**
    consumo_diario = historico.groupby("data")["quantidade_ml"].sum().reset_index()
    
    total_hoje = consumo_diario[consumo_diario["data"] == hoje]["quantidade_ml"].sum()
    total_ontem = consumo_diario[consumo_diario["data"] == ontem]["quantidade_ml"].sum()
    media_diaria = consumo_diario["quantidade_ml"].mean()

    # **Variação vs ontem**
    variacao_vs_ontem = ((total_hoje - total_ontem) / total_ontem * 100) if total_ontem > 0 else 0
    emoji_vs_ontem = "🚀" if variacao_vs_ontem > 0 else "😞"

    # **Variação vs média**
    variacao_vs_media = ((total_hoje - media_diaria) / media_diaria * 100) if media_diaria > 0 else 0
    emoji_vs_media = "😀" if variacao_vs_media > 0 else "☹️"

    # **Dias de Ofensiva**
    dias_ofensivos = consumo_diario[consumo_diario["quantidade_ml"] >= 3000]["data"]
    
    # **Dias consecutivos de Ofensiva**
    dias_ofensivos_sorted = dias_ofensivos.sort_values(ascending=False).tolist()
    consecutivos = 0
    for i in range(len(dias_ofensivos_sorted) - 1):
        if (dias_ofensivos_sorted[i] - dias_ofensivos_sorted[i + 1]).days == 1:
            consecutivos += 1
        else:
            break

    # **Exibir Indicadores**
    st.subheader("📊 Indicadores de Consumo")
    col1, col2, col3 = st.columns(3)
    col1.metric("💦 Total de hoje", f"{total_hoje:.0f} ml")
    col2.metric("📊 Média diária", f"{media_diaria:.0f} ml")
    col3.metric("🔥 Dias de Ofensiva consecutivos", f"{consecutivos} dias")

    col1, col2 = st.columns(2)
    col1.metric(f"📈 Comparado a ontem {emoji_vs_ontem}", f"{variacao_vs_ontem:.1f}%")
    col2.metric(f"📉 Comparado à média {emoji_vs_media}", f"{variacao_vs_media:.1f}%")

    st.subheader("🔥 Dias de Ofensiva")
    st.write(dias_ofensivos.tolist() if not dias_ofensivos.empty else "Nenhum dia de Ofensiva registrado.")

    # **Gráficos**
    st.subheader("📊 Histórico de Consumo")

    fig_dia = px.line(consumo_diario, x="data", y="quantidade_ml", title="Total Consumido por Dia")
    st.plotly_chart(fig_dia)

    consumo_hoje = historico[historico["data"] == hoje].groupby("hora")["quantidade_ml"].sum().reset_index()
    consumo_hoje = todas_horas.merge(consumo_hoje, on="hora", how="left").fillna(0)
    fig_hora = px.line(consumo_hoje, x="hora", y="quantidade_ml", title="Total Consumido por Hora (Hoje)")
    st.plotly_chart(fig_hora)

    media_horaria = historico.groupby("hora")["quantidade_ml"].mean().reset_index()
    media_horaria = todas_horas.merge(media_horaria, on="hora", how="left").fillna(0)
    fig_media_hora = px.bar(media_horaria, x="hora", y="quantidade_ml", title="Média de Consumo por Hora")
    st.plotly_chart(fig_media_hora)

    # **Exibir Tabela Completa**
    st.subheader("📋 Histórico Completo")
    st.dataframe(historico)

else:
    st.write("Nenhum registro encontrado.")
