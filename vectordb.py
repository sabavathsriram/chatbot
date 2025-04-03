import os
import re
from fastapi import FastAPI, Query
from pydantic import BaseModel
from langchain_community.document_loaders import TextLoader
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.docstore.document import Document

# Initialize FastAPI app
app = FastAPI()

# Directory containing document files
DATA_DIR = "kmit_data"
PERSIST_DIR = "db"

# Ensure directory exists
if not os.path.exists(DATA_DIR):
    raise FileNotFoundError(f"Directory '{DATA_DIR}' not found. Please add your documents.")

# Load and process documents
documents = []
for filename in os.listdir(DATA_DIR):
    if filename.endswith(".txt"):
        loader = TextLoader(os.path.join(DATA_DIR, filename))
        documents.extend(loader.load())

if not documents:
    raise ValueError(f"No .txt files found in '{DATA_DIR}'. Please add your documents.")

# Function to split documents into Q&A pairs
def split_into_qa_pairs(text):
    qa_pairs = re.split(r'\n*(?:Q: |^\d+\.\s+)', text, flags=re.MULTILINE)[1:]
    return [pair.strip() for pair in qa_pairs if pair.strip()]

# Process the documents
split_docs = []
for doc in documents:
    qa_pairs = split_into_qa_pairs(doc.page_content)
    for i, qa in enumerate(qa_pairs):
        split_docs.append(Document(
            page_content=qa,
            metadata={"source": doc.metadata["source"], "qa_index": i}
        ))

# Initialize ChromaDB with Sentence Transformer embeddings
embedding = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectordb = Chroma.from_documents(documents=split_docs, embedding=embedding, persist_directory=PERSIST_DIR)

print(f"Embeddings stored in ChromaDB at '{PERSIST_DIR}'")
print(f"Total Q&A pairs indexed: {len(split_docs)}")

# API Model for queries
class QueryModel(BaseModel):
    query: str

# API endpoint for chatbot queries
@app.post("/query/")
async def fetch_answer(request: QueryModel):
    query_text = request.query.strip().lower()
    vectordb = Chroma(persist_directory=PERSIST_DIR, embedding_function=embedding)
    results = vectordb.similarity_search(query_text, k=5)  # Adjust k based on relevance

    if not results:
        return {"answer": "The information is not available in the provided documents."}

    best_answer = results[0].page_content  # Take the most relevant match

    return {"answer": best_answer}

# Run the API server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
