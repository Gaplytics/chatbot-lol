from fastapi import APIRouter

router = APIRouter()

@router.get("")
async def health_check():
    """
    Simple health check endpoint used by Docker Compose and external load balancers.
    """
    return {"status": "ok", "service": "gaply-token-api"}
