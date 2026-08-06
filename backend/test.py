import os

import chromadb
from sentence_transformers import SentenceTransformer

# Path to your ChromaDB
DB_PATH = "./maharashtra_gr_db_v2_backup/chroma_db"

client = chromadb.PersistentClient(path=DB_PATH)

# Load embedding model
embedding_model = SentenceTransformer("BAAI/bge-m3")

collections = client.list_collections()

print(f"\nFound {len(collections)} collection(s)\n")

total_embeddings = 0

for collection in collections:
    col = client.get_collection(collection.name)

    count = col.count()
    total_embeddings += count

    print("=" * 60)
    print(f"Collection : {collection.name}")
    print(f"Embeddings : {count}")

print("=" * 60)
print(f"TOTAL EMBEDDINGS : {total_embeddings}\n")

# ----------------------------------------------------------------------
# Approximate database size on disk
# ----------------------------------------------------------------------

total_size = 0

for root, dirs, files in os.walk(DB_PATH):
    for file in files:
        filepath = os.path.join(root, file)
        total_size += os.path.getsize(filepath)

print(f"Database Size : {total_size / (1024**2):.2f} MB")

# ----------------------------------------------------------------------
# Test query
# ----------------------------------------------------------------------

QUERY = "Gokhale Institute financial sustainability"

query_embedding = embedding_model.encode(
    QUERY,
    normalize_embeddings=True
).tolist()

doc_collection = client.get_collection("gr_documents")

results = doc_collection.query(
    query_embeddings=[query_embedding],
    n_results=5
)

doc = doc_collection.get(
    ids=["202402291744117508.pdf"],
    include=["documents"]
)

print(doc["documents"][0])

chunk_collection = client.get_collection("gr_chunks")

results = chunk_collection.query(
    query_embeddings=[query_embedding],
    where={
        "pdf_name": "202402291744117508.pdf"
    },
    n_results=5
)

print(results["ids"][0])
print(results["documents"][0][0][:1000])

print("\nTop Results:")
for i, (doc_id, distance, metadata) in enumerate(
    zip(results["ids"][0], results["distances"][0], results["metadatas"][0]),
    start=1,
):
    print(f"\n{i}. ID       : {doc_id}")
    print(f"   Distance : {distance:.4f}")
    print(f"   Metadata : {metadata}")