"""Implements text processing for document preparation.

This module provides functions to prepare text documents for data extraction.
"""

from pathlib import Path

from semantic_text_splitter import TextSplitter

from wukong_engine.config.config import Config
from wukong_engine.core.data_model import DataModel
from wukong_engine.utils.file_utils import delete_dir_contents, load_text_data, save_json_data, save_text_data

# Configuration
TIKTOKEN_MODEL = 'gpt-4'  # Tokenizer model to use for splitting text


def process_text_documents(text_dir: Path, processed_dir: Path, results_dir: Path) -> None:
    """Process input documents to prepare them for data extraction.

    Loads input plain text documents and saves them in new files with standardized filenames.
    Creates `Document` entities to represent each document and then saves them in a JSON file.

    Args:
        text_dir: The path to the directory that contains all document sets holding the plain text documents to be processed.
        processed_dir: The path to the directory where processed documents will be saved.
        results_dir: The path to the directory where entities/relations will be stored.

    Raises:
        FileNotFoundError: If the input documents directory or any document set directory does not exist.
    """
    # Prepare target directories
    processed_dir.mkdir(parents=True, exist_ok=True)
    delete_dir_contents(processed_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    delete_dir_contents(results_dir)
    entities_dir = results_dir / 'entities/'
    entities_dir.mkdir(parents=True, exist_ok=True)

    # If the input directory does not exist, abort the process
    if not text_dir.exists():
        raise FileNotFoundError(
            f'Document Processing failed. The text documents directory "{text_dir}" does not exist.',
        )

    # Process each document set separately
    document_paths = {}
    for document_set in DataModel().document_sets:
        set_dir = text_dir / document_set

        # If the document set directory does not exist, abort the process
        if not set_dir.exists():
            raise FileNotFoundError(
                f'Document Processing failed. The directory for the document set "{document_set}" does not exist at path "{set_dir}".',
            )

        # Gather all input plain text files for the set
        document_paths[document_set] = sorted(
            [doc_path for doc_path in set_dir.iterdir() if doc_path.is_file() and doc_path.suffix == '.txt'],
        )

        # Create directory for the document set
        processed_set_dir = processed_dir / document_set
        processed_set_dir.mkdir(parents=True, exist_ok=True)

    # Iterate over each file and process it
    n_documents = 1
    document_entities = []
    for document_set, doc_paths in document_paths.items():
        for document_path in doc_paths:
            # Load contents from the document
            document_name = document_path.stem
            document_content = load_text_data(document_path)

            # Save the document contents as a new plain text file with a standardized name
            processed_document_name = f'document_{n_documents}.txt'
            processed_document_path = processed_dir / document_set / processed_document_name
            save_text_data(document_content, processed_document_path)

            # Create entity for the document, with a unique identifier
            document_id = f'Document_{n_documents}'
            document_entity = {'name': document_name, 'document_set': document_set, '_ObjectId': document_id}
            document_entities.append(document_entity)

            n_documents += 1

    # Save all document entities into a single file
    document_entities_path = entities_dir / 'Document.json'
    save_json_data(document_entities, document_entities_path)


def generate_chunks(docs_dir: Path, chunks_dir: Path, results_dir: Path) -> None:
    """Separate documents into smaller chunks and prepare them for data extraction.

    Splits each document into smaller chunks based on a specified token limit per chunk.
    Creates `Chunk` entities to represent each chunk, and `ChunkOf` relations to link them to their respective full documents.
    All entities and relations are then saved to their respective JSON files.

    Args:
        docs_dir: The path to the directory that contains all document sets holding the documents to be chunked.
        chunks_dir: The path to the directory where the chunks will be saved.
        results_dir: The path to the directory where entities/relations will be stored.
    """
    # Prepare target directories
    chunks_dir.mkdir(parents=True, exist_ok=True)
    delete_dir_contents(chunks_dir)
    entities_dir = results_dir / 'entities/'
    entities_dir.mkdir(parents=True, exist_ok=True)
    delete_dir_contents(entities_dir, items_to_keep=['Document.json'])
    relations_dir = results_dir / 'relations/'
    relations_dir.mkdir(parents=True, exist_ok=True)
    delete_dir_contents(relations_dir)

    # Process each document set separately
    document_paths = {}
    for document_set in DataModel().document_sets:
        set_dir = docs_dir / document_set

        # Gather all documents for the set
        document_paths[document_set] = sorted(
            [
                doc_path
                for doc_path in set_dir.iterdir()
                if doc_path.is_file() and doc_path.suffix == '.txt' and doc_path.name.startswith('document_')
            ],
        )

        # Create directory for the document set chunks
        set_chunks_dir = chunks_dir / document_set
        set_chunks_dir.mkdir(parents=True, exist_ok=True)

    # Iterate over each document and process it into chunks
    chunk_entities = []
    chunk_relations = []
    for document_set, doc_paths in document_paths.items():
        for document_path in doc_paths:
            # Load contents from the document
            document_name = document_path.stem
            document_content = load_text_data(document_path)

            # Split the document content into smaller chunks
            splitter = TextSplitter.from_tiktoken_model(TIKTOKEN_MODEL, Config().get('max_tokens', 2000))
            chunks = splitter.chunks(document_content)

            # Get the unique identifier for the document
            _, document_number = document_name.split('_')
            document_id = f'Document_{document_number}'

            # Iterate over each chunk and process it
            for idx, chunk in enumerate(chunks, start=1):
                # Save chunk as a separate plain text file
                chunk_path = chunks_dir / document_set / f'{document_name}_{idx}.txt'
                save_text_data(chunk, chunk_path)

                # Create entity for the chunk
                chunk_id = f'Chunk_{document_number}_{idx}'
                chunk_entity = {'text': chunk, '_ObjectId': chunk_id}
                chunk_entities.append(chunk_entity)

                # Create relation between the chunk and the document
                chunk_relation = {
                    '_OriginId': chunk_id,
                    '_TargetId': document_id,
                    'chunk_number': idx,
                }
                chunk_relations.append(chunk_relation)

    # Save all chunk entities into a single file
    chunk_entities_path = entities_dir / 'Chunk.json'
    save_json_data(chunk_entities, chunk_entities_path)

    # Save all chunk relations into a single file
    chunk_relations_path = relations_dir / 'ChunkOf.json'
    save_json_data(chunk_relations, chunk_relations_path)
