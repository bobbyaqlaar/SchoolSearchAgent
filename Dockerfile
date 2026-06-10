# Match local .python-version (3.14)
FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency manifests first for layer caching (lockfile required by --frozen)
COPY pyproject.toml uv.lock /app/

RUN uv sync --frozen --no-dev --extra providers

# Copy application source
COPY . /app/

# Cron entry script
RUN chmod +x /app/run_school_db_agent_cron.sh \
    && mkdir -p /app/logs

# Daily run at 02:00; pipe output into docker logs
RUN echo "0 2 * * * root cd /app && ./run_school_db_agent_cron.sh > /proc/1/fd/1 2>&1" \
    > /etc/cron.d/dubai-cron-job \
    && chmod 0644 /etc/cron.d/dubai-cron-job \
    && crontab /etc/cron.d/dubai-cron-job

CMD ["sh", "-c", "printenv | grep -E 'OPENAI_|NEO4J_|LANGCHAIN_|ANTHROPIC_|GOOGLE_|XAI_|GROQ_' > /etc/environment && cron -f"]
