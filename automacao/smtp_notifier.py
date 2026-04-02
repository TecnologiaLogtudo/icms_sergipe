"""
Envio de notificações por e-mail via SMTP após o tratamento da planilha.
"""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import pandas as pd


@dataclass
class SMTPConfig:
    host: str
    port: int
    user: str
    password: str
    from_email: str
    to_emails: list[str]
    use_tls: bool = True
    use_ssl: bool = False
    from_name: str = "Automacao Logtudo"
    enabled: bool = False


def _to_bool(valor: str | None, default: bool = False) -> bool:
    if valor is None:
        return default
    return valor.strip().lower() in {"1", "true", "yes", "sim", "on"}


def carregar_config_smtp() -> SMTPConfig:
    to_raw = os.getenv("SMTP_TO", "")
    to_emails = [e.strip() for e in to_raw.replace(";", ",").split(",") if e.strip()]

    return SMTPConfig(
        host=os.getenv("SMTP_HOST", "").strip(),
        port=int(os.getenv("SMTP_PORT", "587").strip()),
        user=os.getenv("SMTP_USER", "").strip(),
        password=os.getenv("SMTP_PASS", "").strip(),
        from_email=os.getenv("SMTP_FROM_EMAIL", "").strip() or os.getenv("SMTP_USER", "").strip(),
        to_emails=to_emails,
        use_tls=_to_bool(os.getenv("SMTP_USE_TLS"), default=True),
        use_ssl=_to_bool(os.getenv("SMTP_USE_SSL"), default=False),
        from_name=os.getenv("SMTP_FROM_NAME", "Automacao Logtudo").strip(),
        enabled=_to_bool(os.getenv("SMTP_ENABLED"), default=False),
    )


def _config_esta_valida(config: SMTPConfig) -> tuple[bool, str]:
    if not config.enabled:
        return False, "SMTP desabilitado (SMTP_ENABLED=false)."
    if not config.host:
        return False, "SMTP_HOST não configurado."
    if not config.port:
        return False, "SMTP_PORT não configurado."
    if not config.user:
        return False, "SMTP_USER não configurado."
    if not config.password:
        return False, "SMTP_PASS não configurado."
    if not config.from_email:
        return False, "SMTP_FROM_EMAIL não configurado."
    if not config.to_emails:
        return False, "SMTP_TO não configurado."
    if config.use_ssl and config.use_tls:
        return False, "Use apenas um entre SMTP_USE_SSL=true e SMTP_USE_TLS=true."
    return True, ""


def _montar_corpo_html(df: pd.DataFrame, arquivo_origem: Path | None) -> str:
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    origem_txt = str(arquivo_origem) if arquivo_origem else "não informado"
    tabela_html = df.to_html(index=False, border=1, justify="left")
    return f"""
<html>
  <body>
    <p><b>ATENÇÃO !!</b><br>
       Os Seguintes CTEs foram enviados a SEFAZ sem o destaque do ICMS devido.<br><br>
       Equipe faturamento, verificar com brevidade !!</p>
    <p><b>Data/hora:</b> {timestamp}<br>
       <b>Arquivo:</b> {origem_txt}<br>
       <b>Total de registros:</b> {len(df)}</p>
    {tabela_html}
  </body>
</html>
""".strip()


def _montar_corpo_texto(df: pd.DataFrame, arquivo_origem: Path | None) -> str:
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    origem_txt = str(arquivo_origem) if arquivo_origem else "não informado"
    previa = df.head(20).to_string(index=False)
    sufixo = ""
    if len(df) > 20:
        sufixo = f"\n\n... e mais {len(df) - 20} registros."

    return (
        "ATENÇÃO !!\n"
        "Os Seguintes CTEs foram enviados a SEFAZ sem o destaque do ICMS devido.\n\n"
        "Equipe faturamento, verificar com brevidade !!\n\n"
        f"Data/hora: {timestamp}\n"
        f"Arquivo: {origem_txt}\n"
        f"Total de registros: {len(df)}\n\n"
        f"{previa}{sufixo}\n"
    )


def enviar_alerta_campos_st(
    tabela_filtro_st: pd.DataFrame,
    arquivo_origem: Path | None = None,
) -> bool:
    """
    Envia e-mail com os dados encontrados na tabela de filtro de campos ST.

    Retorna True quando envia com sucesso; False em qualquer cenário sem envio.
    """
    if tabela_filtro_st.empty:
        print("ℹ Nenhum registro para notificar por e-mail.")
        return False

    config = carregar_config_smtp()
    valido, motivo = _config_esta_valida(config)
    if not valido:
        print(f"ℹ E-mail não enviado: {motivo}")
        return False

    subject = os.getenv(
        "SMTP_SUBJECT",
        f"[Logtudo] Alerta ST - {len(tabela_filtro_st)} registro(s)",
    ).strip()

    mensagem = EmailMessage()
    mensagem["Subject"] = subject
    mensagem["From"] = f"{config.from_name} <{config.from_email}>"
    mensagem["To"] = ", ".join(config.to_emails)
    mensagem.set_content(_montar_corpo_texto(tabela_filtro_st, arquivo_origem))
    mensagem.add_alternative(_montar_corpo_html(tabela_filtro_st, arquivo_origem), subtype="html")

    csv_bytes = tabela_filtro_st.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
    mensagem.add_attachment(
        csv_bytes,
        maintype="text",
        subtype="csv",
        filename="filtro_campos_st.csv",
    )

    try:
        if config.use_ssl:
            with smtplib.SMTP_SSL(config.host, config.port, timeout=30) as smtp:
                smtp.login(config.user, config.password)
                smtp.send_message(mensagem)
        else:
            with smtplib.SMTP(config.host, config.port, timeout=30) as smtp:
                if config.use_tls:
                    smtp.starttls()
                smtp.login(config.user, config.password)
                smtp.send_message(mensagem)
    except Exception as exc:
        print(f"✗ Falha ao enviar e-mail SMTP: {exc}")
        return False

    print(f"✓ E-mail SMTP enviado para: {', '.join(config.to_emails)}")
    return True
