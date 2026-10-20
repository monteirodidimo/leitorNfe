"""Tela do relatorio de faturamento (Tkinter + matplotlib).

Para abrir:  python app.py
"""

import json
import os
import sqlite3
import sys
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from banco import atualizar_banco
from graficos import desenhar_notas_por_hora, formatar_linha
from pdf import gerar_pdf
from relatorio import carregar_notas, exportar, filtrar, notas_por_hora, resumo

# Quando o programa vira .exe (PyInstaller), os arquivos ficam ao lado do .exe.
if getattr(sys, "frozen", False):
    PASTA_DO_PROGRAMA = os.path.dirname(sys.executable)
else:
    PASTA_DO_PROGRAMA = os.path.dirname(os.path.abspath(__file__))

CAMINHO_BANCO = os.path.join(PASTA_DO_PROGRAMA, "notas.db")
CAMINHO_CONFIG = os.path.join(PASTA_DO_PROGRAMA, "config.json")
FORMATO_DATA = "%d/%m/%Y %H:%M"
COLUNAS = ["Faturamento", "Peso", "Pedidos", "Faturamento diurno", "Faturamento noturno"]
MENSAGEM_BANCO_DANIFICADO = (
    "O arquivo notas.db está danificado.\n\n"
    "Feche o programa, apague o notas.db (ele fica na pasta do programa) "
    "e clique em Atualizar dados para ler os XMLs de novo."
)


