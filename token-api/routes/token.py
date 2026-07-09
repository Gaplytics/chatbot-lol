import os
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from livekit import api

router = APIRouter()

import json

class TokenRequest(BaseModel):
    participant_name: str = "User"
    tenant_id: str
    metadata: dict = None

@router.post("")
async def create_token(req: TokenRequest):
    """
    Issues a short-lived LiveKit AccessToken for the widget session.
    Each token generates a unique room so user sessions are isolated.
    """
    livekit_api_key = os.getenv("LIVEKIT_API_KEY")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")
    
    if not livekit_api_key or not livekit_api_secret:
        raise HTTPException(status_code=500, detail="LiveKit keys are not configured correctly.")
        
    # Unique room and identity for this session
    room_name = f"gaply-room-{uuid.uuid4().hex[:8]}"
    participant_identity = f"user-{uuid.uuid4().hex[:8]}"
    
    # Create video grant with appropriate permissions
    grant = api.VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=True,
        can_subscribe=True,
        can_publish_data=True
    )
    
    # Generate the JWT Token (default expiration is typically 1 hour)
    access_token = api.AccessToken(
        livekit_api_key, 
        livekit_api_secret
    ).with_grants(grant).with_identity(participant_identity).with_name(req.participant_name)
    
    # Inject tenant_id into metadata
    meta = req.metadata or {}
    meta["tenant_id"] = req.tenant_id
    access_token = access_token.with_metadata(json.dumps(meta))
        
    token_str = access_token.to_jwt()
    
    return {
        "token": token_str,
        "room_name": room_name,
        "livekit_url": os.getenv("LIVEKIT_PUBLIC_URL", "ws://localhost:7989")
    }
