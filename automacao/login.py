import os
import time

from Conectividade.playwright_vps_connect import PlaywrightVPSConfig, PlaywrightVPSClient
from automacao.config_loader import carregar_mapeamento


MAPPINGS = carregar_mapeamento()
URL_LOGIN = MAPPINGS["urls"]["login"]
SEL_USUARIO = MAPPINGS["selectors"]["campo_usuario"]
SEL_SENHA = MAPPINGS["selectors"]["campo_senha"]
SEL_ENTRAR = MAPPINGS["selectors"]["botao_entrar"]


def realizar_login(usuario: str, senha: str, headless: bool = False, debug: bool = True) -> None:
    """
    Executa o login no Logtudo.
    
    Args:
        usuario: Usuário para login
        senha: Senha para login
        headless: Se True, executa sem exibir a janela do navegador
        debug: Se True, exibe mais informações de debug
    """
    config = PlaywrightVPSConfig(headless=headless, timeout_ms=60000)

    with PlaywrightVPSClient(config) as client:
        page = client.page

        try:
            print("Acessando a URL de login...")
            page.goto(URL_LOGIN, wait_until="domcontentloaded")
            
            # Aguardar carregamento completo
            print("Aguardando página carregar completamente...")
            time.sleep(2)
            
            # Debug: verificar se os elementos existem
            if debug:
                print(f"Procurando pelo seletor de usuário: {SEL_USUARIO}")
            
            # Tentar esperar pelo campo de usuário aparecer
            try:
                page.wait_for_selector(SEL_USUARIO, timeout=10000)
                print(f"✓ Campo de usuário encontrado")
            except Exception as e:
                print(f"✗ Campo de usuário não encontrado: {e}")
                print(f"  Seletor usado: {SEL_USUARIO}")
                if debug:
                    print(f"  URL da página: {page.url}")
                    # Salvar screenshot para debug
                    page.screenshot(path="debug_screenshot.png")
                    print("  Screenshot salvo em: debug_screenshot.png")
                raise

            print("Preenchendo usuário...")
            page.locator(SEL_USUARIO).fill(usuario)
            
            print("Preenchendo senha...")
            page.locator(SEL_SENHA).fill(senha)

            print("Clicando no botão Entrar...")
            page.locator(SEL_ENTRAR).click()
            
            print("Aguardando navegação...")
            try:
                page.wait_for_load_state("load", timeout=15000)
            except:
                print("  ⚠ Timeout no 'load', continuando mesmo assim...")
            
            time.sleep(2)
            print("✓ Login concluído com sucesso!")
            
        except Exception as e:
            print(f"✗ Erro durante login: {e}")
            raise


if __name__ == "__main__":
    usuario = os.getenv("LOGTUDO_USER", "ATUALIZARBI")
    senha = os.getenv("LOGTUDO_PASS", "sua_senha_aqui")
    # Desativar headless e ativar debug por padrão ao executar diretamente
    realizar_login(usuario, senha, headless=False, debug=True)
