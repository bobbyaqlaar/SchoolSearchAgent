FROM gcr.io/google.com/cloudsdktool/cloud-sdk:slim

WORKDIR /app

RUN apt-get update -qq \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv \
    && pip3 install --break-system-packages --no-cache-dir fastapi "uvicorn[standard]" httpx \
    && rm -rf /var/lib/apt/lists/*

COPY main.py /app/main.py

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
