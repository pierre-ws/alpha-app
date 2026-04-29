import os
import logging
from contextlib import asynccontextmanager

import asyncpg
from azure.identity.aio import ManagedIdentityCredential
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

PGHOST = os.environ["PGHOST"]
PGDATABASE = os.environ["PGDATABASE"]
PGUSER = os.environ["PGUSER"]

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = await get_connection()
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        await conn.execute("""
            INSERT INTO items (name)
            SELECT unnest(ARRAY['foo', 'bar', 'baz'])
            WHERE NOT EXISTS (SELECT 1 FROM items)
        """)
        log.info("schema initialized")
    finally:
        await conn.close()
    yield


app = FastAPI(title="alpha-app backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
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


class ItemCreate(BaseModel):
    name: str


@app.post("/api/items", status_code=201)
async def create_item(body: ItemCreate):
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="name cannot be empty")
    try:
        conn = await get_connection()
        try:
            row = await conn.fetchrow(
                "INSERT INTO items (name) VALUES ($1) RETURNING id, name, created_at",
                body.name.strip(),
            )
            return dict(row)
        finally:
            await conn.close()
    except Exception as exc:
        log.exception("database error")
        raise HTTPException(status_code=503, detail=str(exc))


@app.delete("/api/items/{item_id}", status_code=204)
async def delete_item(item_id: int):
    try:
        conn = await get_connection()
        try:
            result = await conn.execute("DELETE FROM items WHERE id = $1", item_id)
            if result == "DELETE 0":
                raise HTTPException(status_code=404, detail="item not found")
        finally:
            await conn.close()
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("database error")
        raise HTTPException(status_code=503, detail=str(exc))
