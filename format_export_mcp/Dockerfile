FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FORMAT_EXPORT_HOST=0.0.0.0 \
    FORMAT_EXPORT_PORT=8000 \
    FORMAT_EXPORT_STORAGE_DIR=/app/format_export_mcp/storage/exports

WORKDIR /app

COPY format_export_mcp/requirements.txt /app/format_export_mcp/requirements.txt
RUN pip install --no-cache-dir -r /app/format_export_mcp/requirements.txt

COPY format_export_mcp /app/format_export_mcp
RUN mkdir -p /app/format_export_mcp/storage/exports

EXPOSE 8000

CMD ["python", "-m", "format_export_mcp.server_streamable_http"]
