FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY Scrapling-main /app/Scrapling-main
COPY backend/requirements.txt /app/backend/requirements.txt

RUN pip install --upgrade pip \
    && cd /app/backend \
    && pip install -r requirements.txt \
    && scrapling install

COPY backend /app/backend

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/backend", "--reload-dir", "/app/Scrapling-main"]
