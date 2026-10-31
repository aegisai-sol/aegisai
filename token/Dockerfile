FROM node:20-slim
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev || npm install --omit=dev
COPY scripts ./scripts
COPY deployments ./deployments
ENV MAINNET=1 PORT=8080 SOLANA_KEYPAIR=/tmp/mint.json
# Railway secret MINT_AUTH_JSON = keypair JSON array (set in dashboard, never commit)
CMD ["sh","-c","echo \"$MINT_AUTH_JSON\" > $SOLANA_KEYPAIR && chmod 600 $SOLANA_KEYPAIR && node scripts/claim-server.mjs"]
