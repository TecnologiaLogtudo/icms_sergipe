"""
Tratamentos de limpeza para a planilha do relatório de conhecimento.
"""

from __future__ import annotations

import unicodedata

import pandas as pd


def _normalizar_texto(valor: object) -> str:
    texto = "" if valor is None else str(valor)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.strip().lower()


def _eh_vazio(valor: object) -> bool:
    if pd.isna(valor):
        return True
    return str(valor).strip() == ""


def remover_linha_final_bc_icms_st(tabela: pd.DataFrame) -> pd.DataFrame:
    """
    Remove a última linha quando ela possuir valores apenas nas colunas
    BC ST e ICMS ST.
    """
    if tabela.empty:
        return tabela

    mapa_colunas = {_normalizar_texto(col): col for col in tabela.columns}
    col_bc_st = mapa_colunas.get("bc st")
    col_icms_st = mapa_colunas.get("icms st")
    col_frete_valor = mapa_colunas.get("frete valor")

    if col_icms_st is None:
        return tabela

    ultima_linha = tabela.iloc[-1]
    colunas_com_valor = [col for col in tabela.columns if not _eh_vazio(ultima_linha[col])]

    pares_validos = []
    if col_bc_st is not None:
        pares_validos.append({col_bc_st, col_icms_st})
    if col_frete_valor is not None:
        pares_validos.append({col_frete_valor, col_icms_st})

    if set(colunas_com_valor) not in pares_validos:
        return tabela

    return tabela.iloc[:-1].reset_index(drop=True)


def _eh_zero_ou_vazio(valor: object) -> bool:
    if _eh_vazio(valor):
        return True

    texto = str(valor).strip()
    texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto) == 0.0
    except ValueError:
        return False


def gerar_tabela_filtro_campos_st(tabela: pd.DataFrame) -> pd.DataFrame:
    """
    Gera tabela com linhas em que BC ST, Aliquota ICMSST ou ICMS ST
    estejam vazios ou iguais a zero.
    """
    if tabela.empty:
        return pd.DataFrame()

    mapa_colunas = {_normalizar_texto(col): col for col in tabela.columns}
    col_bc_st = mapa_colunas.get("bc st")
    col_aliquota = mapa_colunas.get("aliquota icmsst")
    col_icms_st = mapa_colunas.get("icms st")

    if not col_bc_st or not col_aliquota or not col_icms_st:
        return pd.DataFrame()

    base_ordenada = []
    for nome in ["ctrc", "cliente", "emissao", "c. pedido", "frete valor"]:
        coluna = mapa_colunas.get(nome)
        if coluna:
            base_ordenada.append(coluna)

    registros = []
    cols_alvo = [col_bc_st, col_aliquota, col_icms_st]
    for _, linha in tabela.iterrows():
        colunas_com_problema = [col for col in cols_alvo if _eh_zero_ou_vazio(linha[col])]
        if not colunas_com_problema:
            continue

        registro = {col: linha[col] for col in base_ordenada}
        registro["Colunas com valor vazio/0"] = ", ".join(str(c) for c in colunas_com_problema)
        registros.append(registro)

    if not registros:
        return pd.DataFrame(columns=[*base_ordenada, "Colunas com valor vazio/0"])

    return pd.DataFrame(registros)
