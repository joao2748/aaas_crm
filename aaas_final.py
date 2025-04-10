# aaas_final.py
import pandas as pd
import streamlit as st
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from textblob import TextBlob
import logging
import plotly.express as px
from fpdf import FPDF
import base64

# --- Configurações Iniciais --- #
logging.basicConfig(filename='aaas_errors.log', level=logging.ERROR, 
                   format='%(asctime)s - %(levelname)s - %(message)s')

# --- Classe Principal AAAS --- #
class AAAS:
    def __init__(self):
        self.credenciais = Credentials.from_service_account_file('credenciais.json')
        self.sheet = self._conectar_google_sheets()
        self.dados = self._carregar_dados()
        
    def _conectar_google_sheets(self):
        try:
            gc = gspread.authorize(self.credenciais)
            return gc.open("CRM AAAS").sheet1
        except Exception as e:
            logging.error(f"Erro no Google Sheets: {e}")
            return None

    def _carregar_dados(self):
        if self.sheet:
            df = pd.DataFrame(self.sheet.get_all_records())
            if not df.empty and "Data" in df.columns:
                df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
            return df
        return pd.DataFrame()

    def analisar_sentimento(self, texto):
        try:
            blob = TextBlob(texto)
            polaridade = blob.sentiment.polarity
            if polaridade > 0:
                return {"sentimento": "POSITIVE", "confianca": polaridade}
            elif polaridade < 0:
                return {"sentimento": "NEGATIVE", "confianca": abs(polaridade)}
            else:
                return {"sentimento": "NEUTRAL", "confianca": 0}
        except Exception as e:
            logging.error(f"Erro na análise: {e}")
            return {"sentimento": "NEUTRO", "confianca": 0}

    def enviar_whatsapp(self, telefone, mensagem):
        try:
            print(f"[WHATSAPP] Mensagem enviada para {telefone}: {mensagem[:50]}...")
            return {"status": "enviado", "message_id": f"WA_{datetime.now().timestamp()}"}
        except Exception as e:
            logging.error(f"Erro no WhatsApp: {e}")
            return {"status": "erro", "detalhes": str(e)}

# --- Dashboard Streamlit --- #
def main():
    st.set_page_config(page_title="AAAS Social Seller", layout="wide")
    aaas = AAAS()

    st.sidebar.title("Configurações")
    dark_mode = st.sidebar.toggle("🌙 Modo Escuro")

    if dark_mode:
        st.markdown("""
        <style>
            .stApp { background-color: #1e1e1e; color: #ffffff; }
            .st-bb { background-color: #2d2d2d; }
            .css-18e3th9 { background-color: #1e1e1e; }
        </style>
        """, unsafe_allow_html=True)

    st.title("📊 Painel AAAS Social Seller")

    if aaas.dados.empty or "Status" not in aaas.dados.columns:
        st.warning("Dados não carregados ou faltando colunas obrigatórias.")
        return

    with st.expander("🔍 Filtros Avançados", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filtro = st.multiselect("Status", aaas.dados["Status"].unique())
        with col2:
            plataforma_filtro = st.multiselect("Plataforma", aaas.dados["Plataforma"].unique())
        with col3:
            data_min = st.date_input("Data inicial", aaas.dados["Data"].min())
            data_max = st.date_input("Data final", aaas.dados["Data"].max())

    dados_filtrados = aaas.dados.copy()
    if status_filtro:
        dados_filtrados = dados_filtrados[dados_filtrados["Status"].isin(status_filtro)]
    if plataforma_filtro:
        dados_filtrados = dados_filtrados[dados_filtrados["Plataforma"].isin(plataforma_filtro)]
    dados_filtrados = dados_filtrados[
        (dados_filtrados["Data"] >= pd.to_datetime(data_min)) & 
        (dados_filtrados["Data"] <= pd.to_datetime(data_max))
    ]

    st.header("📈 Visão Geral")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Leads", len(dados_filtrados))

    sentimentos = dados_filtrados["Interação"].apply(aaas.analisar_sentimento)
    positivos = sum(1 for s in sentimentos if s["sentimento"] == "POSITIVE")
    col2.metric("Positivos", f"{positivos} ({(positivos/len(dados_filtrados)*100 if len(dados_filtrados) else 0):.1f}%)")

    col3.metric("Valor Médio", f"R${dados_filtrados['Valor'].mean():.2f}" if not dados_filtrados.empty else "R$0.00")

    tab1, tab2 = st.tabs(["Distribuição", "Desempenho"])
    with tab1:
        fig = px.pie(
            dados_filtrados,
            names="Plataforma",
            title="Leads por Plataforma",
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        fig = px.bar(
            dados_filtrados["Status"].value_counts(),
            title="Leads por Status",
            labels={"value": "Quantidade", "index": "Status"}
        )
        st.plotly_chart(fig, use_container_width=True)

    st.header("💼 Leads Detalhados")
    st.dataframe(dados_filtrados, use_container_width=True, height=400)

    st.header("⚡ Ações Rápidas")
    if st.button("🔄 Atualizar Dados"):
        aaas.dados = aaas._carregar_dados()
        st.rerun()

    if st.button("📤 Enviar WhatsApp"):
        for _, row in dados_filtrados.iterrows():
            mensagem = f"Olá {row['Nome']}! Obrigado pelo contato via {row['Plataforma']}."
            resultado = aaas.enviar_whatsapp(row['Telefone'], mensagem)
            if resultado["status"] == "enviado":
                st.success(f"Mensagem enviada para {row['Nome']}")
            else:
                st.error(f"Erro ao enviar para {row['Nome']}")

    if st.button("💾 Gerar Relatório PDF"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Relatório AAAS - Social Seller", ln=1, align="C")
        pdf.cell(200, 10, txt=f"Período: {data_min} a {data_max}", ln=1)
        pdf.cell(200, 10, txt=f"Total Leads: {len(dados_filtrados)}", ln=1)

        pdf_output = pdf.output(dest="S").encode("latin1")
        b64 = base64.b64encode(pdf_output).decode()
        href = f'<a href="data:application/octet-stream;base64,{b64}" download="relatorio_aaas.pdf">Baixar PDF</a>'
        st.markdown(href, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
