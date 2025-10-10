FROM python:3.11-slim

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Garantir binário padrão do ffmpeg disponível via env
ENV FFMPEG_BINARY=ffmpeg

# Copia requirements
COPY requirements.txt requirements-dev.txt ./

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia código
COPY . .

# Define PYTHONPATH
ENV PYTHONPATH=/app

# Expõe porta
EXPOSE 8000

# Comando padrão
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
