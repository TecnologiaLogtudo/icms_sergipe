import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from Conectividade.playwright_vps_connect import PlaywrightVPSConfig, PlaywrightVPSClient
from automacao.config_loader import carregar_mapeamento
from automacao.login import realizar_login


MAPPINGS = carregar_mapeamento()
URL_LOGIN = MAPPINGS["urls"]["login"]
URL_RELATORIO = MAPPINGS["urls"]["relatorio_conhecimento"]
SEL_BOTAO_GERAR = MAPPINGS["selectors"]["botao_gerar_relatorio"]
SEL_BOTAO_SALVAR_CSS = MAPPINGS["selectors"]["botao_salvar_relatorio_css"]
SEL_BOTAO_SALVAR_XPATH = MAPPINGS["selectors"]["botao_salvar_relatorio_xpath"]


def _encontrar_superficie_relatorio(client: PlaywrightVPSClient, page_inicial, timeout_ms: int = 30000):
    """
    Encontra onde o relatório foi renderizado.

    O Logtudo pode abrir em:
    1) mesma página,
    2) nova aba/popup,
    3) iframe interno.
    """
    inicio = time.time()
    while (time.time() - inicio) * 1000 < timeout_ms:
        paginas = list(client.context.pages) if client.context else [page_inicial]

        # Prioriza páginas mais prováveis (URL do relatório e página atual por último)
        paginas_ordenadas = sorted(
            paginas,
            key=lambda p: (
                "carrega_relatorio2.php" not in (p.url or ""),
                p != page_inicial,
            ),
        )

        for pagina in paginas_ordenadas:
            try:
                if pagina.locator("#_bobarra").count() > 0:
                    return pagina, None
            except Exception:
                pass

            for frame in pagina.frames:
                try:
                    if frame.locator("#_bobarra").count() > 0:
                        return pagina, frame
                except Exception:
                    continue

        time.sleep(0.4)

    return page_inicial, None


def _clicar_botao_salvar(alvo, timeout_ms: int = 12000) -> bool:
    """
    Tenta clicar no botão de salvar usando seletores alternativos.
    """
    seletores = [
        SEL_BOTAO_SALVAR_CSS,
        "#_bobarra > a:nth-child(4)",
        "xpath=//*[@id='_bobarra']/a[4]",
        f"xpath={SEL_BOTAO_SALVAR_XPATH}",
        "#_bobarra img[src*='table_save.svg']",
    ]

    for seletor in seletores:
        try:
            elemento = alvo.locator(seletor).first
            elemento.wait_for(state="visible", timeout=timeout_ms)
            elemento.click()
            print(f"✓ Clique em 'Salvar relatório' com seletor: {seletor}")
            return True
        except Exception:
            continue

    return False


def _resolver_pasta_downloads() -> Path:
    """
    Resolve a pasta de saída dos downloads.

    Pode ser definida pela env LOGTUDO_DOWNLOAD_DIR; padrão: ./downloads
    """
    pasta_env = os.getenv("LOGTUDO_DOWNLOAD_DIR", "").strip()
    pasta = Path(pasta_env) if pasta_env else Path.cwd() / "downloads"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _sanitizar_nome_arquivo(nome: str) -> str:
    proibidos = '<>:"/\\|?*'
    nome_limpo = "".join("_" if c in proibidos else c for c in nome).strip()
    return nome_limpo or f"relatorio_{int(time.time())}.bin"


def _arquivo_mais_recente(pasta: Path, apos: float) -> Path | None:
    candidatos = []
    for item in pasta.glob("*"):
        if item.is_file() and item.stat().st_mtime >= apos:
            candidatos.append(item)
    if not candidatos:
        return None
    return max(candidatos, key=lambda p: p.stat().st_mtime)


def _nome_relatorio_padrao() -> str:
    return f"relatorio_conhecimento_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xls"


def _garantir_extensao_xls(nome: str) -> str:
    caminho = Path(nome)
    if caminho.suffix:
        return nome
    return f"{nome}.xls"


def _nome_unico(caminho: Path) -> Path:
    if not caminho.exists():
        return caminho
    base = caminho.stem
    ext = caminho.suffix
    for i in range(1, 1000):
        candidato = caminho.with_name(f"{base}_{i}{ext}")
        if not candidato.exists():
            return candidato
    return caminho.with_name(f"{base}_{int(time.time())}{ext}")


def _salvar_html_relatorio(alvo, pasta_downloads: Path) -> Path:
    """
    Salva o HTML do relatório com extensão .xls para abertura no Excel.
    """
    html = alvo.content()
    destino = _nome_unico(pasta_downloads / _nome_relatorio_padrao())
    destino.write_text(html, encoding="utf-8")
    return destino


def _limpar_pasta_temporaria(pasta_tmp: Path) -> None:
    for item in pasta_tmp.glob("*"):
        try:
            if item.is_file():
                item.unlink()
        except Exception:
            continue


