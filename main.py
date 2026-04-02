"""
Script principal para executar a automação do Logtudo.

Este script orquestra o fluxo de login e download de relatórios.
"""

import os
import sys
import argparse
import logging
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv

from automacao.login import realizar_login
from automacao.download import baixar_relatorio_conhecimento
from automacao.logging_config import setup_logging


# Carregar variáveis do arquivo .env
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)
setup_logging()
logger = logging.getLogger(__name__)


def obter_credenciais() -> tuple[str, str]:
    """
    Obtém as credenciais do usuário a partir de variáveis de ambiente ou entrada do usuário.
    
    Returns:
        Tuple contendo (usuario, senha)
    """
    usuario = os.getenv("LOGTUDO_USER")
    senha = os.getenv("LOGTUDO_PASS")
    
    if not usuario or not senha:
        logger.warning("credenciais_nao_encontradas_variaveis_ambiente")
        logger.info("defina_logtudo_user_e_logtudo_pass_ou_forneca_interativamente")
        
        if not usuario:
            usuario = input("Digite o usuário: ").strip()
        if not senha:
            from getpass import getpass
            senha = getpass("Digite a senha: ")
    
    return usuario, senha


def _str_para_bool(valor: Optional[str], padrao: bool = True) -> bool:
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "t", "yes", "y", "sim", "s", "on"}


def main(
    acao: str = "download",
    usuario: Optional[str] = None,
    senha: Optional[str] = None,
    headless: Optional[bool] = None,
) -> None:
    """
    Executa a ação de automação especificada.
    
    Args:
        acao: Ação a executar ('login', 'download' ou 'tudo')
        usuario: Usuário para login (opcional, usa variável de ambiente se não fornecido)
        senha: Senha para login (opcional, usa variável de ambiente se não fornecido)
    """
    # Obter credenciais se não foram fornecidas
    if usuario is None or senha is None:
        usuario, senha = obter_credenciais()

    if headless is None:
        headless = _str_para_bool(os.getenv("PLAYWRIGHT_HEADLESS"), padrao=True)
    
    try:
        if acao == "login":
            logger.info("iniciando_acao_login")
            realizar_login(usuario, senha, headless=headless)
            
        elif acao == "download":
            logger.info("iniciando_acao_download_relatorio")
            baixar_relatorio_conhecimento(usuario, senha, headless=headless)
            
        elif acao == "tudo":
            logger.info("iniciando_acao_tudo")
            baixar_relatorio_conhecimento(usuario, senha, headless=headless)
            
        else:
            logger.error("acao_desconhecida valor=%s", acao)
            logger.info("acoes_disponiveis=login,download,tudo")
            sys.exit(1)
        
        logger.info("processo_completado_com_sucesso")
        
    except KeyboardInterrupt:
        logger.warning("operacao_cancelada_pelo_usuario")
        sys.exit(1)
    except Exception as e:
        logger.exception("erro_execucao_automacao detalhe=%s", e)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Automação Logtudo - Download de Relatórios",
        epilog="Exemplo: python main.py --acao download"
    )
    
    parser.add_argument(
        "--acao",
        choices=["login", "download", "tudo"],
        default="download",
        help="Ação a executar (padrão: download)"
    )
    parser.add_argument(
        "-u", "--usuario",
        help="Usuário para login (usa LOGTUDO_USER se não fornecido)"
    )
    parser.add_argument(
        "-s", "--senha",
        help="Senha para login (usa LOGTUDO_PASS se não fornecido)"
    )
    parser.add_argument(
        "--headless",
        choices=["true", "false"],
        help="Executa em modo headless (usa PLAYWRIGHT_HEADLESS se não informado)"
    )
    
    args = parser.parse_args()
    headless_arg = None if args.headless is None else _str_para_bool(args.headless)

    main(acao=args.acao, usuario=args.usuario, senha=args.senha, headless=headless_arg)
