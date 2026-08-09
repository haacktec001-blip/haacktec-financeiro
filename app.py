import customtkinter as ctk
import json
import os
import re
import copy
import csv
from datetime import datetime
from tkinter import filedialog, messagebox

# Tentativa de importação do ReportLab
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

# Tentativa de importação do Matplotlib para os gráficos
try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

DATA_FILE = "dados_haacktec_fin.json"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

MESES_PT = {
    "January": "Janeiro", "February": "Fevereiro", "March": "Março",
    "April": "Abril", "May": "Maio", "June": "Junho",
    "July": "Julho", "August": "Agosto", "September": "Setembro",
    "October": "Outubro", "November": "Novembro", "December": "Dezembro"
}

BANCO_ICONES = [
    "💧", "🏠", "🛒", "🌐", "⚡", "💊", "💳", "📦", 
    "🛠️", "🚗", "🎸", "💻", "📚", "🍔", "✈️", "💡", "🔧", "📱"
]

DESPESAS_INICIAIS_PADRAO = [
    {"categoria": "💧 Água", "meta": 0.0, "itens": []},
    {"categoria": "🏠 Aluguel", "meta": 0.0, "itens": []},
    {"categoria": "🛒 Compras do Mês", "meta": 0.0, "itens": []},
    {"categoria": "🌐 Internet", "meta": 0.0, "itens": []},
    {"categoria": "⚡ Luz", "meta": 0.0, "itens": []},
    {"categoria": "💊 Saúde", "meta": 0.0, "itens": []}
]

CARTOES_PADRAO = [
    "Dinheiro / Pix", "Mercado Pago", "Nubank", "Itaú", "Caixa",
    "Bradesco", "Banco do Brasil", "Santander", "Banco Inter", "C6 Bank",
    "BTG Pactual", "PicPay", "PagBank", "Banrisul", "Sicredi", "Sicoob",
    "Neon", "Credicard", "Caixa Tem", "Outro"
]

# ==============================================================================
# MÓDULO 1: REGRAS E CÁLCULOS FINANCEIROS
# ==============================================================================

def obter_mes_atual_pt():
    mes_en = datetime.now().strftime("%B")
    mes_pt = MESES_PT.get(mes_en, mes_en)
    ano = datetime.now().strftime("%Y")
    return f"{mes_pt} / {ano}"

def calcular_ir_cdi(rendimento_bruto, dias_investido=365):
    if dias_investido <= 180:
        aliquota = 0.225
    elif dias_investido <= 360:
        aliquota = 0.20
    elif dias_investido <= 720:
        aliquota = 0.175
    else:
        aliquota = 0.15
    return rendimento_bruto * aliquota

def calcular_rendimento_caixinha(din_ini, ap_men, cdi_anual=10.50, dias_investido=30):
    taxa_mensal = (1 + cdi_anual / 100) ** (1 / 12) - 1
    rend_saldo_inicial = din_ini * taxa_mensal
    rend_aporte = ap_men * (taxa_mensal * 0.5)
    
    rend_bruto_total = rend_saldo_inicial + rend_aporte
    imposto = calcular_ir_cdi(rend_bruto_total, dias_investido=dias_investido)
    rend_liquido = rend_bruto_total - imposto
    
    saldo_final_estimado = din_ini + ap_men + rend_liquido
    return saldo_final_estimado, rend_liquido

def item_esta_pago(item):
    if "pago" in item:
        return bool(item["pago"])
    dia_vencimento = item.get("dia_vencimento")
    if not dia_vencimento:
        return False
    dia_atual = datetime.now().day
    return dia_atual >= dia_vencimento

def item_esta_atrasado(item):
    if item.get("pago", False):
        return False
    dia_vencimento = item.get("dia_vencimento")
    if not dia_vencimento:
        return False
    dia_atual = datetime.now().day
    return dia_atual > dia_vencimento

# ==============================================================================
# MÓDULO 2: PERSISTÊNCIA DE DADOS E LOGS DE AUDITORIA
# ==============================================================================

def carregar_dados(caminho_arquivo=DATA_FILE):
    if not os.path.exists(caminho_arquivo):
        dados_iniciais = {
            "configurado": False,
            "mes_atual": obter_mes_atual_pt(),
            "historico": {},
            "cartoes": CARTOES_PADRAO,
            "receitas": [{"tipo": "Salário Principal", "fonte": "Empregador", "valor": 0.0}],
            "caixinhas": [
                {"nome": "Reserva de Ferramentas", "dinheiro_inicial": 0.0, "aporte_mensal": 0.0, "cdi_anual": 10.50},
                {"nome": "Reserva de Emergência", "dinheiro_inicial": 0.0, "aporte_mensal": 0.0, "cdi_anual": 10.50}
            ],
            "despesas": copy.deepcopy(DESPESAS_INICIAIS_PADRAO),
            "log_movimentacoes": []
        }
        return dados_iniciais
    
    with open(caminho_arquivo, "r", encoding="utf-8") as f:
        dados = json.load(f)
        if "historico" not in dados:
            dados["historico"] = {}
        if "configurado" not in dados:
            dados["configurado"] = True
        if "log_movimentacoes" not in dados:
            dados["log_movimentacoes"] = []
            
        dados["cartoes"] = CARTOES_PADRAO
            
        mes_corrente = obter_mes_atual_pt()
        if "mes_atual" not in dados:
            dados["mes_atual"] = mes_corrente

        if "caixinhas" not in dados:
            dados["caixinhas"] = [
                {"nome": "Caixinha Geral", "dinheiro_inicial": 0.0, "aporte_mensal": 0.0, "cdi_anual": 10.50}
            ]
        
        if "receitas" not in dados or not dados["receitas"]:
            dados["receitas"] = [{"tipo": "Salário Principal", "fonte": "Empregador", "valor": 0.0}]

        for d in dados.get("despesas", []):
            if "meta" not in d:
                d["meta"] = 0.0
            if "itens" not in d:
                d["itens"] = []
            else:
                for item in d["itens"]:
                    if "data_registro" not in item:
                        item["data_registro"] = datetime.now().strftime("%d/%m/%Y")

        if dados["mes_atual"] != mes_corrente:
            mes_antigo = dados["mes_atual"]
            dados["historico"][mes_antigo] = {
                "receitas": dados.get("receitas", []),
                "despesas": dados.get("despesas", []),
                "caixinhas": dados.get("caixinhas", [])
            }
            novas_despesas = []
            for d in dados.get("despesas", []):
                novos_itens = []
                for item in d.get("itens", []):
                    parcelas = item.get("parcelas", 1)
                    if parcelas > 1:
                        item["parcelas"] = parcelas - 1
                        item["pago"] = False
                        novos_itens.append(item)
                novas_despesas.append({
                    "categoria": d["categoria"], 
                    "meta": d.get("meta", 0.0), 
                    "itens": novos_itens
                })
            dados["despesas"] = novas_despesas
            dados["mes_atual"] = mes_corrente
            salvar_dados(dados)

        return dados

def salvar_dados(dados, caminho_arquivo=DATA_FILE):
    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

def registrar_log(dados, mensagem):
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    entry = f"[{data_hora}] {mensagem}"
    dados.setdefault("log_movimentacoes", []).insert(0, entry)
    if len(dados["log_movimentacoes"]) > 100:
        dados["log_movimentacoes"] = dados["log_movimentacoes"][:100]

# ==============================================================================
# MÓDULO 3: INTERFACE GRÁFICA (CUSTOMTKINTER)
# ==============================================================================

