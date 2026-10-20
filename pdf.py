"""Relatorio em PDF de uma pagina, feito so com matplotlib.

O conteudo e o mesmo da tela: total do periodo, tabela por filial e o
grafico de notas emitidas por hora.
"""

from datetime import datetime

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure

from graficos import desenhar_notas_por_hora, formatar_linha, nome_curto
from relatorio import notas_por_hora, resumo

CABECALHO = ["", "Faturamento", "Peso", "Pedidos", "Fat. diurno", "Fat. noturno"]


def desenhar_tabela(eixo, titulo, linhas):
    eixo.axis("off")
    eixo.set_title(titulo, loc="left", fontsize=11, fontweight="bold")
    tabela = eixo.table(cellText=linhas, colLabels=CABECALHO, loc="upper center", cellLoc="right")
    tabela.auto_set_font_size(False)
    tabela.set_fontsize(8)
    tabela.scale(1, 1.6)
    for (linha, coluna), celula in tabela.get_celld().items():
        celula.set_edgecolor("#cccccc")
        if linha == 0:
            celula.set_facecolor("#eeeeee")
            celula.set_text_props(fontweight="bold")
        if coluna == 0:
            celula.set_text_props(ha="left")


def gerar_pdf(notas, caminho, descricao_filtros, todas_as_filiais):
    """Salva em PDF o relatorio das notas (ja filtradas).

    descricao_filtros: texto do topo, ex.: "Periodo: 06/03/2026 00:00 a 06/03/2026 23:59".
    todas_as_filiais: lista com todas as filiais, para as cores do grafico
    serem as mesmas da tela.
    """
    tabela = resumo(notas)

    # Figure (e nao pyplot) nao abre nenhuma janela: funciona ate sem tela.
    figura = Figure(figsize=(8.27, 11.69))  # folha A4, em polegadas
    figura.text(0.06, 0.96, "Relatório de faturamento", fontsize=18, fontweight="bold")
    figura.text(0.06, 0.935, descricao_filtros, fontsize=10, color="gray")
    figura.text(0.06, 0.915, "Somente notas válidas (sem canceladas, inutilizadas e denegadas)", fontsize=8)

    eixo_total = figura.add_axes([0.06, 0.80, 0.88, 0.09])
    desenhar_tabela(eixo_total, "Total do período", [["Total"] + formatar_linha(tabela.loc["Total"])])

    linhas_filiais = []
    for filial, linha in tabela.drop(index="Total").iterrows():
        linhas_filiais.append([nome_curto(filial)] + formatar_linha(linha))
    eixo_filiais = figura.add_axes([0.06, 0.66, 0.88, 0.12])
    desenhar_tabela(eixo_filiais, "Por filial", linhas_filiais or [["-"] * 6])

    eixo_grafico = figura.add_axes([0.08, 0.40, 0.86, 0.22])
    desenhar_notas_por_hora(eixo_grafico, notas_por_hora(notas), todas_as_filiais)
    # o titulo vem depois: desenhar_notas_por_hora limpa o eixo antes de desenhar
    eixo_grafico.set_title("Notas emitidas por hora", loc="left", fontsize=11, fontweight="bold")

    figura.text(0.06, 0.03, f"Gerado em {datetime.now():%d/%m/%Y %H:%M}", fontsize=7, color="gray")

    with PdfPages(caminho) as arquivo_pdf:
        arquivo_pdf.savefig(figura)
