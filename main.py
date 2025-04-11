import os
import json
import asyncio
import httpx
from threading import Thread
from datetime import timedelta

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

from air_quality_robot.readings import (
    start_logger as start_air_logger,
    get_air_readings,
    get_air_history,
)
from presence_robot.readings import (
    get_presence_readings,
    start_logger as start_presence_logger,
)

load_dotenv()

app = FastAPI()

# CORS for ChatGPT plugin compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://chat.openai.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LOCAL_API_KEY = os.getenv("LOCAL_API_KEY")

@app.on_event("startup")
async def startup():
    asyncio.create_task(start_air_logger())
    asyncio.create_task(start_presence_logger())
    Thread(target=start_self_ping, daemon=True).start()

# Air quality sensor
@app.get("/get_readings")
async def get_readings(request: Request):
    api_key = request.headers.get("X-API-Key")
    if api_key != LOCAL_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return JSONResponse(content=await get_air_readings())

@app.get("/history")
async def get_history(request: Request):
    api_key = request.headers.get("X-API-Key")
    if api_key != LOCAL_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return JSONResponse(content={"history": get_air_history()})

# mmWave presence detector
@app.get("/presence")
async def presence_readings(request: Request):
    api_key = request.headers.get("X-API-Key")
    if api_key != LOCAL_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return JSONResponse(content=await get_presence_readings())

@app.get("/ping")
def ping():
    return {"message": "pong"}

# Self-ping every 14 minutes
async def self_ping():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://localhost:{os.getenv('PORT', 8000)}/ping")
                print(f"Self-ping response: {response.status_code}")
        except Exception as e:
            print(f"Self-ping error: {e}")
        await asyncio.sleep(840)  # 14 minutes

def start_self_ping():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(self_ping())

@app.get("/")
def root():
    return {"message": "Viam robots are running"}

@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
def serve_manifest():
    return FileResponse(".well-known/ai-plugin.json", media_type="application/json")

@app.get("/openapi.yaml", include_in_schema=False)
def serve_openapi():
    return FileResponse("openapi.yaml", media_type="application/yaml")