FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FORMAT_EXPORT_HOST=0.0.0.0 \
    FORMAT_EXPORT_PORT=8000 \
    FORMAT_EXPORT_STORAGE_DIR=/app/format_export_mcp/storage/exports \
    HOME=/home/appuser

WORKDIR /app

# 安装 pandoc + LibreOffice + 中文字体
RUN apt-get update && apt-get install -y --no-install-recommends \
    pandoc \
    libreoffice \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    libreoffice-java-common \
    fonts-noto-cjk \
    fonts-wqy-zenhei \
    fonts-wqy-microhei \
    fontconfig \
    && fc-cache -fv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system appuser && useradd --system --gid appuser --create-home appuser

COPY pyproject.toml /app/pyproject.toml
COPY format_export_mcp /app/format_export_mcp

RUN pip install --no-cache-dir .

RUN mkdir -p /app/format_export_mcp/storage/exports \
    /tmp/libreoffice-profile \
    && chown -R appuser:appuser /app /tmp/libreoffice-profile /home/appuser

USER appuser

EXPOSE 8000

CMD ["python", "-m", "format_export_mcp.server_streamable_http"]