def ler_config():
    try:
        with open(CAMINHO_CONFIG, encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except (OSError, ValueError):
        return {}


def salvar_config(config):
    # Se a pasta do programa nao permitir escrita, so nao guarda a configuracao.
    try:
        with open(CAMINHO_CONFIG, "w", encoding="utf-8") as arquivo:
            json.dump(config, arquivo, indent=2)
    except OSError:
        pass


class Aplicativo:
    def __init__(self, janela):
        self.janela = janela
        self.janela.title("Relatório de faturamento")
        self.janela.geometry("1100x780")
        self.config = ler_config()
        self.notas = None  # todas as notas do banco (DataFrame)
        self.notas_filtradas = None

        self.criar_area_pasta()
        self.criar_area_filtros()
        self.criar_area_totais()
        self.criar_tabela_filiais()
        self.criar_grafico()
        self.criar_botoes_exportar()

        if os.path.exists(CAMINHO_BANCO):
            self.carregar_e_mostrar()
        else:
            self.texto_situacao.set("Para começar, escolha a pasta dos XMLs e clique em Atualizar dados.")

    # --- Montagem da tela ----------------------------------------------------

    def criar_area_pasta(self):
        quadro = ttk.Frame(self.janela, padding=10)
        quadro.pack(fill="x")

        ttk.Label(quadro, text="Pasta dos XMLs:").pack(side="left")
        self.texto_pasta = tk.StringVar(value=self.config.get("pasta", ""))
        ttk.Entry(quadro, textvariable=self.texto_pasta, width=60, state="readonly").pack(side="left", padx=5)
        ttk.Button(quadro, text="Escolher...", command=self.escolher_pasta).pack(side="left")
        self.botao_atualizar = ttk.Button(quadro, text="Atualizar dados", command=self.atualizar_dados)
        self.botao_atualizar.pack(side="left", padx=5)

        self.texto_situacao = tk.StringVar()
        ttk.Label(quadro, textvariable=self.texto_situacao, foreground="gray").pack(side="left", padx=10)

    def criar_area_filtros(self):
        quadro = ttk.LabelFrame(self.janela, text="Filtros", padding=10)
        quadro.pack(fill="x", padx=10)

        ttk.Label(quadro, text="De:").grid(row=0, column=0)
        self.texto_inicio = tk.StringVar()
        ttk.Entry(quadro, textvariable=self.texto_inicio, width=17).grid(row=0, column=1, padx=5)

        ttk.Label(quadro, text="Até:").grid(row=0, column=2)
        self.texto_fim = tk.StringVar()
        ttk.Entry(quadro, textvariable=self.texto_fim, width=17).grid(row=0, column=3, padx=5)

        ttk.Label(quadro, text="Filial:").grid(row=0, column=4, padx=(15, 0))
        self.caixa_filial = ttk.Combobox(quadro, values=["Todas"], state="readonly", width=30)
        self.caixa_filial.set("Todas")
        self.caixa_filial.grid(row=0, column=5, padx=5)

        ttk.Label(quadro, text="Turno:").grid(row=0, column=6, padx=(15, 0))
        turnos = ["Todos", "diurno", "noturno"]
        self.caixa_turno = ttk.Combobox(quadro, values=turnos, state="readonly", width=10)
        self.caixa_turno.set("Todos")
        self.caixa_turno.grid(row=0, column=7, padx=5)

        ttk.Button(quadro, text="Aplicar", command=self.mostrar_relatorio).grid(row=0, column=8, padx=(15, 5))
        ttk.Button(quadro, text="Último dia", command=self.escolher_ultimo_dia).grid(row=0, column=9)

        dica = "Formato: dd/mm/aaaa hh:mm · Diurno 07:00–19:59 · Noturno 20:00–06:59"
        ttk.Label(quadro, text=dica, foreground="gray").grid(row=1, column=0, columnspan=10, sticky="w")

    def criar_area_totais(self):
        quadro = ttk.LabelFrame(self.janela, text="Total do período", padding=10)
        quadro.pack(fill="x", padx=10, pady=10)

        self.valores_totais = []
        for coluna, nome in enumerate(COLUNAS):
            quadro.columnconfigure(coluna, weight=1)
            ttk.Label(quadro, text=nome, foreground="gray").grid(row=0, column=coluna)
            valor = tk.StringVar(value="-")
            ttk.Label(quadro, textvariable=valor, font=("Segoe UI", 16, "bold")).grid(row=1, column=coluna)
            self.valores_totais.append(valor)

    def criar_tabela_filiais(self):
        quadro = ttk.LabelFrame(self.janela, text="Por filial", padding=10)
        quadro.pack(fill="x", padx=10)

        self.tabela = ttk.Treeview(quadro, columns=["Filial"] + COLUNAS, show="headings", height=2)
        self.tabela.heading("Filial", text="Filial")
        self.tabela.column("Filial", anchor="w", width=260)
        for coluna in COLUNAS:
            self.tabela.heading(coluna, text=coluna)
            self.tabela.column(coluna, anchor="e", width=150)
        self.tabela.pack(fill="x")

    def criar_grafico(self):
        quadro = ttk.LabelFrame(self.janela, text="Notas emitidas por hora", padding=5)
        quadro.pack(fill="both", expand=True, padx=10, pady=10)

        self.figura = Figure(figsize=(10, 3))
        self.eixo = self.figura.add_subplot()
        self.canvas = FigureCanvasTkAgg(self.figura, master=quadro)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def criar_botoes_exportar(self):
        quadro = ttk.Frame(self.janela, padding=(10, 0, 10, 10))
        quadro.pack(fill="x")
        ttk.Label(quadro, text="Exportar o período filtrado:").pack(side="left")
        ttk.Button(quadro, text="CSV", command=lambda: self.exportar(".csv")).pack(side="left", padx=5)
        ttk.Button(quadro, text="Excel", command=lambda: self.exportar(".xlsx")).pack(side="left")
        ttk.Button(quadro, text="PDF", command=lambda: self.exportar(".pdf")).pack(side="left", padx=5)

    # --- Acoes -----------------------------------------------------------------

    def escolher_pasta(self):
        pasta = filedialog.askdirectory(title="Escolha a pasta com os XMLs")
        if pasta:
            self.texto_pasta.set(pasta)
            self.config["pasta"] = pasta
            salvar_config(self.config)

    def atualizar_dados(self):
        pasta = self.texto_pasta.get()
        if not pasta or not os.path.isdir(pasta):
            messagebox.showwarning("Pasta", "Escolha uma pasta válida com os XMLs.")
            return

        def mostrar_progresso(lidos, total):
            if lidos % 50 == 0 or lidos == total:
                self.texto_situacao.set(f"Lendo arquivos... {lidos} de {total}")
                # update_idletasks so redesenha a tela; nao processa cliques,
                # entao o usuario nao consegue iniciar uma segunda leitura no meio.
                self.janela.update_idletasks()

        self.botao_atualizar.state(["disabled"])
        try:
            lidos = atualizar_banco(pasta, CAMINHO_BANCO, mostrar_progresso)
        except sqlite3.DatabaseError:
            messagebox.showerror("Banco de dados", MENSAGEM_BANCO_DANIFICADO)
            return
        finally:
            self.botao_atualizar.state(["!disabled"])

        self.texto_situacao.set(f"Atualizado: {lidos} arquivo(s) novo(s) ou alterado(s)")
        self.carregar_e_mostrar()

    def carregar_e_mostrar(self):
        try:
            self.notas = carregar_notas(CAMINHO_BANCO)
        except sqlite3.DatabaseError:
            messagebox.showerror("Banco de dados", MENSAGEM_BANCO_DANIFICADO)
            return

        if self.notas.empty:
            self.texto_situacao.set("Nenhuma nota encontrada. Confira a pasta e clique em Atualizar dados.")
            return

        self.caixa_filial["values"] = ["Todas"] + sorted(self.notas["filial"].unique())
        self.escolher_ultimo_dia()

    def escolher_ultimo_dia(self):
        if self.notas is None or self.notas.empty:
            return
        # O lote noturno passa da meia-noite, entao o dia mais recente pode ter
        # so a sobra da madrugada. Usa o ultimo dia que teve expediente diurno
        # (ou o ultimo dia com notas, se nao houver nenhuma diurna).
        diurnas = self.notas[self.notas["turno"] == "diurno"]
        if diurnas.empty:
            diurnas = self.notas
        ultimo_dia = diurnas["emissao"].max().normalize()

        self.texto_inicio.set(ultimo_dia.strftime(FORMATO_DATA))
        self.texto_fim.set((ultimo_dia + timedelta(hours=23, minutes=59)).strftime(FORMATO_DATA))
        self.mostrar_relatorio()

    def ler_periodo(self):
        """Converte os campos De/Até em datas. Devolve None se estiverem errados."""
        try:
            inicio = datetime.strptime(self.texto_inicio.get().strip(), FORMATO_DATA)
            fim = datetime.strptime(self.texto_fim.get().strip(), FORMATO_DATA)
        except ValueError:
            messagebox.showwarning("Período", "Use o formato dd/mm/aaaa hh:mm, por exemplo 02/03/2026 22:00.")
            return None
        if fim < inicio:
            messagebox.showwarning("Período", "A data final é anterior à inicial.")
            return None
        # inclui o minuto final inteiro (ate hh:mm:59)
        return inicio, fim + timedelta(seconds=59)

    def limpar_resultados(self):
        """Apaga os numeros da tela, para nao parecerem ser do periodo digitado."""
        self.notas_filtradas = None
        for valor in self.valores_totais:
            valor.set("-")
        self.tabela.delete(*self.tabela.get_children())

    def mostrar_relatorio(self):
        if self.notas is None:
            return
        periodo = self.ler_periodo()
        if periodo is None:
            self.limpar_resultados()
            return

        inicio, fim = periodo
        filial, turno = self.caixa_filial.get(), self.caixa_turno.get()
        self.notas_filtradas = filtrar(self.notas, inicio, fim, filial, turno)
        tabela = resumo(self.notas_filtradas)

        for valor, texto in zip(self.valores_totais, formatar_linha(tabela.loc["Total"]), strict=True):
            valor.set(texto)

        self.tabela.delete(*self.tabela.get_children())
        filiais = tabela.drop(index="Total")
        self.tabela.configure(height=max(2, len(filiais)))
        for nome, linha in filiais.iterrows():
            self.tabela.insert("", "end", values=[nome] + formatar_linha(linha))

        todas_as_filiais = list(self.notas["filial"].unique())
        desenhar_notas_por_hora(self.eixo, notas_por_hora(self.notas_filtradas), todas_as_filiais)
        self.figura.tight_layout()
        self.canvas.draw()

    def descrever_filtros(self):
        texto = f"Período: {self.texto_inicio.get()} a {self.texto_fim.get()}"
        if self.caixa_filial.get() != "Todas":
            texto += f" · Filial: {self.caixa_filial.get()}"
        if self.caixa_turno.get() != "Todos":
            texto += f" · Turno: {self.caixa_turno.get()}"
        return texto

    def exportar(self, extensao):
        if self.notas_filtradas is None or self.notas_filtradas.empty:
            messagebox.showinfo("Exportar", "Não há notas no período filtrado.")
            return

        tipos = {".csv": ("CSV", "*.csv"), ".xlsx": ("Excel", "*.xlsx"), ".pdf": ("PDF", "*.pdf")}
        caminho = filedialog.asksaveasfilename(
            defaultextension=extensao, filetypes=[tipos[extensao]], initialfile="relatorio"
        )
        if not caminho:
            return

        try:
            if extensao == ".pdf":
                todas_as_filiais = list(self.notas["filial"].unique())
                gerar_pdf(self.notas_filtradas, caminho, self.descrever_filtros(), todas_as_filiais)
            else:
                exportar(self.notas_filtradas, caminho)
        except PermissionError:
            messagebox.showerror(
                "Exportar", "Não foi possível salvar. O arquivo está aberto em outro programa?"
            )
            return
        messagebox.showinfo("Exportar", f"Arquivo salvo em:\n{caminho}")


if __name__ == "__main__":
    janela = tk.Tk()
    Aplicativo(janela)
    janela.mainloop()
