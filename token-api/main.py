import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routes import token, health, admin

# Load environment variables
load_dotenv()

app = FastAPI(title="Gaply Token API")

# Configure CORS (Critical for allowing the chat widget to fetch tokens from external sites)
cors_origins = os.getenv("WIDGET_CORS_ORIGINS", "").split(",")
if not cors_origins or cors_origins == [""]:
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(token.router, prefix="/token", tags=["token"])
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