def _arquivo_parece_html(caminho: Path) -> bool:
    try:
        amostra = caminho.read_text(encoding="utf-8", errors="ignore")[:2000].lower()
    except Exception:
        return False
    return "<html" in amostra and "<table" in amostra


def _converter_html_para_xlsx_csv(caminho_arquivo: Path) -> None:
    """
    Converte relatório HTML (salvo como .xls) para arquivos reais .xlsx e .csv.
    """
    if not _arquivo_parece_html(caminho_arquivo):
        return

    try:
        import pandas as pd
    except ImportError:
        print("⚠ pandas não instalado. Pulando conversão para .xlsx/.csv.")
        return

    try:
        tabelas = pd.read_html(caminho_arquivo, flavor=["lxml", "bs4"])
    except Exception as exc:
        print(f"⚠ Não foi possível converter HTML para tabela: {exc}")
        return

    if not tabelas:
        print("⚠ Nenhuma tabela encontrada no HTML do relatório.")
        return

    tabela = tabelas[0]
    if tabela.empty:
        print("⚠ Tabela convertida vazia. Pulando exportação .xlsx/.csv.")
        return

    caminho_xlsx = _nome_unico(caminho_arquivo.with_name(f"{caminho_arquivo.stem}_convertido.xlsx"))
    caminho_csv = _nome_unico(caminho_arquivo.with_name(f"{caminho_arquivo.stem}_convertido.csv"))

    tabela.to_excel(caminho_xlsx, index=False)
    tabela.to_csv(caminho_csv, index=False, encoding="utf-8-sig", sep=";")

    print(f"✓ Conversão concluída: {caminho_xlsx.resolve()}")
    print(f"✓ Conversão concluída: {caminho_csv.resolve()}")


