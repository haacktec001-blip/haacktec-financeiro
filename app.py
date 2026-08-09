import streamlit as st
import json
import os
import copy
from datetime import datetime

DATA_FILE = "dados_haacktec_fin.json"

st.set_page_config(page_title="Haacktec - Gestão Financeira", page_icon="💰", layout="centered")

MESES_PT = {
    "January": "Janeiro", "February": "Fevereiro", "March": "Março",
    "April": "Abril", "May": "Maio", "June": "Junho",
    "July": "Julho", "August": "Agosto", "September": "Setembro",
    "October": "Outubro", "November": "Novembro", "December": "Dezembro"
}

DESPESAS_INICIAIS_PADRAO = [
    {"categoria": "💧 Água", "meta": 0.0, "itens": []},
    {"categoria": "🏠 Aluguel", "meta": 0.0, "itens": []},
    {"categoria": "🛒 Compras do Mês", "meta": 0.0, "itens": []},
    {"categoria": "⚡ Luz", "meta": 0.0, "itens": []},
    {"categoria": "💊 Saúde", "meta": 0.0, "itens": []}
]

CARTOES_PADRAO = [
    "Dinheiro / Pix", "Mercado Pago", "Nubank", "Itaú", "Caixa",
    "Bradesco", "Banco do Brasil", "Santander", "Banco Inter", "C6 Bank"
]

def obter_mes_atual_pt():
    mes_en = datetime.now().strftime("%B")
    mes_pt = MESES_PT.get(mes_en, mes_en)
    ano = datetime.now().strftime("%Y")
    return f"{mes_pt} / {ano}"

def carregar_dados():
    if not os.path.exists(DATA_FILE):
        return {
            "configurado": True,
            "mes_atual": obter_mes_atual_pt(),
            "historico": {},
            "cartoes": CARTOES_PADRAO,
            "receitas": [{"tipo": "Salário Principal", "fonte": "Empregador", "valor": 5000.0}],
            "caixinhas": [
                {"nome": "Reserva de Ferramentas", "dinheiro_inicial": 0.0, "aporte_mensal": 0.0, "cdi_anual": 10.50}
            ],
            "despesas": copy.deepcopy(DESPESAS_INICIAIS_PADRAO),
            "log_movimentacoes": []
        }
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_dados(dados):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

dados = carregar_dados()

st.title("🛠️ Haacktec - Gestão Financeira")
st.write(f"**Mês Atual:** {dados.get('mes_atual', '')}")

# 📊 Cálculo dos Totais
total_ganhos = sum(i["valor"] for i in dados.get("receitas", []))
total_gastos = sum(sum(item["valor"] for item in d.get("itens", [])) for d in dados.get("despesas", []))
saldo_livre = total_ganhos - total_gastos

# 📱 Cards de Resumo na Tela
col1, col2, col3 = st.columns(3)
col1.metric("Ganhos", f"R$ {total_ganhos:.2f}")
col2.metric("Gastos", f"R$ {total_gastos:.2f}")
col3.metric("Saldo Livre", f"R$ {saldo_livre:.2f}")

st.divider()

# 📂 Visualização e Adição de Despesas
st.subheader("📋 Despesas por Categoria")

for d in dados.get("despesas", []):
    total_cat = sum(item["valor"] for item in d.get("itens", []))
    with st.expander(f"{d['categoria']} — Total: R$ {total_cat:.2f}"):
        if d.get("itens"):
            for idx, item in enumerate(d["itens"]):
                st.write(f"• **{item['desc']}**: R$ {item['valor']:.2f} (Cartão: {item.get('cartao', 'Pix')})")
        else:
            st.info("Nenhum item cadastrado nesta categoria.")

st.divider()

# ➕ Formulário para Adicionar Novo Item Rápido
st.subheader("➕ Adicionar Novo Gasto")
with st.form("form_novo_gasto"):
    cat_nomes = [d["categoria"] for d in dados["despesas"]]
    cat_escolhida = st.selectbox("Categoria", cat_nomes)
    desc_item = st.text_input("Descrição do Gasto")
    valor_item = st.number_input("Valor (R$)", min_value=0.0, format="%.2f")
    cartao_escolhido = st.selectbox("Forma de Pagamento", dados.get("cartoes", CARTOES_PADRAO))
    
    enviar = st.form_submit_button("Salvar Gasto")
    if enviar and desc_item and valor_item > 0:
        for d in dados["despesas"]:
            if d["categoria"] == cat_escolhida:
                d.get("itens", []).append({
                    "desc": desc_item,
                    "valor": valor_item,
                    "cartao": cartao_escolhido,
                    "parcelas": 1,
                    "dia_vencimento": 10,
                    "pago": True
                })
                salvar_dados(dados)
                st.success(f"Gasto '{desc_item}' adicionado com sucesso!")
                st.rerun()
