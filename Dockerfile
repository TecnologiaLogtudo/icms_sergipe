# Base de build para projetos Python + Playwright em VPS
FROM mcr.microsoft.com/playwright/python:v1.58.0-noble

WORKDIR /app

# Dependencias Python
COPY requirements-playwright-vps.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Garante binarios do Chromium
RUN playwright install chromium

# Copie seu projeto (ajuste conforme sua estrutura)
COPY . /app

# Permissoes para usuario nao-root (pwuser ja existe na imagem base)
RUN mkdir -p /app/data && chown -R pwuser:pwuser /app
USER pwuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_HEADLESS=true

EXPOSE 8000

# Ajuste este comando no projeto de destino
CMD ["python", "-m", "http.server", "8000"]