def baixar_relatorio_conhecimento(usuario: str, senha: str, headless: bool = False, debug: bool = True) -> None:
    """
    Realiza login e baixa o relatório de conhecimento.
    
    Args:
        usuario: Usuário para login
        senha: Senha para login
        headless: Se True, executa sem exibir a janela do navegador
        debug: Se True, exibe mais informações de debug
    """
    pasta_downloads = _resolver_pasta_downloads()
    pasta_downloads_tmp = pasta_downloads / "_tmp_playwright"
    pasta_downloads_tmp.mkdir(parents=True, exist_ok=True)

    config = PlaywrightVPSConfig(
        headless=headless,
        timeout_ms=60000,
        downloads_path=str(pasta_downloads_tmp),
        accept_downloads=True,
    )
    print(f"Pasta de downloads configurada: {pasta_downloads.resolve()}")

    with PlaywrightVPSClient(config) as client:
        page = client.page

        try:
            # Realizar login
            print("Realizando login...")
            page.goto(URL_LOGIN, wait_until="domcontentloaded")
            page.locator(MAPPINGS["selectors"]["campo_usuario"]).fill(usuario)
            page.locator(MAPPINGS["selectors"]["campo_senha"]).fill(senha)
            page.locator(MAPPINGS["selectors"]["botao_entrar"]).click()
            
            # Aguardar a navegação após login
            print("  Aguardando navegação pós-login...")
            try:
                page.wait_for_load_state("load", timeout=15000)
            except:
                print("  ⚠ Timeout no 'load', continuando mesmo assim...")
            
            time.sleep(3)
            print("✓ Login realizado com sucesso!")

            # Aguardar página principal renderizar completamente
            print("Aguardando página principal renderizar...")
            time.sleep(2)

            # Navegar para URL do relatório
            print(f"Navegando para URL do relatório...")
            page.goto(URL_RELATORIO, wait_until="domcontentloaded")
            
            # Aguardar página carregar (sem waiting por networkidle que pode travar)
            print("  Aguardando página carregar...")
            try:
                page.wait_for_load_state("load", timeout=15000)
            except:
                print("  ⚠ Timeout no 'load', continuando mesmo assim...")
            
            time.sleep(3)
            print("✓ Página do relatório carregada!")

            # Aguardar o formulário estar pronto
            print("Aguardando formulário estar pronto...")
            time.sleep(3)

            # Clicar no botão "Gerar Relatório"
            print("Clicando no botão 'Gerar Relatório'...")
            try:
                page.locator(SEL_BOTAO_GERAR).wait_for(timeout=10000)
                paginas_antes = set(client.context.pages) if client.context else {page}
                page.locator(SEL_BOTAO_GERAR).click()

                if client.context:
                    inicio_popup = time.time()
                    while time.time() - inicio_popup < 30:
                        paginas_depois = set(client.context.pages)
                        novas_paginas = [p for p in paginas_depois if p not in paginas_antes]
                        if novas_paginas:
                            nova = novas_paginas[-1]
                            try:
                                nova.wait_for_load_state("domcontentloaded", timeout=15000)
                            except Exception:
                                pass
                            print(f"✓ Nova janela detectada após gerar relatório: {nova.url}")
                            break
                        time.sleep(0.4)
                print("✓ Botão 'Gerar Relatório' clicado!")
            except Exception as e:
                print(f"✗ Erro ao clicar no botão 'Gerar Relatório': {e}")
                if debug:
                    page.screenshot(path="debug_botao_gerar.png")
                    print("  Screenshot salvo em: debug_botao_gerar.png")
                return

            # Aguardar o modal/popup/iframe aparecer (pode demorar enquanto processa o relatório)
            print("Aguardando relatório aparecer (mesma página, popup/aba ou iframe)...")
            print("  (Isto pode levar alguns segundos enquanto o servidor processa)")
            pagina_relatorio = page
            frame_relatorio = None
            try:
                pagina_relatorio, frame_relatorio = _encontrar_superficie_relatorio(client, page, timeout_ms=30000)
                if frame_relatorio is None:
                    print(f"✓ Área do relatório detectada na página: {pagina_relatorio.url}")
                else:
                    print(f"✓ Área do relatório detectada em iframe: {frame_relatorio.url}")
                time.sleep(2)  # Aguardar a animação do modal e conteúdo carregar
            except Exception as e:
                print(f"⚠ Modal não detectado no tempo esperado: {e}")
                if debug:
                    print("  Procurando por elementos alternativas para debug...")
                    page.screenshot(path="debug_modal.png")
                    print("  Screenshot salvo em: debug_modal.png")
                    
                    # Tentar encontrar qualquer elemento que indique sucesso
                    try:
                        conteudo = page.content()
                        if "_bobarra" in conteudo:
                            print("  O elemento #_bobarra está no HTML mas não está visível")
                        if "relatório" in conteudo.lower() or "relatorio" in conteudo.lower():
                            print("  A palavra 'relatório' foi encontrada na página")
                    except:
                        pass
                # Continuar mesmo se não encontrar o seletor exato

            # Clicar no botão "Salvar relatório"
            print("Clicando no botão 'Salvar relatório'...")
            try:
                alvo = frame_relatorio if frame_relatorio is not None else pagina_relatorio
                instante_clique = time.time()
                caminho_final: Optional[Path] = None

                if client.context:
                    clicou = _clicar_botao_salvar(alvo, timeout_ms=12000)
                    if not clicou:
                        raise Exception("Nenhum seletor de 'Salvar relatório' funcionou.")

                    download = None
                    try:
                        download = client.context.wait_for_event("download", timeout=20000)
                    except Exception:
                        pass

                    if download is not None:
                        nome_sugerido = _sanitizar_nome_arquivo(download.suggested_filename or "")
                        nome_sugerido = _garantir_extensao_xls(nome_sugerido)
                        caminho_arquivo = _nome_unico(pasta_downloads / nome_sugerido)
                        download.save_as(str(caminho_arquivo))
                        caminho_final = caminho_arquivo
                        print(f"✓ Download salvo em: {caminho_arquivo.resolve()}")
                    else:
                        # Fallback para casos em que o site dispara download sem evento capturável.
                        time.sleep(4)
                        arquivo = _arquivo_mais_recente(pasta_downloads_tmp, apos=instante_clique)
                        if arquivo is not None:
                            destino = _nome_unico(pasta_downloads / _nome_relatorio_padrao())
                            shutil.copy2(arquivo, destino)
                            caminho_final = destino
                            print(f"✓ Download copiado para arquivo final: {destino.resolve()}")
                        else:
                            destino = _salvar_html_relatorio(alvo, pasta_downloads)
                            caminho_final = destino
                            print(f"✓ Relatório salvo a partir do HTML em: {destino.resolve()}")
                else:
                    clicou = _clicar_botao_salvar(alvo, timeout_ms=12000)
                    if not clicou:
                        raise Exception("Nenhum seletor de 'Salvar relatório' funcionou.")

                if caminho_final is not None:
                    _converter_html_para_xlsx_csv(caminho_final)
            except Exception as e:
                print(f"✗ Erro ao clicar no botão 'Salvar relatório': {e}")
                if debug:
                    try:
                        pagina_relatorio.screenshot(path="debug_salvar.png")
                    except Exception:
                        page.screenshot(path="debug_salvar.png")
                    print("  Screenshot salvo em: debug_salvar.png")
                return

            # Aguardar o download ser processado
            print("Aguardando processamento do relatório...")
            time.sleep(3)
            _limpar_pasta_temporaria(pasta_downloads_tmp)
            print("✓ Download do relatório concluído!")
            
        except Exception as e:
            print(f"✗ Erro durante download: {e}")
            raise


if __name__ == "__main__":
    usuario = os.getenv("LOGTUDO_USER", "ATUALIZARBI")
    senha = os.getenv("LOGTUDO_PASS", "sua_senha_aqui")
    baixar_relatorio_conhecimento(usuario, senha)
