# RAG-LLM-Service-FastAPI

Este repositório implementa um sistema de Retrieval-Augmented Generation (RAG) utilizando FAISS para busca vetorial, com embeddings gerados pela API da OpenAI. A aplicação é construída em FastAPI, proporcionando uma interface rápida e eficiente.

## Passo a Passo para Execução

### 1. Configurar as Chaves de API

- Acesse o arquivo `config.py` e preencha suas chaves de API.

### 2. Executar o Servidor

- Rode o script `run server.bat` para iniciar o servidor.

### Parâmetros da API

- **Método:** POST
- **Body (JSON):**
  ```json
  {
    "system": "",
    "department": "CDC",
    "typology": "NORMAS",
    "query": "QUAL A FINALIDADE DO CDC?"
  }
  ```
- **Headers:**
  - `X-API-Key`: SUA_API_KEY (deve ser configurada no `config.py`)

### Utilização de Documentos Customizados

1. Acesse `api/chains.json` e configure as novas chains, seguindo o exemplo já existente.
2. Crie os diretórios em `files/docs` e coloque os documentos desejados ali dentro. Você pode criar pastas e subpastas, mas não se esqueça de ajustar o `chains.json` para refletir a nova estrutura.
3. Depois de adicionar os documentos, rode o script `ingest documents.bat`.
4. Finalizada a ingestão, rode novamente o `run server.bat` para reiniciar o servidor com os novos documentos.
