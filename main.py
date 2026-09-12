import os
import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

task_statuses = {}

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

def update_status(filename, percentage, message, chunks=0, error=None):
    if error:
        task_statuses[filename] = {"status": "error", "message": error}
    elif percentage == 100:
        task_statuses[filename] = {"status": "completed", "progress": 100, "message": message, "chunks": chunks}
    else:
        task_statuses[filename] = {"status": "processing", "progress": percentage, "message": message}

def process_file_bg(file_path: str, filename: str):
    def callback(percentage, message):
        update_status(filename, percentage, message)
        
    try:
        update_status(filename, 0, "Starting processing...")
        num_chunks = process_single_file(file_path, progress_callback=callback)
        update_status(filename, 100, "File ingested successfully", chunks=num_chunks)
    except Exception as e:
        update_status(filename, 0, str(e), error=str(e))

@app.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    file_path = os.path.join("docs", file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Start background task
    task_statuses[file.filename] = {"status": "queued", "progress": 0, "message": "Queued for processing..."}
    background_tasks.add_task(process_file_bg, file_path, file.filename)
    
    return {"filename": file.filename, "message": "Upload complete, processing in background"}

@app.get("/status/{filename}")
async def get_status(filename: str):
    if filename not in task_statuses:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_statuses[filename]

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
