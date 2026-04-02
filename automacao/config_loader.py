"""
Carregador de configurações e mapeamentos para automação.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict


def carregar_mapeamento() -> Dict[str, Any]:
    """
    Carrega o mapeamento de URLs e seletores.
    
    Tenta carregar de um arquivo JSON, caso contrário retorna valores padrão.
    
    Returns:
        Dict contendo URLs e seletores para o sistema Logtudo.
    """
    config_file = Path(__file__).parent / "mapeamento.json"
    
    # Se um arquivo de mapeamento existe, carrega dele
    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    # Caso contrário, retorna configuração padrão
    return {
        "urls": {
            "login": os.getenv("LOGTUDO_URL", "https://www.logtudo.com.br/login"),
        },
        "selectors": {
            "campo_usuario": os.getenv("LOGTUDO_USER_SELECTOR", "input[name='usuario']"),
            "campo_senha": os.getenv("LOGTUDO_PASS_SELECTOR", "input[name='senha']"),
            "botao_entrar": os.getenv("LOGTUDO_SUBMIT_SELECTOR", "button[type='submit']"),
        }
    }
