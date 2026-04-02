"""
Teste rápido de envio SMTP usando as variáveis do .env.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from automacao.smtp_notifier import enviar_alerta_campos_st


def main() -> None:
    parser = argparse.ArgumentParser(description="Teste de envio SMTP")
    parser.add_argument(
        "--registros",
        type=int,
        default=2,
        help="Quantidade de linhas de exemplo no e-mail (padrão: 2)",
    )
    args = parser.parse_args()

    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(env_path)

    quantidade = max(1, args.registros)
    dados = []
    for i in range(1, quantidade + 1):
        dados.append(
            {
                "ctrc": f"CTRC-{1000 + i}",
                "cliente": f"Cliente Teste {i}",
                "emissao": "02/04/2026",
                "c. pedido": f"PED-{2000 + i}",
                "frete valor": "150,00",
                "Colunas com valor vazio/0": "BC ST, ICMS ST",
            }
        )

    df = pd.DataFrame(dados)
    enviado = enviar_alerta_campos_st(df, arquivo_origem=Path("downloads/arquivo_teste.xls"))

    if enviado:
        print("Teste SMTP concluído com sucesso.")
    else:
        print("Teste SMTP finalizado sem envio. Verifique as mensagens acima.")


if __name__ == "__main__":
    main()
