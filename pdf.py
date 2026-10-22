"""Relatorio em PDF de uma pagina, feito so com matplotlib.

O conteudo e o mesmo da tela: total do periodo, tabela por filial e o
grafico de notas emitidas por hora.
"""

from datetime import datetime

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure

from graficos import desenhar_notas_por_hora, formatar_kg, formatar_linha, formatar_reais, nome_curto
from relatorio import notas_por_hora, resumo, resumo_operacoes

CABECALHO = ["", "Faturamento", "Peso", "Pedidos", "Fat. diurno", "Fat. noturno"]
LARGURAS = [0.30, 0.14, 0.14, 0.14, 0.14, 0.14]  # a primeira coluna (nome) e mais larga
ALTURA_LINHA = 0.024  # altura de cada linha das tabelas, em fracao da pagina


def desenhar_tabela(figura, topo, titulo, linhas, cabecalho=CABECALHO, larguras=LARGURAS):
    """Desenha uma tabela abaixo da posicao 'topo' e devolve onde ela termina.

    A altura cresce com o numero de linhas, entao cabem quantas filiais houver
    sem invadir o grafico.
    """
    altura = ALTURA_LINHA * (len(linhas) + 1)  # +1 do cabecalho
    eixo = figura.add_axes([0.06, topo - altura, 0.88, altura])
    eixo.axis("off")
    eixo.set_title(titulo, loc="left", fontsize=11, fontweight="bold")

    tabela = eixo.table(
        cellText=linhas, colLabels=cabecalho, colWidths=larguras, cellLoc="right", bbox=[0, 0, 1, 1]
    )
    tabela.auto_set_font_size(False)
    tabela.set_fontsize(8)
    for (linha, coluna), celula in tabela.get_celld().items():
        celula.set_edgecolor("#cccccc")
        if linha == 0:
            celula.set_facecolor("#eeeeee")
            celula.set_text_props(fontweight="bold")
        if coluna == 0:
            celula.set_text_props(ha="left")
    return topo - altura


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
    aviso = "Somente vendas válidas (sem canceladas, inutilizadas, denegadas e outras operações)"
    figura.text(0.06, 0.915, aviso, fontsize=8)

    # Cada bloco comeca um pouco abaixo de onde o anterior terminou (0.05 = espaco do titulo).
    total = [["Total"] + formatar_linha(tabela.loc["Total"])]
    fim = desenhar_tabela(figura, 0.87, "Total do período", total)

    filiais = [
        [nome_curto(nome)] + formatar_linha(linha) for nome, linha in tabela.drop(index="Total").iterrows()
    ]
    fim = desenhar_tabela(figura, fim - 0.05, "Por filial", filiais or [["-"] * 6])

    # Notas que nao sao venda: aparecem so aqui, para conferencia.
    operacoes = resumo_operacoes(notas)
    fora = operacoes[operacoes["Operação"] != "Vendas"]
    if not fora.empty:
        linhas = []
        for _, linha in fora.iterrows():
            peso, valor = formatar_kg(linha["Peso (kg)"]), formatar_reais(linha["Valor (R$)"])
            linhas.append([linha["Operação"], str(linha["Notas"]), peso, valor])
        fim = desenhar_tabela(
            figura,
            fim - 0.05,
            "Fora do faturamento",
            linhas,
            cabecalho=["Operação", "Notas", "Peso", "Valor"],
            larguras=[0.46, 0.12, 0.2, 0.22],
        )

    eixo_grafico = figura.add_axes([0.08, fim - 0.30, 0.86, 0.24])
    desenhar_notas_por_hora(eixo_grafico, notas_por_hora(notas), todas_as_filiais)
    # o titulo vem depois: desenhar_notas_por_hora limpa o eixo antes de desenhar
    eixo_grafico.set_title("Notas emitidas por hora", loc="left", fontsize=11, fontweight="bold")

    figura.text(0.06, 0.03, f"Gerado em {datetime.now():%d/%m/%Y %H:%M}", fontsize=7, color="gray")

    with PdfPages(caminho) as arquivo_pdf:
        arquivo_pdf.savefig(figura)
