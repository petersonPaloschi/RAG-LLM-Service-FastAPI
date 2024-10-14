import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

import config

logger = logging.getLogger(__name__)

class EmbeddingProcessor:
    """
    Classe para processar embeddings e interagir com os serviços Azure OpenAI.
    """

    def __init__(self, vector_store_path: str = config.PATH_VECTOR_STORE) -> None:
        logging.basicConfig(
            level=logging.DEBUG if config.LANGCHAIN_DEBUG else logging.INFO
        )
        logging.getLogger("faiss.loader").setLevel(logging.WARNING)

        self.vector_store_path = vector_store_path
        self.prompt_template = self._create_prompt_template()
        self.llm_api = self._initialize_azure_chat()
        self.embed_model = self._initialize_azure_embeddings()

    @staticmethod
    def _create_prompt_template() -> PromptTemplate:
        """
        Cria um template de prompt para a cadeia principal.
        """
        prompt_system = PromptTemplate(
            input_variables=[], template=config.PROMPT_TEMPLATE
        )

        context_prompt = PromptTemplate(
            input_variables=["context", "question"],
            template="""
                **Contexto:**
                {context}

                **Pergunta:**
                {question}

                **Resposta:**
                """,
        )

        combined_prompt = PromptTemplate(
            input_variables=["context", "question"],
            template=prompt_system.template + "\n" + context_prompt.template,
        )

        return combined_prompt

    def _initialize_azure_chat(self) -> AzureChatOpenAI:
        """
        Inicializa a API AzureChatOpenAI.
        """
        return AzureChatOpenAI(
            api_key=config.AZURE_OPENAI_API_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            azure_deployment=config.AZURE_OPENAI_MODEL,
            temperature=config.AZURE_GPT_TEMPERATURE
        )

    def _initialize_azure_embeddings(self) -> AzureOpenAIEmbeddings:
        """
        Inicializa o modelo de embeddings do Azure.
        """

        return AzureOpenAIEmbeddings(
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_API_KEY,
            azure_deployment=config.AZURE_EMBEDDINGS_DEPLOYMENT_NAME,
            model=config.AZURE_EMBEDDING_MODEL_NAME,
            chunk_size=config.EMBED_CHUNK_SIZE
        )

    def create_embeddings(
        self, documents: List[Document], storing_path: str
        ) -> Optional[FAISS]:
        """
        Cria embeddings a partir de documentos e os salva localmente.
        """
        try:
            vectorstore = FAISS.from_documents(documents, self.embed_model)
            vectorstore.save_local(storing_path)
            return vectorstore
        except Exception as e:
            logger.error("Erro ao criar embeddings: %s", e)
            return None

    @lru_cache(maxsize=None)
    def load_embeddings(self, embedding_path: str) -> Optional[FAISS]:
        """
        Carrega embeddings de um caminho local.
        """
        index_path = os.path.join(embedding_path, "index.faiss")
        if os.path.exists(index_path):
            try:
                return FAISS.load_local(
                    embedding_path,
                    self.embed_model,
                    allow_dangerous_deserialization=True
                )
            except Exception as e:
                logger.error("Erro ao carregar embeddings: %s", e)
        else:
            logger.warning(
                "Arquivo de índice não encontrado no caminho: %s", index_path
            )
        return None

    def create_chain(self, path: str) -> Optional[RetrievalQA]:
        """
        Cria uma cadeia de QA usando embeddings no caminho fornecido.
        """
        full_path = os.path.normpath(os.path.join(self.vector_store_path, path))
        
        logger.warning(
            "Criando chain pelo diretorio %s", full_path
        )

        if not os.path.exists(full_path):
            logger.error(
                "Falha ao criar a cadeia: Diretório não existe -> [%s]", full_path
            )
            return None

        vectorstore = self.load_embeddings(embedding_path=full_path)
        if vectorstore is None:
            return None

        retriever = vectorstore.as_retriever(
            search_type="mmr", search_kwargs={"k": 20, "lambda_mult": 0.5}
        )

        return self.load_qa_chain(retriever)

    def load_qa_chain(self, retriever: Any) -> RetrievalQA:
        """
        Carrega uma cadeia de QA com o retriever fornecido.
        """
        return RetrievalQA.from_chain_type(
            llm=self.llm_api,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True,
            chain_type_kwargs={"prompt": self.prompt_template},
        )

    @staticmethod
    def _document_to_dict(doc: Document) -> Dict[str, Any]:
        """
        Converte um objeto de documento em um dicionário.
        """
        return {
            "page_content": doc.page_content,
            "metadata": {
                "title": doc.metadata.get("title", "Sem título"),
                "file_name": os.path.basename(doc.metadata.get("source", "N/A")),
                "author": doc.metadata.get("author", "N/A"),
                "page": int(doc.metadata.get("page", "0")),
            },
        }

    def get_response(self, query: str, chain: RetrievalQA) -> Dict[str, Any]:
        """
        Obtém uma resposta da cadeia de QA para a consulta fornecida.
        """
        try:
            response = chain({"query": query})
            response_content = response.get("result", str(response))

            citations = [
                self._document_to_dict(doc)
                for doc in response["source_documents"]
            ]

            return {
                "tool": citations,
                "messages": [
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": response_content},
                ],
            }
        except Exception as e:
            logger.error("Erro ao obter resposta: %s", e)
            return {
                "tool": [],
                "messages": [
                    {"role": "user", "content": query},
                    {
                        "role": "assistant",
                        "content": (
                            "Peço desculpas, mas encontrei um erro ao processar "
                            "sua consulta. Poderia tentar reformular sua pergunta "
                            "ou perguntar outra coisa?"
                        ),
                    },
                ],
            }
