import os
import logging
from qdrant_client import QdrantClient
from qdrant_client.models import NamedVector
from openai import AsyncOpenAI

logger = logging.getLogger("gaply-rag")

class RAGRetriever:
    def __init__(self):
        qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
        self.collection_name = os.getenv("QDRANT_COLLECTION", "gaply_knowledge")
        self.qclient = QdrantClient(url=qdrant_url)
        self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def retrieve(self, query: str, top_k: int = 5) -> str:
        """
        Embeds the query and searches Qdrant for top-K matching contexts.
        Returns a formatted string of the context chunks.
        """
        try:
            # Create embedding for the user's query
            response = await self.openai_client.embeddings.create(
                input=query,
                model="text-embedding-3-small"
            )
            query_vector = response.data[0].embedding

            # Search in Qdrant using the modern query_points API
            search_result = self.qclient.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
            )

            points = search_result.points if hasattr(search_result, 'points') else search_result

            if not points:
                return "No relevant context found."

            # Format the results into a numbered list
            context_chunks = []
            for i, res in enumerate(points):
                text = res.payload.get("text", "") if res.payload else ""
                if text:
                    context_chunks.append(f"[{i+1}] {text}")

            return "\n\n".join(context_chunks) if context_chunks else "No relevant context found."
            
        except Exception as e:
            logger.error(f"RAG retrieval error: {e}")
            return "Context retrieval failed due to an error."
