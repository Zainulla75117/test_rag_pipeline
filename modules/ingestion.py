from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_chroma import Chroma
from modules.embedding_config import get_embedding_model
import os

def load_documents(docs_path="docs"):
    """Load all text files from the docs directory"""
    print(f"Loading documents from {docs_path}...")
    
    # Check if docs directory exists
    if not os.path.exists(docs_path):
        raise FileNotFoundError(f"The directory {docs_path} does not exist. Please create it and add your company files.")
    
    # Load all .txt files from the docs directory
    loader = DirectoryLoader(
        path=docs_path,
        glob="*.txt",
        loader_cls=TextLoader
    )
    
    documents = loader.load()
    
    if len(documents) == 0:
        raise FileNotFoundError(f"No .txt files found in {docs_path}. Please add your company documents.")
    
   
    for i, doc in enumerate(documents[:2]):  # Show first 2 documents
        print(f"\nDocument {i+1}:")
        print(f"  Source: {doc.metadata['source']}")
        print(f"  Content length: {len(doc.page_content)} characters")
        print(f"  Content preview: {doc.page_content[:100]}...")
        print(f"  metadata: {doc.metadata}")

    return documents

def split_documents(documents, chunk_size=1000, chunk_overlap=100):
    """Split documents into smaller chunks with overlap"""
    print("Splitting documents into chunks...")
    text_splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=chunk_size, 
        chunk_overlap=chunk_overlap
    )
    
    chunks = text_splitter.split_documents(documents)
    
    if chunks:
    
        for i, chunk in enumerate(chunks[:5]):
            print(f"\n--- Chunk {i+1} ---")
            print(f"Source: {chunk.metadata['source']}")
            print(f"Length: {len(chunk.page_content)} characters")
            print(f"Content:")
            print(chunk.page_content)
            print("-" * 50)
        
        if len(chunks) > 5:
            print(f"\n... and {len(chunks) - 5} more chunks")
    
    return chunks

def create_vector_store(chunks, persist_directory="db/chroma_db"):
    """Create and persist ChromaDB vector store"""
    print("Creating embeddings and storing in ChromaDB...")
        
    embedding_model = get_embedding_model()
    
    # Create ChromaDB vector store
    print("--- Creating vector store ---")
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,
        persist_directory=persist_directory, 
        collection_metadata={"hnsw:space": "cosine"}
    )
    print("--- Finished creating vector store ---")
    
    print(f"Vector store created and saved to {persist_directory}")
    return vectorstore

def process_single_file(file_path: str, persist_directory="db/chroma_db", progress_callback=None):
    """Load, split and add a single file to ChromaDB"""
    print(f"Processing single file: {file_path}")
    
    if progress_callback:
        progress_callback(10, "Extracting text from document...")
        
    ext = os.path.splitext(file_path)[1].lower()
    
    documents = []
    
    if ext == '.txt':
        loader = TextLoader(file_path)
        documents = loader.load()
    elif ext == '.csv':
        loader = CSVLoader(file_path)
        documents = loader.load()
    elif ext == '.pdf':
        loader = PyPDFLoader(file_path)
        documents = loader.load()
    elif ext == '.db':
        import sqlite3
        from langchain_core.documents import Document
        
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            try:
                cursor.execute(f"SELECT * FROM {table_name}")
                col_names = [description[0] for description in cursor.description]
                
                while True:
                    rows = cursor.fetchmany(1000)
                    if not rows:
                        break
                    
                    batch_content = f"--- Table: {table_name} ---\n"
                    for row in rows:
                        row_str = ", ".join([f"{col}: {val}" for col, val in zip(col_names, row) if val is not None])
                        batch_content += row_str + "\n"
                    
                    documents.append(Document(page_content=batch_content, metadata={"source": file_path, "table": table_name}))
            except Exception as e:
                print(f"Error reading table {table_name}: {e}")
        
        conn.close()
        
    else:
        # Fallback to TextLoader or raise error depending on needs
        raise ValueError(f"Unsupported file extension: {ext}")
        
    if not documents:
        raise ValueError(f"No content found in {file_path}")
        
    if progress_callback:
        progress_callback(40, "Splitting document into chunks...")
        
    chunks = split_documents(documents)
    
    if not chunks:
        raise ValueError(f"Failed to split documents for {file_path}")
        
    if progress_callback:
        progress_callback(70, "Generating embeddings and storing in database...")
        
    embedding_model = get_embedding_model()
    
    vectorstore = Chroma(
        persist_directory=persist_directory,
        embedding_function=embedding_model,
        collection_metadata={"hnsw:space": "cosine"}
    )
    
    vectorstore.add_documents(documents=chunks)
    
    if progress_callback:
        progress_callback(100, "Processing complete")
    
    return len(chunks)
