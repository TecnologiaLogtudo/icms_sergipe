import os
import shutil
import time
import unicodedata
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from Conectividade.playwright_vps_connect import PlaywrightVPSConfig, PlaywrightVPSClient
from automacao.config_loader import carregar_mapeamento
from automacao.login import realizar_login
from automacao.tratamento_planilha import (
    gerar_tabela_filtro_campos_st,
    remover_linha_final_bc_icms_st,
)
from automacao.smtp_notifier import enviar_alerta_campos_st

logger = logging.getLogger(__name__)

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
            logger.info("clique_salvar_relatorio_ok seletor=%s", seletor)
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


def _deve_limpar_downloads() -> bool:
    valor = os.getenv("LOGTUDO_CLEAN_DOWNLOADS", "true").strip().lower()
    return valor in {"1", "true", "t", "yes", "y", "sim", "s", "on"}


def _limpar_downloads_finais(pasta_downloads: Path, pasta_tmp: Path) -> None:
    """
    Remove arquivos da pasta de downloads ao fim do ciclo.
    Mantém apenas diretórios e arquivos de controle (ex: .gitkeep).
    """
    for item in pasta_downloads.glob("*"):
        if item == pasta_tmp:
            continue
        if item.is_dir():
            continue
        if item.name.lower() in {".gitkeep"}:
            continue
        try:
            item.unlink()
        except Exception as exc:
            logger.warning("falha_remover_arquivo_download nome=%s detalhe=%s", item.name, exc)


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
        logger.warning("pandas_nao_instalado conversao_xlsx_csv_pulada")
        return

    try:
        tabelas = pd.read_html(caminho_arquivo, flavor=["lxml", "bs4"])
    except Exception as exc:
        logger.warning("falha_converter_html_para_tabela detalhe=%s", exc)
        return

    if not tabelas:
        logger.warning("nenhuma_tabela_encontrada_no_html")
        return

    def _normalizar_txt(valor: object) -> str:
        texto = "" if valor is None else str(valor)
        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(c for c in texto if not unicodedata.combining(c))
        return texto.strip().lower()

    headers_esperados = {
        "emissao",
        "ctrc",
        "cliente",
        "peso",
        "remetente",
        "c. pedido",
        "destinatario",
        "valor nota",
        "cfop",
        "cst",
        "frete valor",
        "bc st",
        "aliquota icmsst",
        "icms st",
    }

    tabela = None
    melhor_score = -1
    for candidata in tabelas:
        score = 0

        colunas_norm = {_normalizar_txt(c) for c in list(candidata.columns)}
        score += len(headers_esperados.intersection(colunas_norm))

        if not candidata.empty:
            primeira_linha_norm = {_normalizar_txt(v) for v in candidata.iloc[0].tolist()}
            score += len(headers_esperados.intersection(primeira_linha_norm))

        # privilegia tabela larga (a de dados tem 14 colunas)
        if candidata.shape[1] >= 10:
            score += 3

        if score > melhor_score:
            melhor_score = score
            tabela = candidata.copy()

    if tabela is None:
        logger.warning("nenhuma_tabela_compativel_identificada")
        return

    # Em muitos relatórios, o header vem como primeira linha de dados.
    if not tabela.empty:
        primeira_linha = [str(v).strip() for v in tabela.iloc[0].tolist()]
        primeira_linha_norm = {_normalizar_txt(v) for v in primeira_linha}
        if len(headers_esperados.intersection(primeira_linha_norm)) >= 5:
            tabela.columns = primeira_linha
            tabela = tabela.iloc[1:].reset_index(drop=True)

    if tabela.empty:
        logger.warning("tabela_convertida_vazia exportacao_pulada")
        return

    tabela = remover_linha_final_bc_icms_st(tabela)
    tabela_filtro_st = gerar_tabela_filtro_campos_st(tabela)

    caminho_xlsx = _nome_unico(caminho_arquivo.with_name(f"{caminho_arquivo.stem}_convertido.xlsx"))
    caminho_csv = _nome_unico(caminho_arquivo.with_name(f"{caminho_arquivo.stem}_convertido.csv"))

    with pd.ExcelWriter(caminho_xlsx, engine="openpyxl") as writer:
        tabela.to_excel(writer, sheet_name="dados", index=False)
        if not tabela_filtro_st.empty:
            tabela_filtro_st.to_excel(writer, sheet_name="filtro_campos_st", index=False)
    tabela.to_csv(caminho_csv, index=False, encoding="utf-8-sig", sep=";")

    logger.info("conversao_concluida arquivo=%s", caminho_xlsx.resolve())
    logger.info("conversao_concluida arquivo=%s", caminho_csv.resolve())
    if not tabela_filtro_st.empty:
        logger.info("aba_adicional_criada nome=filtro_campos_st")
        enviar_alerta_campos_st(tabela_filtro_st, arquivo_origem=caminho_arquivo)


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
    logger.info("pasta_downloads_configurada caminho=%s", pasta_downloads.resolve())

    with PlaywrightVPSClient(config) as client:
        page = client.page

        try:
            # Realizar login
            logger.info("realizando_login")
            page.goto(URL_LOGIN, wait_until="domcontentloaded")
            page.locator(MAPPINGS["selectors"]["campo_usuario"]).fill(usuario)
            page.locator(MAPPINGS["selectors"]["campo_senha"]).fill(senha)
            page.locator(MAPPINGS["selectors"]["botao_entrar"]).click()
            
            # Aguardar a navegação após login
            logger.info("aguardando_navegacao_pos_login")
            try:
                page.wait_for_load_state("load", timeout=15000)
            except:
                logger.warning("timeout_load_pos_login continuando")
            
            time.sleep(3)
            logger.info("login_realizado_com_sucesso")

            # Aguardar página principal renderizar completamente
            logger.info("aguardando_pagina_principal_renderizar")
            time.sleep(2)

            # Navegar para URL do relatório
            logger.info("navegando_para_url_relatorio")
            page.goto(URL_RELATORIO, wait_until="domcontentloaded")
            
            # Aguardar página carregar (sem waiting por networkidle que pode travar)
            logger.info("aguardando_pagina_relatorio_carregar")
            try:
                page.wait_for_load_state("load", timeout=15000)
            except:
                logger.warning("timeout_load_relatorio continuando")
            
            time.sleep(3)
            logger.info("pagina_relatorio_carregada")

            # Aguardar o formulário estar pronto
            logger.info("aguardando_formulario_pronto")
            time.sleep(3)

            # Clicar no botão "Gerar Relatório"
            logger.info("clicando_botao_gerar_relatorio")
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
                            logger.info("nova_janela_detectada_apos_gerar_relatorio url=%s", nova.url)
                            break
                        time.sleep(0.4)
                logger.info("botao_gerar_relatorio_clicado")
            except Exception as e:
                logger.exception("erro_clicar_botao_gerar_relatorio detalhe=%s", e)
                if debug:
                    page.screenshot(path="debug_botao_gerar.png")
                    logger.info("screenshot_salvo arquivo=debug_botao_gerar.png")
                return

            # Aguardar o modal/popup/iframe aparecer (pode demorar enquanto processa o relatório)
            logger.info("aguardando_superficie_relatorio popup_aba_iframe")
            pagina_relatorio = page
            frame_relatorio = None
            try:
                pagina_relatorio, frame_relatorio = _encontrar_superficie_relatorio(client, page, timeout_ms=30000)
                if frame_relatorio is None:
                    logger.info("area_relatorio_detectada_pagina url=%s", pagina_relatorio.url)
                else:
                    logger.info("area_relatorio_detectada_iframe url=%s", frame_relatorio.url)
                time.sleep(2)  # Aguardar a animação do modal e conteúdo carregar
            except Exception as e:
                logger.warning("modal_relatorio_nao_detectado detalhe=%s", e)
                if debug:
                    logger.info("debug_modal_ativo procurando_elementos")
                    page.screenshot(path="debug_modal.png")
                    logger.info("screenshot_salvo arquivo=debug_modal.png")
                    
                    # Tentar encontrar qualquer elemento que indique sucesso
                    try:
                        conteudo = page.content()
                        if "_bobarra" in conteudo:
                            logger.info("elemento_bobarra_presente_html_nao_visivel")
                        if "relatório" in conteudo.lower() or "relatorio" in conteudo.lower():
                            logger.info("palavra_relatorio_encontrada_na_pagina")
                    except:
                        pass
                # Continuar mesmo se não encontrar o seletor exato

            # Clicar no botão "Salvar relatório"
            logger.info("clicando_botao_salvar_relatorio")
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
                        logger.info("download_salvo caminho=%s", caminho_arquivo.resolve())
                    else:
                        # Fallback para casos em que o site dispara download sem evento capturável.
                        time.sleep(4)
                        arquivo = _arquivo_mais_recente(pasta_downloads_tmp, apos=instante_clique)
                        if arquivo is not None:
                            destino = _nome_unico(pasta_downloads / _nome_relatorio_padrao())
                            shutil.copy2(arquivo, destino)
                            caminho_final = destino
                            logger.info("download_copiado_para_arquivo_final caminho=%s", destino.resolve())
                        else:
                            destino = _salvar_html_relatorio(alvo, pasta_downloads)
                            caminho_final = destino
                            logger.info("relatorio_salvo_a_partir_html caminho=%s", destino.resolve())
                else:
                    clicou = _clicar_botao_salvar(alvo, timeout_ms=12000)
                    if not clicou:
                        raise Exception("Nenhum seletor de 'Salvar relatório' funcionou.")

                if caminho_final is not None:
                    _converter_html_para_xlsx_csv(caminho_final)
            except Exception as e:
                logger.exception("erro_clicar_botao_salvar_relatorio detalhe=%s", e)
                if debug:
                    try:
                        pagina_relatorio.screenshot(path="debug_salvar.png")
                    except Exception:
                        page.screenshot(path="debug_salvar.png")
                    logger.info("screenshot_salvo arquivo=debug_salvar.png")
                return

            # Aguardar o download ser processado
            logger.info("aguardando_processamento_relatorio")
            time.sleep(3)
            _limpar_pasta_temporaria(pasta_downloads_tmp)
            logger.info("download_relatorio_concluido")
            
        except Exception as e:
            logger.exception("erro_durante_download detalhe=%s", e)
            raise
        finally:
            _limpar_pasta_temporaria(pasta_downloads_tmp)
            if _deve_limpar_downloads():
                _limpar_downloads_finais(pasta_downloads, pasta_downloads_tmp)
                logger.info("limpeza_pos_ciclo_downloads_concluida")


if __name__ == "__main__":
    usuario = os.getenv("LOGTUDO_USER", "ATUALIZARBI")
    senha = os.getenv("LOGTUDO_PASS", "sua_senha_aqui")
    baixar_relatorio_conhecimento(usuario, senha)
