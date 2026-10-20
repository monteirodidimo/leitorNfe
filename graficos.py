"""Formatacao de numeros e o grafico de notas por hora.

Usados tanto na tela (app.py) quanto no PDF (pdf.py), para os dois ficarem iguais.
"""

from matplotlib.ticker import MaxNLocator

# Uma cor fixa para cada filial, na ordem alfabetica dos nomes. Assim a filial
# tem sempre a mesma cor, mesmo quando o grafico mostra so uma delas.
CORES = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]


def formatar_reais(valor):
    # 1234567.8 -> "R$ 1.234.567,80"
    texto = f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {texto}"


def formatar_kg(valor):
    texto = f"{valor:,.1f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{texto} kg"


def formatar_linha(linha):
    """Formata uma linha do resumo (relatorio.resumo) para mostrar na tela ou no PDF."""
    return [
        formatar_reais(linha["Faturamento (R$)"]),
        formatar_kg(linha["Peso (kg)"]),
        str(int(linha["Pedidos"])),
        formatar_reais(linha["Faturamento diurno (R$)"]),
        formatar_reais(linha["Faturamento noturno (R$)"]),
    ]


def nome_curto(filial):
    # "Empresa Exemplo - Filial SP" -> "Filial SP"
    return filial.split(" - ")[-1]


def desenhar_notas_por_hora(eixo, por_hora, todas_as_filiais):
    """Barras empilhadas: cada barra e uma hora; cada cor, uma filial.

    A altura da barra e o total de notas naquela hora e as cores mostram quanto
    veio de cada filial. O fundo cinza marca o turno noturno (20h as 6h59).
    """
    eixo.clear()
    eixo.axvspan(-0.5, 6.5, color="#eeeeee")
    eixo.axvspan(19.5, 23.5, color="#eeeeee")

    altura = [0] * 24
    for filial in por_hora.columns:
        cor = CORES[sorted(todas_as_filiais).index(filial) % len(CORES)]
        eixo.bar(range(24), por_hora[filial], bottom=altura, color=cor, label=nome_curto(filial))
        altura = [a + b for a, b in zip(altura, por_hora[filial], strict=True)]

    eixo.set_xticks(range(24))
    eixo.set_xticklabels([f"{hora:02d}h" for hora in range(24)], fontsize=8)
    eixo.set_xlim(-0.5, 23.5)
    eixo.set_ylim(0, max(altura) * 1.1 + 1)
    eixo.yaxis.set_major_locator(MaxNLocator(integer=True))  # nao existe "meia nota"
    eixo.set_ylabel("Notas")
    eixo.spines[["top", "right"]].set_visible(False)

    if sum(altura) == 0:
        eixo.text(11.5, 0.5, "Nenhuma nota válida neste período", ha="center", color="gray")
    else:
        # Legenda embaixo do grafico, para nunca cobrir as barras (ate 4 filiais por linha).
        colunas = min(len(por_hora.columns), 4)
        eixo.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=colunas, frameon=False)
