import streamlit as st
import json
import os
import copy
from datetime import datetime

DATA_FILE = "dados_haacktec_fin.json"

st.set_page_config(page_title="Haacktec - Gestão Financeira", page_icon="💰", layout="wide")

MESES_PT = {
    "January": "Janeiro", "February": "Fevereiro", "March": "Março",
    "April": "Abril", "May": "Maio", "June": "Junho",
    "July": "Julho", "August": "Agosto", "September": "Setembro",
    "October": "Outubro", "November": "Novembro", "December": "Dezembro"
}

DESPESAS_INICIAIS_PADRAO = [
    {"categoria": "💧 Água", "meta": 0.0, "itens": []},
    {"categoria": "🏠 Aluguel", "meta": 0.0, "itens": []},
    {"categoria": "⚡ Luz", "meta": 0.0, "itens": []},
    {"categoria": "🛒 Compras do Mês", "meta": 0.0, "itens": []},
    {"categoria": "💊 Saúde", "meta": 0.0, "itens": []},
    {"categoria": "💳 Cartão de Crédito", "meta": 0.0, "itens": []},
    {"categoria": "📂 Financiamentos / Dívidas", "meta": 0.0, "itens": []}
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

# 🖥️ Layout em Duas Colunas (Esquerda: Categorias | Direita: Painel de Controle)
col_esq, col_dir = st.columns([1.2, 1])

with col_esq:
    st.markdown(f"### Mês: {dados.get('mes_atual', '')}")
    st.divider()
    st.markdown("#### 📂 Categorias / Despesas")

    for d in dados.get("despesas", []):
        total_cat = sum(item["valor"] for item in d.get("itens", []))
        with st.expander(f"{d['categoria']} — Total: R$ {total_cat:.2f}"):
            if d.get("itens"):
                for idx, item in enumerate(d["itens"]):
                    st.write(f"• **{item['desc']}**: R$ {item['valor']:.2f} (Pagto: {item.get('cartao', 'Pix')})")
            else:
                st.info("Nenhum item cadastrado nesta categoria.")

    st.divider()
    with st.expander("➕ Adicionar Nova Categoria"):
        nova_cat_nome = st.text_input("Nome da Categoria")
        if st.button("Criar Categoria"):
            if nova_cat_nome:
                dados["despesas"].append({"categoria": f"📁 {nova_cat_nome}", "meta": 0.0, "itens": []})
                salvar_dados(dados)
                st.success("Categoria criada com sucesso!")
                st.rerun()

with col_dir:
    st.markdown("### 🎛️ Painel de Controle & Saldo")
    
    total_ganhos = sum(i["valor"] for i in dados.get("receitas", []))
    total_gastos = sum(sum(item["valor"] for item in d.get("itens", [])) for d in dados.get("despesas", []))
    saldo_livre = total_ganhos - total_gastos

    st.metric("GANHOS DO MÊS", f"R$ {total_ganhos:.2f}")
    st.metric("GASTOS DO MÊS", f"R$ {total_gastos:.2f}")
    st.metric("SALDO LIVRE", f"R$ {saldo_livre:.2f}")

    st.divider()
    st.markdown("#### ⚙️ Ações e Ferramentas")

    with st.expander("⚙️ Questionário de Perfil Financeiro"):
        novo_salario = st.number_input("Qual é a sua Renda Mensal Líquida (R$)?", value=5000.0, format="%.2f")
        if st.button("Atualizar Perfil"):
            dados["receitas"][0]["valor"] = novo_salario
            salvar_dados(dados)
            st.success("Perfil atualizado!")
            st.rerun()

    with st.expander("➕ Adicionar Novo Gasto / Despesa"):
        with st.form("form_gasto_painel"):
            cat_nomes = [d["categoria"] for d in dados["despesas"]]
            cat_esc = st.selectbox("Categoria", cat_nomes)
            desc = st.text_input("Descrição")
            val = st.number_input("Valor (R$)", min_value=0.0, format="%.2f")
            cartao = st.selectbox("Forma de Pagamento", dados.get("cartoes", CARTOES_PADRAO))
            
            if st.form_submit_button("Salvar Despesa") and desc and val > 0:
                for d in dados["despesas"]:
                    if d["categoria"] == cat_esc:
                        d.get("itens", []).append({
                            "desc": desc, "valor": val, "cartao": cartao,
                            "parcelas": 1, "dia_vencimento": 10, "pago": True
                        })
                        salvar_dados(dados)
                        st.success("Gasto adicionado!")
                        st.rerun()

    with st.expander("📦 Caixinhas & Investimentos"):
        st.write("Suas reservas configuradas:")
        for c in dados.get("caixinhas", []):
            st.write(f"- **{c['nome']}** (CDI: {c['cdi_anual']}%)")
