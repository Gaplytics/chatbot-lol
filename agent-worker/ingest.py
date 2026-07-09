import os
import logging
import glob
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from openai import OpenAI

logger = logging.getLogger("gaply-ingest")

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Splits text into overlapping chunks based on word count."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks

def ingest_all(scraped_pages: list[dict] = None):
    """
    Ingests all manual markdown files and optionally scraped pages into Qdrant.
    """
    qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
    collection_name = os.getenv("QDRANT_COLLECTION", "gaply_knowledge")
    
    qclient = QdrantClient(url=qdrant_url)
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Ensure collection exists, otherwise create it
    try:
        qclient.get_collection(collection_name)
    except:
        logger.info(f"Creating collection {collection_name} in Qdrant...")
        qclient.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
        )
    
    points = []
    
    # 1. Ingest manual markdown files
    knowledge_dir = os.path.join(os.path.dirname(__file__), "knowledge")
    md_files = glob.glob(os.path.join(knowledge_dir, "*.md"))
    
    for file_path in md_files:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            filename = os.path.basename(file_path)
            
            for i, chunk in enumerate(chunk_text(content)):
                # Embed the chunk
                res = openai_client.embeddings.create(input=chunk, model="text-embedding-3-small")
                vector = res.data[0].embedding
                
                point_id = str(uuid.uuid4())
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={"text": chunk, "source": filename, "type": "manual"}
                    )
                )
                
    # 2. Ingest scraped pages (if provided)
    if scraped_pages:
        for page in scraped_pages:
            for i, chunk in enumerate(chunk_text(page["content"])):
                res = openai_client.embeddings.create(input=chunk, model="text-embedding-3-small")
                vector = res.data[0].embedding
                
                point_id = str(uuid.uuid4())
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={"text": chunk, "source": page["url"], "title": page["title"], "type": "scraped"}
                    )
                )
                
    # Upsert to Qdrant
    if points:
        qclient.upsert(
            collection_name=collection_name,
            points=points
        )
        logger.info(f"Successfully ingested {len(points)} chunks into Qdrant collection '{collection_name}'.")
    else:
        logger.warning("No data found to ingest.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv()
    ingest_all()
