import os
import shutil
from langchain_community.document_loaders import TextLoader, CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFaceEndpoint
from langchain_chroma import Chroma
from langchain.prompts import PromptTemplate

# Set Hugging Face API Key
os.environ["HUGGINGFACEHUB_API_TOKEN"] = "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"

# Directory containing files
data_dir = "D:\\OneDrive\\Desktop\\web development\\backend\\python\\KMIT_DATA"

# Load documents
documents = []
for filename in os.listdir(data_dir):
    file_path = os.path.join(data_dir, filename)
    try:
        if filename.endswith(".txt"):
            loader = TextLoader(file_path, encoding="utf-8")
            documents.extend(loader.load())
        elif filename.endswith(".csv"):
            loader = CSVLoader(file_path, encoding="utf-8")
            documents.extend(loader.load())
    except Exception as e:
        print(f"Error loading {file_path}: {e}")

if not documents:
    raise ValueError("No documents loaded.")

print(f"Loaded {len(documents)} documents.")
print(f"Sample content: {documents[0].page_content[:200]}...")

# Split into chunks
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=150)
texts = text_splitter.split_documents(documents)
print(f"Split into {len(texts)} chunks.")

# Embedding model
embedding = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")

# Create vector database
persist_directory = "db"
if os.path.exists(persist_directory):
    shutil.rmtree(persist_directory)
    print(f"Cleared database at {persist_directory}")
vectordb = Chroma.from_documents(documents=texts, embedding=embedding, persist_directory=persist_directory)
vectordb = Chroma(persist_directory=persist_directory, embedding_function=embedding)

# Simple retriever
retriever = vectordb.as_retriever(search_type="similarity", search_kwargs={"k": 50})

# LLM setup
llm = HuggingFaceEndpoint(
    repo_id="mistralai/Mixtral-8x7B-Instruct-v0.1",
    model_kwargs={"token": os.getenv("HUGGINGFACEHUB_API_TOKEN")},
    temperature=0.001,
    max_new_tokens=1500,
)

# Strict prompt
prompt_template = """Use the following context from the KMIT documents to answer the question about Keshav Memorial Institute of Technology (KMIT) in Hyderabad, India. Copy all relevant details verbatim from the context exactly as they appear, without summarization, paraphrasing, or omission. If no relevant context is retrieved or the answer isn’t found, state 'The information is unavailable in the provided documents' and provide no additional information.

Context: {context}

Question: {question}

Answer:"""
PROMPT = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=retriever,
    return_source_documents=True,
    chain_type_kwargs={"prompt": PROMPT},
)

# Debug and process
def process_llm_response(llm_response):
    print("Answer:")
    print(llm_response['result'].strip())
    print("\nSources:")
    for source in llm_response["source_documents"][:5]:  # Limit to 5 for brevity
        score = source.metadata.get('relevance_score', 'N/A')
        print(f"{source.metadata['source']} - Score: {score} - {source.page_content[:100]}...")
    print(f"Retrieved {len(llm_response['source_documents'])} document chunks.")

# Queries
queries = [
    "Can you provide a brief description of KMIT as an educational institution?",
    "How to join a Bachelor's degree at KMIT?",
    "Where is KMIT located?",
    "What is the highest package at KMIT?",
    "What programs does KMIT offer?",
    "What are the facilities available at KMIT?",
    "Who is the Dean of Placements at KMIT?",
    "What is the fee structure for B.Tech at KMIT?",
    "What sports facilities are available at KMIT?",
    "What is the placement record for the 2023-24 batch at KMIT?"
]

for query in queries:
    print(f"\nQuery: {query}")
    docs = retriever.invoke(query)
    print(f"Retrieved docs: {len(docs)} - Sample: {[doc.page_content[:100] for doc in docs[:2]]}")
    response = qa_chain.invoke(query)
    process_llm_response(response)