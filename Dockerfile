FROM python:3.12-slim
 
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=America/Sao_Paulo
 
RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata ca-certificates \
 && rm -rf /var/lib/apt/lists/*
 
WORKDIR /app
 
COPY requirements.txt .
RUN pip install -r requirements.txt
 
COPY src/ ./src/
COPY bot/ ./bot/
COPY jobs/ ./jobs/
COPY scripts/ ./scripts/
 
RUN useradd --create-home --uid 10001 botuser && chown -R botuser:botuser /app
USER botuser
 
CMD ["python", "-u", "bot/discord_bot.py"]
