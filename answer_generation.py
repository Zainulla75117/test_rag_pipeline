from langchain_chroma import Chroma
from modules.embedding_config import get_embedding_model
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage


load_dotenv()

persistent_directory = "db/chroma_db"

# Load embeddings and vector store
embedding_model = get_embedding_model()
# Create a Gemini model
model = ChatGoogleGenerativeAI(model="gemini-3.7-flash")

db = Chroma(
    persist_directory=persistent_directory,
    embedding_function=embedding_model,
    collection_metadata={"hnsw:space": "cosine"}  
)

# Search for relevant documents
while True:
    query = str(input("user_input: "))

    retriever = db.as_retriever(search_kwargs={"k": 2})

    # retriever = db.as_retriever(
    #     search_type="similarity_score_threshold",
    #     search_kwargs={
    #         "k": 5,
    #         "score_threshold": 0.3  # Only return chunks with cosine similarity ≥ 0.3
    #     }
    # )

    relevant_docs = retriever.invoke(query)

    print(f"User Query: {query}")
    # Display results
    print("--- Context ---")
    for i, doc in enumerate(relevant_docs, 1):
        print(f"Document {i}:\n{doc.page_content}\n")


    # Combine the query and the relevant document contents
    combined_input = f"""Based on the following documents, please answer this question: {query}

    Documents:
    {chr(10).join([f"- {doc.page_content}" for doc in relevant_docs])}

    Please provide a clear, helpful answer using only the information from these documents. If you can't find the answer in the documents, say "I don't have enough information to answer that question based on the provided documents."
    """



    # Define the messages for the model
    messages = [
        SystemMessage(content="You are a helpful assistant."),
        HumanMessage(content=combined_input),
    ]

# Invoke the model with the combined input
    if query.lower() == "quit":
        break

    result = model.invoke(messages)

    print("AI_response:")
    print(result.content[0]["text"]+"\n\n")