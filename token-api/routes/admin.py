from fastapi import APIRouter

router = APIRouter()

@router.post("/ingest")
async def trigger_ingest():
    """
    Admin endpoint to trigger re-ingestion of manual markdown files into Qdrant.
    Note: In a pure microservice environment with separate containers, this should 
    publish an event to Redis that the agent-worker listens to. 
    """
    return {"status": "accepted", "message": "Ingest request queued. (Requires Redis PubSub wiring in production)."}

@router.post("/scrape")
async def trigger_scrape():
    """
    Admin endpoint to trigger a fresh scrape of the website and ingestion into Qdrant.
    """
    return {"status": "accepted", "message": "Scrape request queued. (Requires Redis PubSub wiring in production)."}
