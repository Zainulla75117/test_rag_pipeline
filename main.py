import os
import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# Import existing logic (adapted)
from modules.ingestion import process_single_file
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI
from modules.embedding_config import get_embedding_model
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="RAG API")

# Ensure directories exist
os.makedirs("docs", exist_ok=True)
os.makedirs("db/chroma_db", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

persistent_directory = "db/chroma_db"
embedding_model = get_embedding_model()
llm_model = ChatGoogleGenerativeAI(model="gemini-3.7-flash")

def get_db():
    return Chroma(
        persist_directory=persistent_directory,
        embedding_function=embedding_model,
        collection_metadata={"hnsw:space": "cosine"}
    )

class QueryRequest(BaseModel):
    query: str

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("static/index.html", "r") as f:
        return f.read()

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    file_path = os.path.join("docs", file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # Process the single file
        num_chunks = process_single_file(file_path)
        return {"filename": file.filename, "message": "File ingested successfully", "chunks": num_chunks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query")
async def query_rag(request: QueryRequest):
    query = request.query
    
    db = get_db()
    retriever = db.as_retriever(search_kwargs={"k": 2})
    
    try:
        relevant_docs = retriever.invoke(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying db: {str(e)}")
        
    if relevant_docs:
        # Combine the query and the relevant document contents
        combined_input = f"""Based on the following documents, please answer this question: {query}

        Documents:
        {chr(10).join([f"- {doc.page_content}" for doc in relevant_docs])}

        Please provide a clear, helpful answer using only the information from these documents. If you can't find the answer in the documents, say "I don't have enough information to answer that question based on the provided documents."
        """
    else:
        # Just use the query directly if no documents are found
        combined_input = query

    messages = [
        SystemMessage(content="You are a helpful assistant."),
        HumanMessage(content=combined_input),
    ]

    result = llm_model.invoke(messages)
    
    answer_text = result.content
    if isinstance(answer_text, list):
        answer_text = "".join([block.get("text", "") if isinstance(block, dict) else str(block) for block in answer_text])
    
    sources = [{"content": doc.page_content, "source": doc.metadata.get("source", "Unknown")} for doc in relevant_docs] if relevant_docs else []
    
    return {"answer": answer_text, "sources": sources}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
