from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.api.v1 import api_router

app = FastAPI(title="AI Agentic Deals API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_websockets=True,  # Explicitly allow WebSocket connections
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")
