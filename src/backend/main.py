import os
import logging

import asyncpg
from azure.identity.aio import ManagedIdentityCredential
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="alpha-app backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

PGHOST = os.environ["PGHOST"]
PGDATABASE = os.environ["PGDATABASE"]
PGUSER = os.environ["PGUSER"]

# Azure PostgreSQL Flexible Server requires an Entra ID token as the password.
# The token is obtained automatically from the workload identity projected volume
# injected by the AKS Workload Identity webhook (AZURE_FEDERATED_TOKEN_FILE).
POSTGRES_AAD_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"


async def get_token() -> str:
    async with ManagedIdentityCredential() as credential:
        token = await credential.get_token(POSTGRES_AAD_SCOPE)
        return token.token


async def get_connection() -> asyncpg.Connection:
    password = await get_token()
    return await asyncpg.connect(
        host=PGHOST,
        database=PGDATABASE,
        user=PGUSER,
        password=password,
        ssl="require",
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/items")
async def list_items():
    try:
        conn = await get_connection()
        try:
            rows = await conn.fetch("SELECT id, name, created_at FROM items ORDER BY created_at DESC LIMIT 20")
            return [dict(r) for r in rows]
        finally:
            await conn.close()
    except Exception as exc:
        log.exception("database error")
        raise HTTPException(status_code=503, detail=str(exc))
