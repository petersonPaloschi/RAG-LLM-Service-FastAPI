# functions/document_processor.py

import logging
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyPDF2 import PdfReader
import requests
from bs4 import BeautifulSoup
from dateutil import parser

from langchain_community.document_loaders import (
    CSVLoader,
    TextLoader,
    UnstructuredFileLoader,
)
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

import config

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Classe para processamento de documentos, incluindo carregamento,
    pré-processamento, extração de textos e metadados.
    """

    def __init__(
        self,
        min_chunk_size: int = config.MIN_CHUNK_SIZE,
        max_chunk_size: int = config.MAX_CHUNK_SIZE,
        chunk_overlap: int = config.CHUNK_OVERLAP,
    ) -> None:
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap

    def _get_file_name(self, path: str) -> str:
        return Path(path).stem

    def _normalize_text(self, text: str) -> str:
        """
        Normaliza o texto removendo caracteres especiais e espaços extras.
        """
        text = unicodedata.normalize("NFKD", text).encode(
            "ASCII", "ignore"
        ).decode("ASCII")
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\.{2,}", ".", text)
        text = re.sub(r"\r+", "\n", text)
        text = re.sub(r"\t+", " ", text)
        text = re.sub(r"\n{2,}", "\n\n", text)
        text = re.sub(
            r"([.!?])\s*([A-ZÀÁÂÃÉÊÍÓÔÕÚÇ])", r"\1\n\2", text
        )
        text = re.sub(r"(\d+),(\d+)", r"\1.\2", text)
        text = re.sub(r"(\w+)-\s+(\w+)", r"\1\2", text)
        return text.strip()

    def _preprocess_pdf(self, content: str) -> str:
        return re.sub(r"\f", "\n\n", content)

    def _preprocess_csv(self, content: str) -> str:
        return re.sub(r"^.*?(\w+,\w+)", r"\1", content, flags=re.DOTALL)

    def _preprocess_txt(self, content: str) -> str:
        return re.sub(r"\n\s*\n", "\n\n", content)

    def _filter_content(self, content: str) -> str:
        """
        Filtra o conteúdo removendo linhas curtas ou irrelevantes.
        """
        lines = [
            line.strip() for line in content.split("\n") if len(line.strip()) > 10
        ]
        return "\n".join(lines)

    def _clean_metadata(self, doc: Document) -> Document:
        """
        Limpa e formata os metadados do documento.
        """
        doc.metadata["file_path"] = self._get_file_name(
            doc.metadata.get("file_path", "")
        )
        doc.metadata["page"] = int(doc.metadata.get("page_number", 1))
        doc.metadata["total_pages"] = int(doc.metadata.get("total_pages", 1))
        return doc

    def _fetch_link_content(self, url: str) -> Optional[str]:
        """
        Busca e extrai o texto de um link HTTP.
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                " AppleWebKit/537.36 (KHTML, like Gecko)"
                " Chrome/110.0.5481.100 Safari/537.36"
            )
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            desired_tags = soup.find_all(["p", "h1", "h2"])
            text = " ".join(
                tag.get_text(separator=" ", strip=True) for tag in desired_tags
            )

            text = self._normalize_text(text) 
            text = self._filter_content(text) 

            return text
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao acessar {url}: {e}")
            return None

    def process_document(self, doc: Document) -> Document:
        """
        Processa o documento, normalizando o texto e extraindo metadados.
        """
        doc.page_content = self._normalize_text(doc.page_content)
        doc.page_content = self._filter_content(doc.page_content)

        doc = self._clean_metadata(doc)

        path = doc.metadata.get("file_path", "source")
        page = doc.metadata.get("page", "1")

        metadata_str = (
            f"Documento: {path} | "
            f"Número da página: {page} | "
            f"Texto do chunk: "
        )

        doc.page_content = metadata_str + doc.page_content

        link_contents = []
        links = doc.metadata.get("links", [])
        if links:
            links = set(links)
            for link in links:
                link_text = self._fetch_link_content(link)
                if link_text:
                    link_contents.append(f" link|url|aplicativo|app|tela: {link} | Texto do link: {link_text}")

        if link_contents:
            for content in link_contents:
                doc.page_content = doc.page_content + content

        return doc

    def create_text_splitter(self) -> RecursiveCharacterTextSplitter:
        """
        Cria um divisor de texto recursivo com base nos tamanhos de chunk.
        """
        return RecursiveCharacterTextSplitter(
            separators=["\n\n", "."],
            chunk_size=self.max_chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

    def split_text(self, text: str) -> List[str]:
        """
        Divide o texto em chunks com base no divisor de texto.
        """
        splitter = self.create_text_splitter()
        return splitter.split_text(text)

    def load_files(self, file_path: str) -> List[Document]:
        """
        Carrega e processa arquivos de um diretório especificado.
        """
        documents = []
        for root, _, files in os.walk(file_path):
            for file in files:
                _file_path = os.path.join(root, file)
                logger.info(f"Processando arquivo: {_file_path}")
                try:
                    if file.endswith(".pdf"):
                        docs = self.extract_from_pdf(_file_path)
                    elif file.endswith(".txt"):
                        loader = TextLoader(_file_path)
                        docs = loader.load()
                        for doc in docs:
                            doc.page_content = self._preprocess_txt(
                                doc.page_content
                            )
                    elif file.endswith(".csv"):
                        loader = CSVLoader(_file_path)
                        docs = loader.load()
                        for doc in docs:
                            doc.page_content = self._preprocess_csv(
                                doc.page_content
                            )
                    else:
                        loader = UnstructuredFileLoader(_file_path)
                        docs = loader.load()

                    for doc in docs:
                        processed_doc = self.process_document(doc)
                        chunks = self.split_text(processed_doc.page_content)
                        for chunk in chunks:
                            chunk_doc = processed_doc.copy()
                            chunk_doc.page_content = chunk
                            documents.append(chunk_doc)

                except Exception as e:
                    logger.error(f"Erro ao processar o arquivo {_file_path}: {e}")

        if not documents:
            logger.warning(f"Nenhum documento válido encontrado em {file_path}")

        return documents

    def extract_from_pdf(self, file_path: str) -> List[Document]:
        """
        Extrai texto e metadados de um arquivo PDF.
        """
        documents = []
        try:
            doc = PdfReader(file_path)  # Carrega o PDF

            # Iterar sobre as páginas do documento
            for page_num, page in enumerate(doc.pages):
                text = page.extract_text()  # Extrai o texto da página

                if not isinstance(text, str):
                    logger.warning(f"Texto vazio ou não processável na página {page_num} do arquivo: {file_path}")
                    text = ""

                # Extraindo links (anotações)
                links = []
                if "/Annots" in page:
                    for annot in page["/Annots"]:
                        annot_obj = annot.get_object()
                        if "/A" in annot_obj and "/URI" in annot_obj["/A"]:
                            uri = annot_obj["/A"]["/URI"]
                            if isinstance(uri, str):
                                links.append(uri)
                            else:
                                logger.warning(f"Link inesperado na página {page_num+1} do arquivo: {file_path}, link: {uri}")

                metadata: Dict[str, Any] = {
                    "file_path": file_path,
                    "page_number": page_num + 1,
                    "links": links,
                }

                documents.append(Document(page_content=text, metadata=metadata))

        except Exception as e:
            logger.error(f"Erro ao processar o arquivo {file_path}: {e}")
        
        return documents