# AegisAI peer miner/coordinator node (stdlib-only; no keys, no Solana submit).
FROM python:3.12-slim
WORKDIR /app
COPY aegis_miner ./aegis_miner
COPY main.py config.yaml ./
ENV AEGIS_DATA=/data PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8787
CMD ["python3", "-m", "aegis_miner.coordinator", "8787"]