class AppPlanilhaEstilo(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Haacktec - Gestão Financeira Integrada")
        self.geometry("1020x820")
        self.resizable(True, True)

        self.dados = carregar_dados()

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # PAINEL ESQUERDO: LANÇAMENTOS
        self.frame_esq = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=8)
        self.frame_esq.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.frame_esq.grid_rowconfigure(1, weight=1)
        self.frame_esq.grid_columnconfigure(0, weight=1)

        self.lbl_esq_titulo = ctk.CTkLabel(self.frame_esq, text=f"Mês: {self.dados.get('mes_atual', 'Atual')}", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_esq_titulo.grid(row=0, column=0, pady=10)

        self.scroll_cat = ctk.CTkScrollableFrame(self.frame_esq, fg_color="#222222")
        self.scroll_cat.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        btn_frame = ctk.CTkFrame(self.frame_esq, fg_color="transparent")
        btn_frame.grid(row=2, column=0, pady=10, sticky="ew", padx=10)
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        btn_add = ctk.CTkButton(btn_frame, text="➕ Nova Categoria", fg_color="#2b7a78", hover_color="#3aafa9", command=self.janela_adicionar_categoria)
        btn_add.grid(row=0, column=0, padx=2, sticky="ew")

        btn_del = ctk.CTkButton(btn_frame, text="🗑️ Excluir Categoria", fg_color="#c0392b", hover_color="#e74c3c", command=self.janela_remover_gasto)
        btn_del.grid(row=0, column=1, padx=2, sticky="ew")

        # PAINEL DIREITO: DASHBOARD
        self.frame_dir = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=8)
        self.frame_dir.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.frame_dir.grid_columnconfigure(0, weight=1)

        lbl_dir_titulo = ctk.CTkLabel(self.frame_dir, text="Painel de Controle & Saldo", font=ctk.CTkFont(size=16, weight="bold"))
        lbl_dir_titulo.pack(pady=10)

        # CRIAÇÃO DO ALERTA GLOBAL ANTES DE QUALQUER ATUALIZAÇÃO DA TABELA
        self.alerta_atraso_frame = ctk.CTkFrame(self.frame_dir, fg_color="#5a1e1e", corner_radius=6, border_width=1, border_color="#e74c3c")
        self.alerta_atraso_lbl = ctk.CTkLabel(self.alerta_atraso_frame, text="⚠️ Atenção: Possui dívidas atrasadas pendentes!", font=ctk.CTkFont(size=11, weight="bold"), text_color="#ffcccc")
        self.alerta_atraso_lbl.pack(padx=10, pady=6)
        self.alerta_atraso_frame.pack_forget()

        self.card_ganhos = self.criar_card("GANHOS TOTAIS (RENDA)", "R$ 0,00", "#2b7a78")
        self.card_gastos = self.criar_card("GASTOS TOTAIS (DESPESAS)", "R$ 0,00", "#c0392b")
        self.card_invest = self.criar_card("ESTIMATIVA CAIXINHAS (CDI)", "R$ 0,00", "#8e44ad")
        self.card_saldo = self.criar_card("SALDO DISPONÍVEL (LIVRE)", "R$ 0,00", "#27ae60")
        self.card_patrimonio = self.criar_card("PATRIMÔNIO TOTAL ESTIMADO", "R$ 0,00", "#3a86ff")

        # AGORA É SEGURO ATUALIZAR A TABELA E O DASHBOARD
        self.atualizar_tabela_categorias()
        self.atualizar_dashboard()

        btn_ganhos = ctk.CTkButton(self.frame_dir, text="💰 Gerenciar Ganhos / Renda", fg_color="#3a86ff", hover_color="#4361ee", command=self.janela_gerenciar_ganhos)
        btn_ganhos.pack(pady=2, padx=20, fill="x")

        btn_investimento = ctk.CTkButton(self.frame_dir, text="📦 Gerenciar Caixinhas Personalizadas", fg_color="#8e44ad", hover_color="#9b59b6", command=self.janela_gerenciar_caixinhas)
        btn_investimento.pack(pady=2, padx=20, fill="x")

        btn_log = ctk.CTkButton(self.frame_dir, text="📜 Ver Log de Movimentações", fg_color="#4a5568", hover_color="#718096", command=self.janela_exibir_log)
        btn_log.pack(pady=2, padx=20, fill="x")

        btn_grafico = ctk.CTkButton(self.frame_dir, text="📊 Ver Gráfico de Despesas", fg_color="#16a085", hover_color="#1abc9c", command=self.exibir_grafico_gastos)
        btn_grafico.pack(pady=2, padx=20, fill="x")

        btn_hist = ctk.CTkButton(self.frame_dir, text="📚 Ver Histórico de Meses Anteriores", fg_color="#533483", hover_color="#6f3f9f", command=self.janela_historico)
        btn_hist.pack(pady=2, padx=20, fill="x")

        btn_simulador = ctk.CTkButton(self.frame_dir, text="🔮 Simulador de Meses Futuros", fg_color="#d35400", hover_color="#e67e22", command=self.janela_simulador_futuro)
        btn_simulador.pack(pady=2, padx=20, fill="x")

        btn_pdf_geral = ctk.CTkButton(self.frame_dir, text="📄 Exportar Relatório Geral em PDF", fg_color="#2b7a78", hover_color="#3aafa9", command=self.exportar_relatorio_geral_pdf)
        btn_pdf_geral.pack(pady=2, padx=20, fill="x")

        btn_csv = ctk.CTkButton(self.frame_dir, text="📊 Exportar Planilha (CSV)", fg_color="#27ae60", hover_color="#2ecc71", command=self.exportar_planilha_csv)
        btn_csv.pack(pady=2, padx=20, fill="x")

        backup_frame = ctk.CTkFrame(self.frame_dir, fg_color="transparent")
        backup_frame.pack(pady=6, padx=20, fill="x")
        backup_frame.grid_columnconfigure(0, weight=1)
        backup_frame.grid_columnconfigure(1, weight=1)

        btn_backup = ctk.CTkButton(backup_frame, text="💾 Backup JSON", fg_color="#4a5568", hover_color="#718096", command=self.fazer_backup_json)
        btn_backup.grid(row=0, column=0, padx=2, sticky="ew")

        btn_restore = ctk.CTkButton(backup_frame, text="📂 Importar JSON", fg_color="#4a5568", hover_color="#718096", command=self.restaurar_backup_json)
        btn_restore.grid(row=0, column=1, padx=2, sticky="ew")

        if not self.dados.get("configurado", False):
            self.after(300, self.janela_onboarding_inicial)

    def configurar_janela_modal(self, win, titulo, largura, altura):
        win.title(titulo)
        win.geometry(f"{largura}x{altura}")
        win.resizable(True, True)
        win.transient(self)
        win.grab_set()

    def criar_card(self, titulo, valor_inicial, cor_borda):
        card = ctk.CTkFrame(self.frame_dir, fg_color="#2a2a2a", border_width=2, border_color=cor_borda, corner_radius=8)
        card.pack(pady=3, padx=20, fill="x")
        
        lbl_t = ctk.CTkLabel(card, text=titulo, font=ctk.CTkFont(size=10, weight="bold"), text_color="#aaaaaa")
        lbl_t.pack(anchor="w", padx=15, pady=(3, 0))
        
        lbl_v = ctk.CTkLabel(card, text=valor_inicial, font=ctk.CTkFont(size=15, weight="bold"), text_color="#ffffff")
        lbl_v.pack(anchor="w", padx=15, pady=(0, 3))
        
        card.lbl_valor = lbl_v
        return card

    def atualizar_tabela_categorias(self):
        for widget in self.scroll_cat.winfo_children():
            widget.destroy()

        header_frame = ctk.CTkFrame(self.scroll_cat, fg_color="#333333", height=30)
        header_frame.pack(fill="x", pady=2)
        ctk.CTkLabel(header_frame, text="Categoria / Descrição", font=ctk.CTkFont(weight="bold"), width=180, anchor="w").pack(side="left", padx=10)
        ctk.CTkLabel(header_frame, text="Total / Meta", font=ctk.CTkFont(weight="bold"), width=120, anchor="e").pack(side="right", padx=10)

        tem_atrasado_geral = False

        for d in self.dados["despesas"]:
            total_cat = sum(item["valor"] for item in d.get("itens", []))
            meta_cat = d.get("meta", 0.0)

            atrasado_cat = any(item_esta_atrasado(item) for item in d.get("itens", []))
            if atrasado_cat:
                tem_atrasado_geral = True

            cor_fundo_linha = "#321a1a" if atrasado_cat else "#262626"
            row = ctk.CTkFrame(self.scroll_cat, fg_color=cor_fundo_linha, height=40)
            row.pack(fill="x", pady=2)
            
            sufixo_atraso = " ⚠️" if atrasado_cat else ""
            btn_cat = ctk.CTkButton(
                row, 
                text=f" {d['categoria']}{sufixo_atraso}", 
                anchor="w", 
                fg_color="transparent", 
                hover_color="#333333",
                font=ctk.CTkFont(weight="bold"), 
                text_color="#ff5555" if atrasado_cat else "#ffffff",
                command=lambda cat=d["categoria"]: self.janela_detalhes_categoria(cat)
            )
            btn_cat.pack(side="left", padx=5, fill="x", expand=True)
            
            btn_edit_cat = ctk.CTkButton(
                row,
                text="✏️",
                width=28,
                height=26,
                fg_color="#2980b9",
                hover_color="#3498db",
                command=lambda cat=d["categoria"]: self.janela_editar_categoria(cat)
            )
            btn_edit_cat.pack(side="right", padx=2)

            if meta_cat > 0 and total_cat > meta_cat:
                cor_texto = "#ff5555"
                txt_meta = f"R$ {total_cat:.2f} / {meta_cat:.0f} ⚠️"
            elif meta_cat > 0:
                cor_texto = "#ffcccc"
                txt_meta = f"R$ {total_cat:.2f} / {meta_cat:.0f}"
            else:
                cor_texto = "#ffcccc" if total_cat > 0 else "#888888"
                txt_meta = f"R$ {total_cat:.2f}"

            lbl_val = ctk.CTkLabel(row, text=txt_meta, anchor="e", width=110, text_color=cor_texto, font=ctk.CTkFont(size=11, weight="bold"))
            lbl_val.pack(side="right", padx=5)

        if tem_atrasado_geral:
            self.alerta_atraso_frame.pack(pady=(0, 8), padx=20, fill="x", before=self.card_ganhos)
        else:
            self.alerta_atraso_frame.pack_forget()

    def atualizar_dashboard(self):
        total_ganhos = sum(i["valor"] for i in self.dados["receitas"])
        total_gastos = sum(sum(item["valor"] for item in d.get("itens", [])) for d in self.dados["despesas"])
        
        total_caixinhas_estimado = 0.0
        total_aportes_mes = 0.0

        for cx in self.dados.get("caixinhas", []):
            din_ini = cx.get("dinheiro_inicial", 0.0)
            ap_men = cx.get("aporte_mensal", 0.0)
            cdi_anual = cx.get("cdi_anual", 10.50)
            
            saldo_est, _ = calcular_rendimento_caixinha(din_ini, ap_men, cdi_anual, dias_investido=30)
            total_caixinhas_estimado += saldo_est
            total_aportes_mes += ap_men

        saldo_disponivel = total_ganhos - total_gastos - total_aportes_mes
        patrimonio_total = saldo_disponivel + total_caixinhas_estimado

        self.card_ganhos.lbl_valor.configure(text=f"R$ {total_ganhos:.2f}")
        self.card_gastos.lbl_valor.configure(text=f"R$ {total_gastos:.2f}")
        self.card_invest.lbl_valor.configure(text=f"R$ {total_caixinhas_estimado:.2f}")
        
        cor_saldo = "#27ae60" if saldo_disponivel >= 0 else "#e74c3c"
        self.card_saldo.configure(border_color=cor_saldo)
        self.card_saldo.lbl_valor.configure(text=f"R$ {saldo_disponivel:.2f}", text_color=cor_saldo)
        self.card_patrimonio.lbl_valor.configure(text=f"R$ {patrimonio_total:.2f}")

    def salvar_e_recarregar(self):
        salvar_dados(self.dados)
        self.lbl_esq_titulo.configure(text=f"Mês: {self.dados.get('mes_atual', 'Atual')}")
        self.atualizar_tabela_categorias()
        self.atualizar_dashboard()

    def janela_exibir_log(self):
        win = ctk.CTkToplevel(self)
        self.configurar_janela_modal(win, "Histórico de Auditoria & Movimentações", 600, 500)

        main_frame = ctk.CTkScrollableFrame(win, fg_color="#1a1a1a")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(main_frame, text="📜 Log de Histórico de Ações", font=ctk.CTkFont(size=16, weight="bold"), text_color="#3aafa9").pack(pady=10)

        logs = self.dados.get("log_movimentacoes", [])
        if not logs:
            ctk.CTkLabel(main_frame, text="Nenhuma movimentação registrada ainda.", text_color="#888888").pack(pady=20)
            return

        for entry in logs:
            lbl = ctk.CTkLabel(main_frame, text=entry, anchor="w", justify="left", font=ctk.CTkFont(size=11), text_color="#cccccc")
            lbl.pack(fill="x", padx=10, pady=2)

    def janela_onboarding_inicial(self):
        win = ctk.CTkToplevel(self)
        self.configurar_janela_modal(win, "Perfil Financeiro Inicial", 520, 720)

        main_frame = ctk.CTkScrollableFrame(win, fg_color="#222222")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(main_frame, text="🚀 Questionário de Perfil Financeiro", font=ctk.CTkFont(size=18, weight="bold"), text_color="#3aafa9").pack(pady=(10, 2))
        ctk.CTkLabel(main_frame, text="O sistema vai criar as categorias exatas para o seu dia a dia.", text_color="#aaaaaa", font=ctk.CTkFont(size=11)).pack(pady=(0, 15))

        ctk.CTkLabel(main_frame, text="💵 Qual é a sua Renda Mensal Líquida (R$)?", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(6, 2))
        e_salario = ctk.CTkEntry(main_frame, placeholder_text="ex: 3500.00", width=440)
        e_salario.pack(padx=20, pady=2)

        ctk.CTkLabel(main_frame, text="🏠 Qual é a sua situação de Moradia?", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(12, 2))
        cb_moradia = ctk.CTkComboBox(main_frame, values=["Aluguel", "Casa Própria (Financiada)", "Casa Própria (Quitada)"], width=440)
        cb_moradia.pack(padx=20, pady=2)

        f_moradia_val = ctk.CTkFrame(main_frame, fg_color="transparent")
        f_moradia_val.pack(padx=20, pady=4, fill="x")
        
        lbl_moradia_val = ctk.CTkLabel(f_moradia_val, text="Valor Mensal do Aluguel (R$):", font=ctk.CTkFont(size=11, weight="bold"))
        lbl_moradia_val.pack(anchor="w")
        e_moradia_val = ctk.CTkEntry(f_moradia_val, placeholder_text="0.00", width=440)
        e_moradia_val.pack(pady=2)

        def atualizar_campo_moradia(choice):
            if choice == "Aluguel":
                f_moradia_val.pack(padx=20, pady=4, fill="x", after=cb_moradia)
                lbl_moradia_val.configure(text="Valor Mensal do Aluguel (R$):")
            elif choice == "Casa Própria (Financiada)":
                f_moradia_val.pack(padx=20, pady=4, fill="x", after=cb_moradia)
                lbl_moradia_val.configure(text="Valor da Parcela do Financiamento Imobiliário (R$):")
            else:
                f_moradia_val.pack_forget()

        cb_moradia.configure(command=atualizar_campo_moradia)

        ctk.CTkLabel(main_frame, text="💳 Possui Cartão de Crédito?", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(12, 2))
        cb_cartao = ctk.CTkComboBox(main_frame, values=["Sim", "Não"], width=440)
        cb_cartao.pack(padx=20, pady=2)

        ctk.CTkLabel(main_frame, text="📦 Tem outros Financiamentos ou Empréstimos?", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(12, 2))
        cb_dividas = ctk.CTkComboBox(main_frame, values=["Não", "Sim"], width=440)
        cb_dividas.pack(padx=20, pady=2)

        ctk.CTkLabel(main_frame, text="⚡ Estimativa Média de Contas Básicas (R$):", font=ctk.CTkFont(size=13, weight="bold"), text_color="#3aafa9").pack(anchor="w", padx=20, pady=(16, 5))

        f_basicos = ctk.CTkFrame(main_frame, fg_color="#1a1a1a", corner_radius=8)
        f_basicos.pack(padx=20, pady=5, fill="x")

        ctk.CTkLabel(f_basicos, text="💧 Água (R$):", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=0, padx=10, pady=(8, 2), sticky="w")
        e_agua = ctk.CTkEntry(f_basicos, placeholder_text="ex: 80.00", width=200)
        e_agua.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="ew")

        ctk.CTkLabel(f_basicos, text="⚡ Luz (R$):", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=1, padx=10, pady=(8, 2), sticky="w")
        e_luz = ctk.CTkEntry(f_basicos, placeholder_text="ex: 200.00", width=200)
        e_luz.grid(row=1, column=1, padx=10, pady=(0, 8), sticky="ew")

        ctk.CTkLabel(f_basicos, text="🌐 Internet (R$):", font=ctk.CTkFont(size=11, weight="bold")).grid(row=2, column=0, padx=10, pady=(4, 2), sticky="w")
        e_net = ctk.CTkEntry(f_basicos, placeholder_text="ex: 90.00", width=200)
        e_net.grid(row=3, column=0, padx=10, pady=(0, 8), sticky="ew")

        ctk.CTkLabel(f_basicos, text="💊 Saúde (R$):", font=ctk.CTkFont(size=11, weight="bold")).grid(row=2, column=1, padx=10, pady=(4, 2), sticky="w")
        e_saude = ctk.CTkEntry(f_basicos, placeholder_text="ex: 150.00", width=200)
        e_saude.grid(row=3, column=1, padx=10, pady=(0, 8), sticky="ew")

        ctk.CTkLabel(f_basicos, text="🛒 Mercado / Compras do Mês (R$):", font=ctk.CTkFont(size=11, weight="bold")).grid(row=4, column=0, columnspan=2, padx=10, pady=(4, 2), sticky="w")
        e_mercado = ctk.CTkEntry(f_basicos, placeholder_text="ex: 1200.00", width=420)
        e_mercado.grid(row=5, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")

        f_basicos.grid_columnconfigure(0, weight=1)
        f_basicos.grid_columnconfigure(1, weight=1)

        def concluir():
            sal_txt = e_salario.get().replace(",", ".").strip() or "0"
            try:
                sal_val = float(sal_txt)
            except ValueError:
                sal_val = 0.0

            if self.dados["receitas"]:
                self.dados["receitas"][0]["valor"] = sal_val
            else:
                self.dados["receitas"] = [{"tipo": "Salário Principal", "fonte": "Empregador", "valor": sal_val}]

            novas_categorias = []

            op_moradia = cb_moradia.get()
            m_val_txt = e_moradia_val.get().replace(",", ".").strip() or "0"
            try:
                val_moradia = float(m_val_txt)
            except ValueError:
                val_moradia = 0.0

            if op_moradia == "Aluguel":
                novas_categorias.append({"categoria": "🏠 Aluguel", "meta": val_moradia, "itens": []})
            elif op_moradia == "Casa Própria (Financiada)":
                novas_categorias.append({"categoria": "📦 Financiamento Imobiliário", "meta": val_moradia, "itens": []})

            def parse_val(e):
                try:
                    return float(e.get().replace(",", ".").strip() or "0")
                except ValueError:
                    return 0.0

            novas_categorias.append({"categoria": "💧 Água", "meta": parse_val(e_agua), "itens": []})
            novas_categorias.append({"categoria": "⚡ Luz", "meta": parse_val(e_luz), "itens": []})
            novas_categorias.append({"categoria": "🌐 Internet", "meta": parse_val(e_net), "itens": []})
            novas_categorias.append({"categoria": "🛒 Compras do Mês", "meta": parse_val(e_mercado), "itens": []})
            novas_categorias.append({"categoria": "💊 Saúde", "meta": parse_val(e_saude), "itens": []})

            if cb_cartao.get() == "Sim":
                novas_categorias.append({"categoria": "💳 Cartão de Crédito", "meta": 0.0, "itens": []})

            if cb_dividas.get() == "Sim":
                novas_categorias.append({"categoria": "📦 Financiamentos / Dívidas", "meta": 0.0, "itens": []})

            self.dados["despesas"] = novas_categorias
            self.dados["configurado"] = True
            registrar_log(self.dados, "Perfil financeiro inicial configurado com sucesso.")
            self.salvar_e_recarregar()
            win.destroy()
            messagebox.showinfo("Sucesso", "Perfil financeiro configurado com sucesso!")

        def pular():
            self.dados["configurado"] = True
            salvar_dados(self.dados)
            win.destroy()

        ctk.CTkButton(main_frame, text="💾 Salvar e Gerar Minhas Categorias", fg_color="#2b7a78", hover_color="#3aafa9", command=concluir).pack(pady=(20, 5), padx=20, fill="x")
        ctk.CTkButton(main_frame, text="Pular por enquanto", fg_color="transparent", text_color="#888888", hover_color="#333333", command=pular).pack(pady=2)

    def exportar_planilha_csv(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile=f"Haacktec_Financeiro_{self.dados.get('mes_atual', '').replace(' / ', '_')}.csv")
        if not filepath: return

        try:
            with open(filepath, mode="w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file, delimiter=";")
                writer.writerow(["Categoria", "Descrição", "Valor (R$)", "Parcelas", "Cartão / Pago via", "Dia Vencimento", "Data Registro", "Status"])
                
                for d in self.dados.get("despesas", []):
                    cat_nome = d["categoria"]
                    for item in d.get("itens", []):
                        status = "Pago" if item_esta_pago(item) else "Pendente"
                        writer.writerow([
                            cat_nome,
                            item.get("desc", ""),
                            f"{item.get('valor', 0.0):.2f}".replace(".", ","),
                            item.get("parcelas", 1),
                            item.get("cartao", "Dinheiro / Pix"),
                            item.get("dia_vencimento", 1),
                            item.get("data_registro", datetime.now().strftime("%d/%m/%Y")),
                            status
                        ])
            registrar_log(self.dados, "Relatório da planilha exportado para CSV.")
            messagebox.showinfo("Sucesso", f"Planilha CSV exportada com sucesso em:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao exportar CSV: {e}")

    def exibir_grafico_gastos(self):
        if not HAS_MATPLOTLIB:
            messagebox.showerror("Erro", "A biblioteca 'matplotlib' não está instalada.\nInstale executando: pip install matplotlib")
            return

        categorias = []
        totais = []

        for d in self.dados.get("despesas", []):
            total_cat = sum(item["valor"] for item in d.get("itens", []))
            if total_cat > 0:
                categorias.append(d["categoria"])
                totais.append(total_cat)

        if not totais:
            messagebox.showinfo("Gráfico de Gastos", "Não há despesas cadastradas no mês atual para exibir no gráfico.")
            return

        fig, ax = plt.subplots(figsize=(7, 6))
        fig.patch.set_facecolor('#1a1a1a')
        ax.set_facecolor('#1a1a1a')

        wedges, texts, autotexts = ax.pie(
            totais, 
            labels=categorias, 
            autopct='%1.1f%%', 
            startangle=140,
            textprops=dict(color="w")
        )

        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_weight('bold')

        ax.set_title(f"Distribuição de Gastos - {self.dados.get('mes_atual', '')}", color="white", fontsize=14, fontweight="bold")
        plt.tight_layout()
        plt.show()

    def fazer_backup_json(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json", 
            filetypes=[("JSON files", "*.json")], 
            initialfile=f"Backup_Haacktec_{datetime.now().strftime('%Y%m%d')}.json"
        )
        if filepath:
            try:
                salvar_dados(self.dados, filepath)
                registrar_log(self.dados, "Backup completo dos dados em formato JSON gerado.")
                messagebox.showinfo("Sucesso", f"Backup salvo com sucesso em:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao exportar backup: {e}")

    def restaurar_backup_json(self):
        filepath = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if filepath:
            try:
                novos_dados = carregar_dados(filepath)
                self.dados = novos_dados
                registrar_log(self.dados, "Base de dados restaurada com sucesso a partir de backup JSON.")
                self.salvar_e_recarregar()
                messagebox.showinfo("Sucesso", "Dados restaurados com sucesso!")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao restaurar arquivo de backup: {e}")

    def janela_adicionar_categoria(self):
        win = ctk.CTkToplevel(self)
        self.configurar_janela_modal(win, "Nova Categoria", 420, 320)

        main_frame = ctk.CTkFrame(win, fg_color="#222222")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(main_frame, text="Escolha o Ícone:", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 2))
        
        cb_icone = ctk.CTkComboBox(main_frame, values=BANCO_ICONES, width=120)
        cb_icone.pack(pady=4)
        cb_icone.set(BANCO_ICONES[0])

        ctk.CTkLabel(main_frame, text="Nome da Nova Categoria:", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 2))
        e_cat = ctk.CTkEntry(main_frame, width=320)
        e_cat.pack(pady=4)

        ctk.CTkLabel(main_frame, text="Meta de Gastos R$ (Opcional):", font=ctk.CTkFont(weight="bold")).pack(pady=(8, 2))
        e_meta = ctk.CTkEntry(main_frame, width=320, placeholder_text="ex: 500.00")
        e_meta.pack(pady=4)

        def salvar():
            nome = e_cat.get().strip()
            meta_txt = e_meta.get().replace(",", ".").strip() or "0"
            if not nome: 
                messagebox.showerror("Erro", "Digite um nome para a categoria!", parent=win)
                return
            try:
                meta_val = float(meta_txt)
            except ValueError:
                meta_val = 0.0

            icone = cb_icone.get()
            nome_completo = f"{icone} {nome}"

            if not any(d["categoria"].lower() == nome_completo.lower() for d in self.dados["despesas"]):
                self.dados["despesas"].append({"categoria": nome_completo, "meta": meta_val, "itens": []})
                registrar_log(self.dados, f"Criada nova categoria '{nome_completo}' com meta de R$ {meta_val:.2f}.")
                self.salvar_e_recarregar()
            win.destroy()

        ctk.CTkButton(main_frame, text="Criar Categoria", fg_color="#2b7a78", hover_color="#3aafa9", command=salvar).pack(pady=20)

    def janela_editar_categoria(self, nome_categoria_direta=None):
        win = ctk.CTkToplevel(self)
        self.configurar_janela_modal(win, "Editar Categoria", 420, 360)

        main_frame = ctk.CTkFrame(win, fg_color="#222222")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(main_frame, text="Selecione a Categoria:", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 2))
        categorias = [d["categoria"] for d in self.dados["despesas"]]
        if not categorias:
            ctk.CTkLabel(main_frame, text="Nenhuma categoria cadastrada.", text_color="#aaaaaa").pack(pady=10)
            return

        cb_cat = ctk.CTkComboBox(main_frame, values=categorias, width=320)
        cb_cat.pack(pady=4)
        
        cat_inicial = nome_categoria_direta if nome_categoria_direta in categorias else categorias[0]
        cb_cat.set(cat_inicial)

        ctk.CTkLabel(main_frame, text="Novo Ícone:", font=ctk.CTkFont(weight="bold")).pack(pady=(8, 2))
        cb_icone = ctk.CTkComboBox(main_frame, values=BANCO_ICONES, width=120)
        cb_icone.pack(pady=4)

        ctk.CTkLabel(main_frame, text="Novo Nome:", font=ctk.CTkFont(weight="bold")).pack(pady=(8, 2))
        e_novo_nome = ctk.CTkEntry(main_frame, width=320)
        e_novo_nome.pack(pady=4)

        ctk.CTkLabel(main_frame, text="Meta de Gastos R$:", font=ctk.CTkFont(weight="bold")).pack(pady=(8, 2))
        e_meta = ctk.CTkEntry(main_frame, width=320)
        e_meta.pack(pady=4)

        def preencher_campos(choice):
            for d in self.dados["despesas"]:
                if d["categoria"] == choice:
                    partes = choice.split(" ", 1)
                    if len(partes) > 1 and partes[0] in BANCO_ICONES:
                        cb_icone.set(partes[0])
                        nome_puro = partes[1]
                    else:
                        cb_icone.set(BANCO_ICONES[0])
                        nome_puro = choice

                    e_novo_nome.delete(0, 'end')
                    e_novo_nome.insert(0, nome_puro)
                    
                    e_meta.delete(0, 'end')
                    e_meta.insert(0, str(d.get('meta', 0.0)))
                    break

        cb_cat.configure(command=preencher_campos)
        preencher_campos(cat_inicial)

        def salvar_edicao():
            cat_antiga = cb_cat.get()
            nome_limpo = e_novo_nome.get().strip()
            meta_txt = e_meta.get().replace(",", ".").strip() or "0"
            icone = cb_icone.get()
            if not nome_limpo: return
            try:
                meta_val = float(meta_txt)
            except ValueError:
                meta_val = 0.0

            nova_cat_completa = f"{icone} {nome_limpo}"

            for d in self.dados["despesas"]:
                if d["categoria"] == cat_antiga:
                    d["categoria"] = nova_cat_completa
                    d["meta"] = meta_val
                    break
            
            registrar_log(self.dados, f"Alterada categoria '{cat_antiga}' para '{nova_cat_completa}' com meta de R$ {meta_val:.2f}.")
            self.salvar_e_recarregar()
            win.destroy()

        ctk.CTkButton(main_frame, text="Salvar Alterações", fg_color="#2980b9", hover_color="#3498db", command=salvar_edicao).pack(pady=20)

    def janela_detalhes_categoria(self, nome_cat):
        cat_data = next((d for d in self.dados["despesas"] if d["categoria"] == nome_cat), None)
        if not cat_data: return

        win = ctk.CTkToplevel(self)
        self.configurar_janela_modal(win, f"Itens de: {nome_cat}", 960, 720)

        scroll_win = ctk.CTkScrollableFrame(win, fg_color="#1a1a1a")
        scroll_win.pack(fill="both", expand=True, padx=5, pady=5)

        lbl_tit = ctk.CTkLabel(scroll_win, text=f"Gerenciar Itens - {nome_cat}", font=ctk.CTkFont(size=15, weight="bold"))
        lbl_tit.pack(pady=(10, 2))

        search_frame = ctk.CTkFrame(scroll_win, fg_color="transparent")
        search_frame.pack(fill="x", padx=10, pady=5)
        
        e_busca = ctk.CTkEntry(search_frame, placeholder_text="🔍 Filtrar itens por nome...", width=300)
        e_busca.pack(side="left", padx=5)

        scroll_itens = ctk.CTkScrollableFrame(scroll_win, width=900, height=220, fg_color="#222222")
        scroll_itens.pack(padx=10, pady=5, fill="both", expand=True)

        lista_cartoes = self.dados.get("cartoes", CARTOES_PADRAO)

        def carregar_lista_itens(filtro=""):
            for w in scroll_itens.winfo_children():
                w.destroy()
            
            if not cat_data.get("itens"):
                ctk.CTkLabel(scroll_itens, text="Nenhum item cadastrado nesta categoria.", text_color="#888888").pack(pady=20)
                return

            for idx, item in enumerate(cat_data["itens"]):
                if filtro and filtro.lower() not in item["desc"].lower():
                    continue

                pago = item_esta_pago(item)
                atrasado = item_esta_atrasado(item)
                
                if atrasado:
                    cor_fundo = "#3b1a1a"
                elif pago:
                    cor_fundo = "#1e3a2f"
                else:
                    cor_fundo = "#2a2a2a"
                
                row_i = ctk.CTkFrame(scroll_itens, fg_color=cor_fundo, height=38)
                row_i.pack(fill="x", pady=2, padx=5)

                def alternar_pago(i=idx):
                    item_ref = cat_data["itens"][i]
                    novo_status = not item_esta_pago(item_ref)
                    item_ref["pago"] = novo_status
                    st_txt = "PAGO" if novo_status else "PENDENTE"
                    registrar_log(self.dados, f"Alterado status do item '{item_ref['desc']}' ({nome_cat}) para {st_txt}.")
                    self.salvar_e_recarregar()
                    carregar_lista_itens(e_busca.get().strip())

                chk_var = ctk.BooleanVar(value=pago)
                chk_pago = ctk.CTkCheckBox(row_i, text="", variable=chk_var, width=20, command=alternar_pago)
                chk_pago.pack(side="left", padx=5)
                
                ctk.CTkLabel(row_i, text=item["desc"], anchor="w", width=120).pack(side="left", padx=5)
                ctk.CTkLabel(row_i, text=f"R$ {item['valor']:.2f}", anchor="e", width=70, text_color="#ffcccc").pack(side="left", padx=2)
                
                cartao_nome = item.get("cartao", "Dinheiro / Pix")
                ctk.CTkLabel(row_i, text=cartao_nome, anchor="center", width=100, text_color="#85e3ff", font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=2)

                parc_txt = f"{item.get('parcelas', 1)}x" if item.get('parcelas', 1) > 1 else "À vista"
                ctk.CTkLabel(row_i, text=parc_txt, anchor="center", width=45, text_color="#3aafa9").pack(side="left", padx=2)
                
                venc_txt = f"Venc: Dia {item.get('dia_vencimento', 1)}"
                ctk.CTkLabel(row_i, text=venc_txt, anchor="center", width=75, text_color="#aaaaaa", font=ctk.CTkFont(size=10)).pack(side="left", padx=2)
                
                if atrasado:
                    status_txt = "⚠️ Atrasado"
                    status_cor = "#ff5555"
                elif pago:
                    status_txt = "✅ Pago"
                    status_cor = "#2ecc71"
                else:
                    status_txt = "⏳ Pendente"
                    status_cor = "#f39c12"

                ctk.CTkLabel(row_i, text=status_txt, anchor="center", width=70, text_color=status_cor, font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=2)

                dt_reg_txt = item.get("data_registro", datetime.now().strftime("%d/%m/%Y"))
                lbl_dt_reg = ctk.CTkLabel(row_i, text=f"Criado: {dt_reg_txt}", anchor="center", width=95, text_color="#3a86ff", font=ctk.CTkFont(size=10, weight="bold"))
                lbl_dt_reg.pack(side="left", padx=5)

                btn_del_item = ctk.CTkButton(row_i, text="❌", width=30, fg_color="#c0392b", hover_color="#e74c3c",
                                             command=lambda i=idx: remover_item(i))
                btn_del_item.pack(side="right", padx=5)

                btn_edit_item = ctk.CTkButton(row_i, text="✏️", width=30, fg_color="#2980b9", hover_color="#3498db",
                                              command=lambda i=idx: abrir_janela_edicao(i))
                btn_edit_item.pack(side="right", padx=2)

        def ao_digitar_busca(event):
            carregar_lista_itens(e_busca.get().strip())

        e_busca.bind("<KeyRelease>", ao_digitar_busca)

        def remover_item(idx):
            item_alvo = cat_data["itens"][idx]
            if messagebox.askyesno("Confirmar Exclusão", f"Tem certeza que deseja excluir o item '{item_alvo['desc']}' no valor de R$ {item_alvo['valor']:.2f}?", parent=win):
                cat_data["itens"].pop(idx)
                registrar_log(self.dados, f"Excluído o item '{item_alvo['desc']}' (R$ {item_alvo['valor']:.2f}) da categoria '{nome_cat}'.")
                self.salvar_e_recarregar()
                carregar_lista_itens(e_busca.get().strip())

        def abrir_janela_edicao(idx):
            item = cat_data["itens"][idx]
            
            edit_win = ctk.CTkToplevel(win)
            self.configurar_janela_modal(edit_win, "Editar Item", 380, 480)

            edit_frame = ctk.CTkFrame(edit_win, fg_color="#222222")
            edit_frame.pack(fill="both", expand=True, padx=10, pady=10)

            ctk.CTkLabel(edit_frame, text="Editar Descrição:", font=ctk.CTkFont(weight="bold")).pack(pady=(8, 2))
            e_ed_desc = ctk.CTkEntry(edit_frame, width=280)
            e_ed_desc.pack(pady=2)
            e_ed_desc.insert(0, item["desc"])

            ctk.CTkLabel(edit_frame, text="Editar Valor (R$):", font=ctk.CTkFont(weight="bold")).pack(pady=(8, 2))
            e_ed_val = ctk.CTkEntry(edit_frame, width=280)
            e_ed_val.pack(pady=2)
            e_ed_val.insert(0, str(item["valor"]))

            ctk.CTkLabel(edit_frame, text="Cartão / Forma de Pagamento:", font=ctk.CTkFont(weight="bold")).pack(pady=(8, 2))
            cb_ed_cartao = ctk.CTkComboBox(edit_frame, values=lista_cartoes, width=280)
            cb_ed_cartao.pack(pady=2)
            cb_ed_cartao.set(item.get("cartao", lista_cartoes[0]))

            ctk.CTkLabel(edit_frame, text="Número de Parcelas:", font=ctk.CTkFont(weight="bold")).pack(pady=(8, 2))
            e_ed_parc = ctk.CTkEntry(edit_frame, width=280)
            e_ed_parc.pack(pady=2)
            e_ed_parc.insert(0, str(item.get("parcelas", 1)))

            ctk.CTkLabel(edit_frame, text="Dia de Vencimento (1 a 31):", font=ctk.CTkFont(weight="bold")).pack(pady=(8, 2))
            e_ed_venc = ctk.CTkEntry(edit_frame, width=280)
            e_ed_venc.pack(pady=2)
            e_ed_venc.insert(0, str(item.get("dia_vencimento", 1)))

            dt_criacao = item.get("data_registro", datetime.now().strftime("%d/%m/%Y"))
            ctk.CTkLabel(edit_frame, text=f"Data de Registro: {dt_criacao}", font=ctk.CTkFont(size=11), text_color="#3a86ff").pack(pady=(8, 2))

            def salvar_edicao():
                try:
                    novo_desc = e_ed_desc.get().strip()
                    novo_val = float(e_ed_val.get().replace(",", "."))
                    novo_cartao = cb_ed_cartao.get().strip()
                    parc_txt = e_ed_parc.get().strip()
                    venc_txt = e_ed_venc.get().strip()
                    
                    if not parc_txt.isdigit() or not venc_txt.isdigit():
                        messagebox.showerror("Erro", "Parcelas e Dia de Vencimento devem conter apenas números inteiros!", parent=edit_win)
                        return
                    
                    nova_parc = int(parc_txt)
                    novo_venc = int(venc_txt)
                    
                    if not (1 <= novo_venc <= 31):
                        messagebox.showerror("Erro", "O dia de vencimento deve estar entre 1 e 31!", parent=edit_win)
                        return
                    
                    cat_data["itens"][idx] = {
                        "desc": novo_desc,
                        "valor": novo_val,
                        "cartao": novo_cartao,
                        "parcelas": nova_parc,
                        "dia_vencimento": novo_venc,
                        "data_registro": dt_criacao,
                        "pago": item.get("pago", False)
                    }
                    registrar_log(self.dados, f"Item '{novo_desc}' (R$ {novo_val:.2f}) editado na categoria '{nome_cat}'.")
                    self.salvar_e_recarregar()
                    carregar_lista_itens(e_busca.get().strip())
                    edit_win.destroy()
                except ValueError:
                    messagebox.showerror("Erro", "Verifique se o valor monetário inserido é válido.", parent=edit_win)

            ctk.CTkButton(edit_frame, text="Salvar Alterações", fg_color="#2b7a78", command=salvar_edicao).pack(pady=15)

        carregar_lista_itens()

        # FORMULÁRIO DE INSERÇÃO COM RÓTULOS CLAROS IDENTIFICANDO CADA CAMPO NUMÉRICO
        form_container = ctk.CTkFrame(scroll_win, fg_color="#222222", corner_radius=8)
        form_container.pack(pady=10, fill="x", padx=10)

        labels_frame = ctk.CTkFrame(form_container, fg_color="transparent")
        labels_frame.pack(fill="x", padx=5, pady=(5, 0))
        
        ctk.CTkLabel(labels_frame, text="Descrição", font=ctk.CTkFont(size=10, weight="bold"), text_color="#aaaaaa", width=140, anchor="w").pack(side="left", padx=2)
        ctk.CTkLabel(labels_frame, text="Valor (R$)", font=ctk.CTkFont(size=10, weight="bold"), text_color="#aaaaaa", width=80, anchor="w").pack(side="left", padx=2)
        ctk.CTkLabel(labels_frame, text="Forma de Pagto", font=ctk.CTkFont(size=10, weight="bold"), text_color="#aaaaaa", width=130, anchor="w").pack(side="left", padx=2)
        ctk.CTkLabel(labels_frame, text="📦 Qtd Parcelas", font=ctk.CTkFont(size=10, weight="bold"), text_color="#3aafa9", width=95, anchor="w").pack(side="left", padx=2)
        ctk.CTkLabel(labels_frame, text="📅 Dia Vencimento", font=ctk.CTkFont(size=10, weight="bold"), text_color="#3aafa9", width=95, anchor="w").pack(side="left", padx=2)

        inputs_frame = ctk.CTkFrame(form_container, fg_color="transparent")
        inputs_frame.pack(fill="x", padx=5, pady=(0, 8))

        e_desc = ctk.CTkEntry(inputs_frame, placeholder_text="Ex: Notebook", width=140)
        e_desc.pack(side="left", padx=2)

        e_val = ctk.CTkEntry(inputs_frame, placeholder_text="0.00", width=80)
        e_val.pack(side="left", padx=2)

        cb_cartao = ctk.CTkComboBox(inputs_frame, values=lista_cartoes, width=130)
        cb_cartao.pack(side="left", padx=2)
        cb_cartao.set(lista_cartoes[0])

        def validar_apenas_digitos(P):
            if P == "" or P.isdigit():
                return True
            return False

        vcmd = (win.register(validar_apenas_digitos), '%P')
        
        e_parc = ctk.CTkEntry(inputs_frame, placeholder_text="Ex: 12", width=95, validate="key", validatecommand=vcmd)
        e_parc.pack(side="left", padx=2)
        e_parc.insert(0, "1")

        e_venc = ctk.CTkEntry(inputs_frame, placeholder_text="Ex: 10", width=95, validate="key", validatecommand=vcmd)
        e_venc.pack(side="left", padx=2)
        e_venc.insert(0, "10")

        def adicionar_item_action():
            desc = e_desc.get().strip()
            val_txt = e_val.get().replace(",", ".").strip()
            cartao = cb_cartao.get().strip()
            parc_txt = e_parc.get().strip()
            venc_txt = e_venc.get().strip()

            if not desc:
                messagebox.showerror("Erro de Preenchimento", "Informe a descrição do item!", parent=win)
                return

            try:
                val = float(val_txt)
                if val <= 0:
                    messagebox.showerror("Erro de Valor", "O valor deve ser maior que zero!", parent=win)
                    return
            except ValueError:
                messagebox.showerror("Erro de Valor", "Digite um valor numérico válido (ex: 45.90)!", parent=win)
                return

            if not parc_txt.isdigit() or not venc_txt.isdigit():
                messagebox.showerror("Erro de Formato", "Parcelas e Vencimento aceitam apenas números inteiros!", parent=win)
                return

            parc = int(parc_txt)
            venc = int(venc_txt)

            if not (1 <= venc <= 31):
                messagebox.showerror("Erro de Vencimento", "O dia de vencimento deve estar entre 1 e 31!", parent=win)
                return

            data_hoje = datetime.now().strftime("%d/%m/%Y")

            cat_data["itens"].append({
                "desc": desc, 
                "valor": val, 
                "cartao": cartao, 
                "parcelas": parc, 
                "dia_vencimento": venc, 
                "data_registro": data_hoje,
                "pago": False
            })
            
            registrar_log(self.dados, f"Adicionado item '{desc}' (R$ {val:.2f}) na categoria '{nome_cat}'.")
            self.salvar_e_recarregar()
            
            e_desc.delete(0, 'end')
            e_val.delete(0, 'end')
            e_parc.delete(0, 'end')
            e_parc.insert(0, "1")
            e_venc.delete(0, 'end')
            e_venc.insert(0, "10")
            carregar_lista_itens(e_busca.get().strip())

        btn_add_item = ctk.CTkButton(inputs_frame, text="➕", width=40, fg_color="#2b7a78", command=adicionar_item_action)
        btn_add_item.pack(side="right", padx=2)

    def janela_gerenciar_caixinhas(self):
        win = ctk.CTkToplevel(self)
        self.configurar_janela_modal(win, "Gerenciar Caixinhas Personalizadas", 560, 580)

        scroll_win = ctk.CTkScrollableFrame(win, fg_color="#1a1a1a")
        scroll_win.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(scroll_win, text="📦 Caixinhas de Investimento e Reservas", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=10)

        scroll_lista = ctk.CTkScrollableFrame(scroll_win, width=500, height=220, fg_color="#222222")
        scroll_lista.pack(padx=10, pady=5, fill="both", expand=True)

        def carregar_lista_caixinhas():
            for w in scroll_lista.winfo_children():
                w.destroy()
            
            caixinhas = self.dados.get("caixinhas", [])
            if not caixinhas:
                ctk.CTkLabel(scroll_lista, text="Nenhuma caixinha cadastrada.", text_color="#888888").pack(pady=20)
                return

            for idx, cx in enumerate(caixinhas):
                row_c = ctk.CTkFrame(scroll_lista, fg_color="#2a2a2a", height=50)
                row_c.pack(fill="x", pady=3, padx=5)
                
                din_ini = cx.get("dinheiro_inicial", 0.0)
                ap_men = cx.get("aporte_mensal", 0.0)
                cdi_anual = cx.get("cdi_anual", 10.50)
                
                total_atual, _ = calcular_rendimento_caixinha(din_ini, ap_men, cdi_anual, dias_investido=30)
                
                info_txt = f"{cx['nome']}\nSaldo Est. Líquido: R$ {total_atual:.2f} (Aporte Mensal: R$ {ap_men:.2f})"
                ctk.CTkLabel(row_c, text=info_txt, anchor="w", justify="left", font=ctk.CTkFont(size=11)).pack(side="left", padx=10)
                
                btn_del_cx = ctk.CTkButton(row_c, text="🗑️", width=35, fg_color="#c0392b", hover_color="#e74c3c",
                                           command=lambda i=idx: remover_caixinha(i))
                btn_del_cx.pack(side="right", padx=5)

        def remover_caixinha(idx):
            if len(self.dados.get("caixinhas", [])) <= 1:
                messagebox.showwarning("Aviso", "Mantenha ao menos uma caixinha cadastrada.", parent=win)
                return
            cx_alvo = self.dados["caixinhas"][idx]
            if messagebox.askyesno("Confirmar Exclusão", f"Deseja realmente remover a caixinha '{cx_alvo['nome']}'?", parent=win):
                self.dados["caixinhas"].pop(idx)
                registrar_log(self.dados, f"Excluída caixinha '{cx_alvo['nome']}'.")
                self.salvar_e_recarregar()
                carregar_lista_caixinhas()

        carregar_lista_caixinhas()

        form_frame = ctk.CTkFrame(scroll_win, fg_color="#222222", corner_radius=6)
        form_frame.pack(pady=10, fill="x", padx=10)

        ctk.CTkLabel(form_frame, text="➕ Criar Nova Caixinha Personalizada", font=ctk.CTkFont(weight="bold"), text_color="#3aafa9").pack(pady=(8, 4))

        e_nome = ctk.CTkEntry(form_frame, placeholder_text="Nome da Caixinha (ex: Reserva Ferramentas)", width=350)
        e_nome.pack(pady=4)

        e_din = ctk.CTkEntry(form_frame, placeholder_text="Valor Inicial Acumulado (R$)", width=350)
        e_din.pack(pady=4)

        e_ap = ctk.CTkEntry(form_frame, placeholder_text="Aporte Mensal Previsto (R$)", width=350)
        e_ap.pack(pady=4)

        e_cdi = ctk.CTkEntry(form_frame, placeholder_text="CDI Anual % (ex: 10.50)", width=350)
        e_cdi.pack(pady=4)
        e_cdi.insert(0, "10.50")

        def adicionar_caixinha_action():
            try:
                nome = e_nome.get().strip()
                din = float(e_din.get().replace(",", ".").strip() or 0.0)
                ap = float(e_ap.get().replace(",", ".").strip() or 0.0)
                cdi = float(e_cdi.get().replace(",", ".").strip() or 10.50)
                
                if not nome:
                    messagebox.showerror("Erro", "Dê um nome para a caixinha!", parent=win)
                    return

                self.dados.setdefault("caixinhas", []).append({
                    "nome": nome,
                    "dinheiro_inicial": din,
                    "aporte_mensal": ap,
                    "cdi_anual": cdi
                })
                registrar_log(self.dados, f"Criada nova caixinha '{nome}' (Aporte: R$ {ap:.2f}).")
                self.salvar_e_recarregar()
                
                e_nome.delete(0, 'end')
                e_din.delete(0, 'end')
                e_ap.delete(0, 'end')
                carregar_lista_caixinhas()
            except ValueError:
                messagebox.showerror("Erro", "Verifique se os campos numéricos estão corretos.", parent=win)

        ctk.CTkButton(form_frame, text="Adicionar Caixinha", fg_color="#8e44ad", hover_color="#9b59b6", command=adicionar_caixinha_action).pack(pady=10)

    def janela_gerenciar_ganhos(self):
        win = ctk.CTkToplevel(self)
        self.configurar_janela_modal(win, "Gerenciar Ganhos e Fontes de Renda", 540, 520)

        scroll_win = ctk.CTkScrollableFrame(win, fg_color="#1a1a1a")
        scroll_win.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(scroll_win, text="Fontes de Ganhos Registradas", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=10)

        scroll_lista = ctk.CTkScrollableFrame(scroll_win, width=480, height=200, fg_color="#222222")
        scroll_lista.pack(padx=10, pady=5, fill="both", expand=True)

        def carregar_lista_ganhos():
            for w in scroll_lista.winfo_children():
                w.destroy()
            
            receitas = self.dados.get("receitas", [])
            if not receitas:
                ctk.CTkLabel(scroll_lista, text="Nenhum ganho cadastrado.", text_color="#888888").pack(pady=20)
                return

            for idx, rec in enumerate(receitas):
                row_g = ctk.CTkFrame(scroll_lista, fg_color="#2a2a2a", height=38)
                row_g.pack(fill="x", pady=2, padx=5)
                
                txt_detalhe = f"{rec.get('tipo', 'Salário')} (Fonte: {rec.get('fonte', 'Geral')})"
                ctk.CTkLabel(row_g, text=txt_detalhe, anchor="w", width=240).pack(side="left", padx=10)
                ctk.CTkLabel(row_g, text=f"R$ {rec['valor']:.2f}", anchor="e", width=100, text_color="#85e3ff").pack(side="left", padx=5)
                
                btn_del_rec = ctk.CTkButton(row_g, text="🗑️", width=35, fg_color="#c0392b", hover_color="#e74c3c",
                                            command=lambda i=idx: remover_ganho(i))
                btn_del_rec.pack(side="right", padx=5)

        def remover_ganho(idx):
            if len(self.dados.get("receitas", [])) <= 1:
                messagebox.showwarning("Aviso", "É recomendado manter ao menos uma fonte de ganho cadastrada.", parent=win)
                return
            rec_alvo = self.dados["receitas"][idx]
            if messagebox.askyesno("Confirmar Exclusão", f"Excluir a fonte de renda '{rec_alvo['tipo']}' (R$ {rec_alvo['valor']:.2f})?", parent=win):
                self.dados["receitas"].pop(idx)
                registrar_log(self.dados, f"Excluída receita '{rec_alvo['tipo']}' (R$ {rec_alvo['valor']:.2f}).")
                self.salvar_e_recarregar()
                carregar_lista_ganhos()

        carregar_lista_ganhos()

        form_frame = ctk.CTkFrame(scroll_win, fg_color="#222222", corner_radius=6)
        form_frame.pack(pady=10, fill="x", padx=10)

        ctk.CTkLabel(form_frame, text="Adicionar Novo Ganho / Salário", font=ctk.CTkFont(weight="bold"), text_color="#3aafa9").pack(pady=(8, 4))

        e_tipo = ctk.CTkEntry(form_frame, placeholder_text="Tipo (ex: Salário Tiago, Renda Extra)", width=320)
        e_tipo.pack(pady=4)

        e_fonte = ctk.CTkEntry(form_frame, placeholder_text="Fonte Pagadora (ex: Empresa X, Cliente)", width=320)
        e_fonte.pack(pady=4)

        e_val = ctk.CTkEntry(form_frame, placeholder_text="Valor (ex: 5000.00)", width=320)
        e_val.pack(pady=4)

        def adicionar_ganho_action():
            try:
                tipo = e_tipo.get().strip()
                fonte = e_fonte.get().strip()
                val_txt = e_val.get().replace(",", ".").strip()
                
                if not tipo or not fonte or not val_txt:
                    messagebox.showerror("Erro", "Preencha todos os campos do ganho!", parent=win)
                    return
                
                val = float(val_txt)
                if val < 0: return

                self.dados.setdefault("receitas", []).append({"tipo": tipo, "fonte": fonte, "valor": val})
                registrar_log(self.dados, f"Adicionada nova receita '{tipo}' no valor de R$ {val:.2f}.")
                self.salvar_e_recarregar()
                
                e_tipo.delete(0, 'end')
                e_fonte.delete(0, 'end')
                e_val.delete(0, 'end')
                carregar_lista_ganhos()
            except ValueError:
                messagebox.showerror("Erro", "Verifique se o valor numérico está correto.", parent=win)

        ctk.CTkButton(form_frame, text="➕ Adicionar Ganho", fg_color="#2b7a78", hover_color="#3aafa9", command=adicionar_ganho_action).pack(pady=10)

    def janela_historico(self):
        win = ctk.CTkToplevel(self)
        self.configurar_janela_modal(win, "Histórico de Meses Anteriores", 600, 500)

        scroll_win = ctk.CTkScrollableFrame(win, fg_color="#1a1a1a")
        scroll_win.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(scroll_win, text="Meses Salvos no Histórico", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        historico = self.dados.get("historico", {})
        if not historico:
            ctk.CTkLabel(scroll_win, text="Nenhum mês anterior registrado ainda.", text_color="#888888").pack(pady=20)
            return

        for mes, dados_mes in historico.items():
            card_m = ctk.CTkFrame(scroll_win, fg_color="#262626", corner_radius=6)
            card_m.pack(fill="x", padx=15, pady=5)
            
            tot_g = sum(i["valor"] for i in dados_mes.get("receitas", []))
            tot_d = sum(sum(item["valor"] for item in d.get("itens", [])) for d in dados_mes.get("despesas", []))
            
            ctk.CTkLabel(card_m, text=f"📅 {mes}", font=ctk.CTkFont(weight="bold"), text_color="#3aafa9").pack(anchor="w", padx=10, pady=(8, 2))
            ctk.CTkLabel(card_m, text=f"Ganhos: R$ {tot_g:.2f} | Gastos: R$ {tot_d:.2f} | Saldo: R$ {tot_g - tot_d:.2f}", text_color="#cccccc").pack(anchor="w", padx=10, pady=(0, 4))
            
            btn_det_hist = ctk.CTkButton(card_m, text="🔍 Ver Detalhes e Exportar PDF", fg_color="#2b7a78", hover_color="#3aafa9", height=28,
                                         command=lambda m=mes, dm=dados_mes: self.janela_detalhes_historico_mes(m, dm))
            btn_det_hist.pack(anchor="e", padx=10, pady=(2, 8))

    def janela_detalhes_historico_mes(self, mes_nome, dados_mes):
        win = ctk.CTkToplevel(self)
        self.configurar_janela_modal(win, f"Detalhes do Mês: {mes_nome}", 640, 600)

        scroll_win = ctk.CTkScrollableFrame(win, fg_color="#1a1a1a")
        scroll_win.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(scroll_win, text=f"Relatório Detalhado - {mes_nome}", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        tot_g = sum(i["valor"] for i in dados_mes.get("receitas", []))
        tot_d = sum(sum(item["valor"] for item in d.get("itens", [])) for d in dados_mes.get("despesas", []))
        saldo = tot_g - tot_d

        res_frame = ctk.CTkFrame(scroll_win, fg_color="#222222")
        res_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(res_frame, text=f"Renda: R$ {tot_g:.2f} | Gastos: R$ {tot_d:.2f} | Saldo: R$ {saldo:.2f}", font=ctk.CTkFont(weight="bold")).pack(pady=8, padx=10)

        scroll_cats = ctk.CTkScrollableFrame(scroll_win, width=580, height=320, fg_color="#222222")
        scroll_cats.pack(padx=15, pady=10, fill="both", expand=True)

        for d in dados_mes.get("despesas", []):
            cat_tot = sum(i["valor"] for i in d.get("itens", []))
            cat_lbl = ctk.CTkLabel(scroll_cats, text=f"{d['categoria']} (Total: R$ {cat_tot:.2f})", font=ctk.CTkFont(weight="bold"), text_color="#3aafa9")
            cat_lbl.pack(anchor="w", padx=5, pady=(8, 2))
            
            for item in d.get("itens", []):
                parc_txt = f"({item.get('parcelas', 1)}x)" if item.get('parcelas', 1) > 1 else "(À vista)"
                cartao_txt = f"[{item.get('cartao', 'Dinheiro / Pix')}]"
                dt_txt = f"({item.get('data_registro', '')})" if item.get('data_registro') else ""
                item_lbl = ctk.CTkLabel(scroll_cats, text=f"   • {item['desc']} {cartao_txt}: R$ {item['valor']:.2f} {parc_txt} {dt_txt}", text_color="#cccccc")
                item_lbl.pack(anchor="w", padx=15, pady=1)

        def exportar_pdf_historico_action():
            if not HAS_REPORTLAB:
                messagebox.showerror("Erro", "A biblioteca reportlab não está instalada.")
                return
            
            filepath = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")], initialfile=f"Relatorio_{mes_nome.replace(' / ', '_')}.pdf")
            if not filepath: return
            
            try:
                doc = SimpleDocTemplate(filepath, pagesize=letter)
                elements = []
                styles = getSampleStyleSheet()
                title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#2b7a78'), spaceAfter=10)
                
                elements.append(Paragraph(f"Haacktec - Relatório do Mês: {mes_nome}", title_style))
                elements.append(Spacer(1, 10))
                
                resumo_data = [
                    ["Resumo do Período", "Valor (R$)"],
                    ["Ganhos Totais", f"R$ {tot_g:.2f}"],
                    ["Gastos Totais", f"R$ {tot_d:.2f}"],
                    ["Saldo Líquido", f"R$ {saldo:.2f}"]
                ]
                
                t_res = Table(resumo_data, colWidths=[300, 150])
                t_res.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3a86ff')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ]))
                
                elements.append(t_res)
                elements.append(Spacer(1, 15))
                elements.append(Paragraph("Detalhamento por Categoria e Itens", styles['Heading2']))
                elements.append(Spacer(1, 8))
                
                detalhe_data = [["Categoria / Item", "Cartão", "Parcelas", "Data Criado", "Valor (R$)"]]
                for d in dados_mes.get("despesas", []):
                    detalhe_data.append([d['categoria'], "", "", "", ""])
                    for item in d.get('itens', []):
                        p_txt = f"{item.get('parcelas', 1)}x" if item.get('parcelas', 1) > 1 else "À vista"
                        dt_reg = item.get('data_registro', '-')
                        detalhe_data.append([f"   • {item['desc']}", item.get('cartao', 'Dinheiro / Pix'), p_txt, dt_reg, f"R$ {item['valor']:.2f}"])
                        
                t_det = Table(detalhe_data, colWidths=[180, 110, 60, 70, 70])
                t_det.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2b7a78')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('ALIGN', (4, 0), (4, -1), 'RIGHT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ]))
                
                elements.append(t_det)
                doc.build(elements)
                messagebox.showinfo("Sucesso", f"Relatório salvo com sucesso em:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao gerar PDF: {e}")

        btn_pdf_hist = ctk.CTkButton(scroll_win, text="📄 Salvar Relatório deste Mês em PDF", fg_color="#2b7a78", hover_color="#3aafa9", command=exportar_pdf_historico_action)
        btn_pdf_hist.pack(pady=10, padx=20, fill="x")

    def janela_simulador_futuro(self):
        win = ctk.CTkToplevel(self)
        self.configurar_janela_modal(win, "Simulador de Meses Futuros", 640, 650)

        scroll_win = ctk.CTkScrollableFrame(win, fg_color="#1a1a1a")
        scroll_win.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(scroll_win, text="🔮 Projeção de Meses Futuros (Com Caixinhas CDI)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        ctk.CTkLabel(scroll_win, text="Calcula com base na média dos seus gastos recorrentes e parcelamentos ativos:", text_color="#aaaaaa", font=ctk.CTkFont(size=11)).pack(pady=(0, 10))

        historico = self.dados.get("historico", {})
        somas_historico_casa = []
        for mes, dados_mes in historico.items():
            total_mes_casa = sum(sum(i["valor"] for i in d.get("itens", [])) for d in dados_mes.get("despesas", []))
            if total_mes_casa > 0:
                somas_historico_casa.append(total_mes_casa)

        total_atual_casa = sum(sum(i["valor"] for i in d.get("itens", [])) for d in self.dados.get("despesas", []))
        if total_atual_casa > 0:
            somas_historico_casa.append(total_atual_casa)

        if somas_historico_casa:
            media_despesas_casa = sum(somas_historico_casa) / len(somas_historico_casa)
        else:
            media_despesas_casa = total_atual_casa

        cfg_frame = ctk.CTkFrame(scroll_win, fg_color="#222222")
        cfg_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(cfg_frame, text=f"Média de Gastos Mensais: R$ {media_despesas_casa:.2f}", text_color="#3aafa9", font=ctk.CTkFont(weight="bold")).pack(pady=8, padx=10)

        scroll_proj = ctk.CTkScrollableFrame(scroll_win, width=580, height=340, fg_color="#222222")
        scroll_proj.pack(padx=15, pady=10, fill="both", expand=True)

        despesas_simulacao = copy.deepcopy(self.dados.get("despesas", []))
        salario_atual = sum(i["valor"] for i in self.dados.get("receitas", []))
        caixinhas_sim = copy.deepcopy(self.dados.get("caixinhas", []))
        meses_lista_pt = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        
        try:
            mes_atual_str = self.dados.get("mes_atual", "Janeiro / 2026")
            partes = mes_atual_str.split("/")
            nome_mes_atual = partes[0].strip()
            ano_atual = int(partes[1].strip())
            idx_mes_base = meses_lista_pt.index(nome_mes_atual)
        except Exception:
            idx_mes_base = datetime.now().month - 1
            ano_atual = datetime.now().year

        for m_offset in range(1, 7):
            idx_futuro = (idx_mes_base + m_offset) % 12
            ano_futuro = ano_atual + ((idx_mes_base + m_offset) // 12)
            nome_mes_futuro = f"{meses_lista_pt[idx_futuro]} / {ano_futuro}"

            total_caixinhas_sim_mes = 0.0
            total_aporte_mensal_sim = 0.0
            
            for cx in caixinhas_sim:
                din_ini = cx.get("dinheiro_inicial", 0.0)
                ap_men = cx.get("aporte_mensal", 0.0)
                cdi_anual = cx.get("cdi_anual", 10.50)
                
                novo_total_cx, _ = calcular_rendimento_caixinha(din_ini, ap_men, cdi_anual, dias_investido=30 * m_offset)
                
                cx["dinheiro_inicial"] = novo_total_cx
                total_caixinhas_sim_mes += novo_total_cx
                total_aporte_mensal_sim += ap_men

            total_parcelas_mes = 0
            novas_despesas_simulacao = []
            
            for d in despesas_simulacao:
                novos_itens_sim = []
                for item in d.get("itens", []):
                    parcelas = item.get("parcelas", 1)
                    if parcelas > 0:
                        total_parcelas_mes += item["valor"]
                        if parcelas > 1:
                            novo_item = copy.deepcopy(item)
                            novo_item["parcelas"] = parcelas - 1
                            novos_itens_sim.append(novo_item)
                novas_despesas_simulacao.append({"categoria": d["categoria"], "meta": d.get("meta", 0.0), "itens": novos_itens_sim})
            
            despesas_simulacao = novas_despesas_simulacao
            total_gastos_projetados = media_despesas_casa + total_parcelas_mes
            saldo_projetado = salario_atual - total_gastos_projetados - total_aporte_mensal_sim

            card_s = ctk.CTkFrame(scroll_proj, fg_color="#2a2a2a", corner_radius=6)
            card_s.pack(fill="x", padx=10, pady=5)
            
            ctk.CTkLabel(card_s, text=f"📅 {nome_mes_futuro}", font=ctk.CTkFont(weight="bold"), text_color="#3aafa9").pack(anchor="w", padx=10, pady=(6, 2))
            ctk.CTkLabel(card_s, text=f"Salário: R$ {salario_atual:.2f} | Gastos Projetados: R$ {total_gastos_projetados:.2f} | Aportes: R$ {total_aporte_mensal_sim:.2f}", text_color="#cccccc", font=ctk.CTkFont(size=10)).pack(anchor="w", padx=10, pady=(0, 2))
            ctk.CTkLabel(card_s, text=f"Total Caixinhas Acumulado (CDI Líquido Est.): R$ {total_caixinhas_sim_mes:.2f}", text_color="#8e44ad", font=ctk.CTkFont(weight="bold", size=11)).pack(anchor="w", padx=10, pady=(0, 2))
            
            cor_s_proj = "#27ae60" if saldo_projetado >= 0 else "#e74c3c"
            ctk.CTkLabel(card_s, text=f"Saldo Mensal Livre Estimado: R$ {saldo_projetado:.2f}", text_color=cor_s_proj, font=ctk.CTkFont(weight="bold", size=11)).pack(anchor="w", padx=10, pady=(0, 6))

    def exportar_relatorio_geral_pdf(self):
        if not HAS_REPORTLAB:
            messagebox.showerror("Erro", "A biblioteca reportlab não está instalada.")
            return
        
        filepath = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")], initialfile="Relatorio_Geral_Haacktec.pdf")
        if not filepath: return
        
        try:
            doc = SimpleDocTemplate(filepath, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#2b7a78'), spaceAfter=15)
            
            elements.append(Paragraph("Haacktec - Relatório Financeiro Geral", title_style))
            elements.append(Paragraph(f"Mês Referência: {self.dados.get('mes_atual', 'Atual')}", styles['Normal']))
            elements.append(Spacer(1, 15))
            
            total_ganhos = sum(i["valor"] for i in self.dados["receitas"])
            total_gastos = sum(sum(item["valor"] for item in d.get("itens", [])) for d in self.dados["despesas"])
            
            total_caixinhas_pdf = 0.0
            total_aportes_pdf = 0.0

            for cx in self.dados.get("caixinhas", []):
                din_ini = cx.get("dinheiro_inicial", 0.0)
                ap_men = cx.get("aporte_mensal", 0.0)
                cdi_anual = cx.get("cdi_anual", 10.50)
                
                s_est, _ = calcular_rendimento_caixinha(din_ini, ap_men, cdi_anual, dias_investido=30)
                total_caixinhas_pdf += s_est
                total_aportes_pdf += ap_men
            
            saldo = total_ganhos - total_gastos - total_aportes_pdf
            
            resumo_data = [
                ["Resumo Geral", "Valor (R$)"],
                ["Ganhos Totais", f"R$ {total_ganhos:.2f}"],
                ["Gastos Totais", f"R$ {total_gastos:.2f}"],
                ["Aportes Caixinhas", f"R$ {total_aportes_pdf:.2f}"],
                ["Saldo Caixinhas (CDI Est.)", f"R$ {total_caixinhas_pdf:.2f}"],
                ["Saldo Líquido Mensal Livre", f"R$ {saldo:.2f}"]
            ]
            
            t_res = Table(resumo_data, colWidths=[300, 150])
            t_res.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3a86ff')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            
            elements.append(t_res)
            elements.append(Spacer(1, 20))
            elements.append(Paragraph("Detalhamento por Categoria", styles['Heading2']))
            elements.append(Spacer(1, 10))
            
            cat_table_data = [["Categoria", "Total (R$)"]]
            for d in self.dados["despesas"]:
                tot_c = sum(i["valor"] for i in d.get("itens", []))
                cat_table_data.append([d["categoria"], f"R$ {tot_c:.2f}"])
                
            t_cat = Table(cat_table_data, colWidths=[300, 150])
            t_cat.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2b7a78')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            
            elements.append(t_cat)
            doc.build(elements)
            registrar_log(self.dados, "Exportado Relatório Financeiro Geral em PDF.")
            messagebox.showinfo("Sucesso", f"Relatório geral exportado com sucesso para:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao gerar PDF: {e}")

    def janela_remover_gasto(self):
        win = ctk.CTkToplevel(self)
        self.configurar_janela_modal(win, "Remover Categoria", 400, 220)

        main_frame = ctk.CTkFrame(win, fg_color="#222222")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(main_frame, text="Selecione a Categoria:", font=ctk.CTkFont(weight="bold")).pack(pady=(15, 5))
        
        categorias = [d["categoria"] for d in self.dados["despesas"]]
        if not categorias:
            ctk.CTkLabel(main_frame, text="Nenhuma categoria cadastrada.", text_color="#aaaaaa").pack(pady=10)
            return

        cb_cat = ctk.CTkComboBox(main_frame, values=categorias, width=260)
        cb_cat.pack(pady=10)
        cb_cat.set(categorias[0])

        def remover():
            cat_selecionada = cb_cat.get()
            cat_obj = next((d for d in self.dados["despesas"] if d["categoria"] == cat_selecionada), None)
            
            if cat_obj:
                itens_count = len(cat_obj.get("itens", []))
                total_val = sum(i["valor"] for i in cat_obj.get("itens", []))
                
                if itens_count > 0:
                    msg = f"Atenção!\nA categoria '{cat_selecionada}' possui {itens_count} item(ns) cadastrado(s) totalizando R$ {total_val:.2f}.\n\nTem certeza de que deseja excluir esta categoria e TODOS os seus registros?"
                else:
                    msg = f"Tem certeza de que deseja remover a categoria '{cat_selecionada}'?"

                if messagebox.askyesno("Confirmar Exclusão", msg, parent=win):
                    self.dados["despesas"] = [d for d in self.dados["despesas"] if d["categoria"] != cat_selecionada]
                    registrar_log(self.dados, f"Excluída categoria '{cat_selecionada}' contendo {itens_count} itens (Total R$ {total_val:.2f}).")
                    self.salvar_e_recarregar()
                    win.destroy()

        ctk.CTkButton(main_frame, text="Remover Categoria", fg_color="#c0392b", hover_color="#e74c3c", command=remover).pack(pady=15)

if __name__ == "__main__":
    app = AppPlanilhaEstilo()
    app.mainloop()
