from functions import document_processor, embedding_processor
import config
import os
import shutil
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def delete_all_in_dir(path: str) -> None:
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        logger.info(f"Removendo: {item_path}")
        if os.path.isfile(item_path) or os.path.islink(item_path):
            os.unlink(item_path)  
        elif os.path.isdir(item_path):
            shutil.rmtree(item_path)

if __name__ == "__main__":

    PATH_VECTOR_STORE = config.PATH_VECTOR_STORE
    PATH_FILE = config.PATH_FILE

    # Configuração da classe DocumentProcessor
    docs = document_processor.DocumentProcessor(
        min_chunk_size=config.MIN_CHUNK_SIZE,
        max_chunk_size=config.MAX_CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP
    )
    embed = embedding_processor.EmbeddingProcessor()

    delete_all_in_dir(PATH_VECTOR_STORE)

    total_documents = 0
    total_chunks = 0

    for root, dirs, files in os.walk(PATH_FILE):
        if files:
            try:
                storing_path = root.replace(PATH_FILE, PATH_VECTOR_STORE)

                documents = docs.load_files(root)
                
                if not documents:
                    logger.warning(f"Nenhum documento válido encontrado na pasta {root}. Ignorando...")
                    continue
                
                total_documents += len(files)
                total_chunks += len(documents)
                
                vectorstore = embed.create_embeddings(documents, storing_path)

                logger.info(f"Sucesso ao processar os documentos da pasta: {root}")
                logger.info(f"Documentos processados: {len(files)}")
                logger.info(f"Chunks gerados: {len(documents)}")
            except Exception as error:
                logger.error(f"Erro ao processar os documentos da pasta {root}. Erro: {error}")
        else:
            logger.info(f"Nenhum arquivo encontrado na pasta {root}. Ignorando...")

    logger.info("Processamento finalizado!")
    logger.info(f"Total de documentos processados: {total_documents}")
    logger.info(f"Total de chunks gerados: {total_chunks}")