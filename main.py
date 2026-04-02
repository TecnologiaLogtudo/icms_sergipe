"""
Script principal para executar a automação do Logtudo.

Este script orquestra o fluxo de login e download de relatórios.
"""

import os
import sys
import argparse
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv

from automacao.login import realizar_login
from automacao.download import baixar_relatorio_conhecimento


# Carregar variáveis do arquivo .env
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)


def obter_credenciais() -> tuple[str, str]:
    """
    Obtém as credenciais do usuário a partir de variáveis de ambiente ou entrada do usuário.
    
    Returns:
        Tuple contendo (usuario, senha)
    """
    usuario = os.getenv("LOGTUDO_USER")
    senha = os.getenv("LOGTUDO_PASS")
    
    if not usuario or not senha:
        print("⚠ Credenciais não encontradas nas variáveis de ambiente.")
        print("Defina LOGTUDO_USER e LOGTUDO_PASS ou forneça-as interativamente.\n")
        
        if not usuario:
            usuario = input("Digite o usuário: ").strip()
        if not senha:
            from getpass import getpass
            senha = getpass("Digite a senha: ")
    
    return usuario, senha


def main(acao: str = "download", usuario: Optional[str] = None, senha: Optional[str] = None) -> None:
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
    
    try:
        if acao == "login":
            print("=" * 60)
            print("INICIANDO: Apenas Login")
            print("=" * 60)
            realizar_login(usuario, senha, headless=False)
            
        elif acao == "download":
            print("=" * 60)
            print("INICIANDO: Download de Relatório")
            print("=" * 60)
            baixar_relatorio_conhecimento(usuario, senha, headless=False)
            
        elif acao == "tudo":
            print("=" * 60)
            print("INICIANDO: Login + Download de Relatório")
            print("=" * 60)
            baixar_relatorio_conhecimento(usuario, senha, headless=False)
            
        else:
            print(f"✗ Ação desconhecida: {acao}")
            print("Ações disponíveis: 'login', 'download', 'tudo'")
            sys.exit(1)
        
        print("\n" + "=" * 60)
        print("✓ SUCESSO: Processo completado!")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n⚠ Operação cancelada pelo usuário.")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERRO: {e}")
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
    
    args = parser.parse_args()
    
    main(acao=args.acao, usuario=args.usuario, senha=args.senha)
