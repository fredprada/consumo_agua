import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime
from PIL import Image
import pytz

# Configuração da página
st.set_page_config(
    page_title="Pedrito, o Fiscal da Hidratação",
    page_icon="🚰",
    layout="wide"
)

# Carregar e exibir a imagem do Pedrito
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

# Função para registrar consumo
def registrar_consumo(usuario_id, quantidade_ml):
    agora_utc = datetime.now(pytz.utc)  # Hora atual em UTC
    agora_local = agora_utc.astimezone(UTC_MINUS_3)  # Converte para UTC-3
    data = {
        "usuario_id": usuario_id,
        "data_hora": agora_local.isoformat(),
        "quantidade_ml": quantidade_ml,
    }
    response = requests.post(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}", json=data, headers=HEADERS)
    return response.status_code == 201

# Função para obter histórico do usuário
def obter_historico(usuario_id):
    query = f"?usuario_id=eq.{usuario_id}&select=*"
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}{query}", headers=HEADERS)
    if response.status_code == 200:
        return pd.DataFrame(response.json())
    return pd.DataFrame()

# Função para obter ranking geral
def obter_ranking():
    query = "?select=usuario_id,quantidade_ml"
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}{query}", headers=HEADERS)
    if response.status_code == 200:
        df = pd.DataFrame(response.json())
        if not df.empty:
            ranking = df.groupby("usuario_id")["quantidade_ml"].sum().reset_index()
            ranking = ranking.sort_values(by="quantidade_ml", ascending=False)
            return ranking
    return pd.DataFrame()

# Entrada do usuário
usuario_id = st.text_input("Digite seu ID de usuário:")

if usuario_id:
    quantidade = st.number_input("Quantas unidades você tomou?", min_value=1, step=1, value=1)
    medida = st.selectbox("Selecione a medida:", list(MEDIDAS.keys()))

    if MEDIDAS[medida] is None:
        quantidade_ml = st.number_input("Digite a quantidade em ml:", min_value=1, step=1)
    else:
        quantidade_ml = quantidade * MEDIDAS[medida]

    if st.button("Registrar"):
        if registrar_consumo(usuario_id, quantidade_ml):
            st.success(f"Registrado: {quantidade_ml}ml!")
        else:
            st.error("Erro ao registrar consumo.")

    # Histórico de consumo
    st.subheader("📊 Histórico de Consumo")
    historico = obter_historico(usuario_id)

    if not historico.empty:
        historico['data_hora'] = pd.to_datetime(historico['data_hora']).dt.tz_convert(UTC_MINUS_3)  # Ajusta para UTC-3
        historico = historico.sort_values(by="data_hora", ascending=False)

        # Criar colunas de data e hora já convertidas para UTC-3
        historico["data"] = historico["data_hora"].dt.date
        historico["hora"] = historico["data_hora"].dt.hour

        # Criar index de horas para garantir que todas as horas do dia apareçam no gráfico
        todas_horas = pd.DataFrame({"hora": list(range(24))})

        # **Consumo por dia (gráfico de linha)**
        consumo_diario = historico.groupby("data")["quantidade_ml"].sum().reset_index()
        fig_dia = px.line(consumo_diario, x="data", y="quantidade_ml", title="Total Consumido por Dia")
        st.plotly_chart(fig_dia)

        # **Consumo por hora (gráfico de linha)**
        consumo_hora = historico.groupby("hora")["quantidade_ml"].sum().reset_index()
        consumo_hora = todas_horas.merge(consumo_hora, on="hora", how="left").fillna(0)  # Garantir todas as horas 0-23
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

    # Indicadores comparativos
    st.subheader("📊 Comparativo de Consumo")
    ranking = obter_ranking()

    if not ranking.empty:
        usuario_posicao = ranking[ranking["usuario_id"] == usuario_id]
        if not usuario_posicao.empty:
            posicao = ranking[ranking["usuario_id"] == usuario_id].index[0] + 1
            total_consumido = usuario_posicao["quantidade_ml"].values[0]
            st.write(f"Você está na posição **{posicao}** do ranking com **{total_consumido}ml** consumidos.")

        # Exibir ranking dos top 5 consumidores
        st.subheader("🏆 Ranking de Consumo")
        top5 = ranking.head(5)
        st.dataframe(top5)

    else:
        st.write("Nenhum dado para exibir no ranking.")
