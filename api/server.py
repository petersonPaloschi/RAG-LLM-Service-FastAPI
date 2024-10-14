from fastapi import FastAPI, HTTPException, Request, status, Depends, Security
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from typing import Any
from functions.embedding_processor import EmbeddingProcessor

import config
import json
import time
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = config.API_KEY
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

class RateLimiter:
    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.requests = {}

    async def is_rate_limited(self, client_id: str) -> bool:
        now = time.time()
        window_start = now - 60
        self.requests.setdefault(client_id, [])
        self.requests[client_id] = [timestamp for timestamp in self.requests[client_id] if timestamp > window_start]

        if len(self.requests[client_id]) >= self.requests_per_minute:
            logger.warning(f"Limite de requisições excedido para o cliente: {client_id}")
            return True

        self.requests[client_id].append(now)
        return False

rate_limiter = RateLimiter(requests_per_minute=60)

app = FastAPI()

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == API_KEY:
        return api_key_header
    else:
        logger.warning("Tentativa de uso de chave de API inválida")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Credenciais inválidas"
        )
    
class ChatRequest(BaseModel):
    system: str = Field(..., description="Sistema de mensagem")
    department: str = Field(..., description="Departamento")
    typology: str = Field(..., description="Tipologia")
    query: str = Field(..., description="Consulta do usuário")

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    if await rate_limiter.is_rate_limited(client_ip):
        logger.warning(f"Limite de requisições excedido para o IP: {client_ip}")
        return JSONResponse(status_code=429, content={"error": "Limite de requisições excedido"})
    response = await call_next(request)
    return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando a aplicação")
    try:
        with open("api/chains.json", "r") as file:
            departments_chains = json.load(file)
        logger.info("chains.json carregado com sucesso")
    except Exception as e:
        logger.error(f"Erro ao carregar departments.json: {e}")
        departments_chains = {}

    embed = EmbeddingProcessor()
    app.state.embed = embed

    app.state.chains = {
        dept.upper(): {
            typology.upper(): embed.create_chain(path)
            for typology, path in typologies.items()
        }
        for dept, typologies in departments_chains.items()
    }
    logger.info("Embed e chains inicializados")
    yield
    logger.info("Aplicação finalizada")

app = FastAPI(lifespan=lifespan)

async def get_chain(department: str, typology: str) -> Any:
    department_chains = app.state.chains.get(department)
    
    if not department_chains:
        logger.error(f"Departamento não encontrado: {department}")
        raise HTTPException(status_code=404, detail="Departamento não encontrado")
    chain = department_chains.get(typology)
    if not chain:
        logger.error(f"Tipologia não encontrada: {typology} no departamento: {department}")
        raise HTTPException(status_code=404, detail="Tipologia não encontrada")
    return chain

@app.post("/chat")
async def chat(request: ChatRequest, api_key: str = Depends(get_api_key)):
    logger.info(f"Requisição recebida para o departamento: {request.department}, tipologia: {request.typology}")
    try:
        chain = await get_chain(request.department.upper(), request.typology.upper())
        if not chain:
            logger.error("Chain não disponível")
            raise HTTPException(status_code=500, detail="Chain não disponível")
        
        response = await asyncio.to_thread(app.state.embed.get_response, request.query, chain)
        logger.info("Resposta gerada com sucesso")
        return JSONResponse(content=response)
    except HTTPException as e:
        logger.error(f"HTTPException: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Ocorreu uma exceção: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Ocorreu um erro: {str(e)}"}
        )
    
@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: HTTPException):
    logger.warning(f"404 Não Encontrado: {request.url}")
    return JSONResponse(
        status_code=404,
        content={"message": "Rota não encontrada"}
    )