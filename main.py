import os
import json
import asyncio
from datetime import datetime, timedelta

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from dotenv import load_dotenv

from viam.rpc.dial import DialOptions
from viam.robot.client import RobotClient
from viam.components.sensor import Sensor

load_dotenv()

app = FastAPI()

DATA_LOG_FILE = "air_quality_log.json"
LOG_INTERVAL_SECONDS = 300  # 5 minutes
MAX_LOG_DURATION = timedelta(hours=24)

# CORS for ChatGPT plugin compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://chat.openai.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def start_logger():
    async def log_readings():
        while True:
            data = await get_viam_readings()
            timestamped_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "data": data
            }

            try:
                if os.path.exists(DATA_LOG_FILE):
                    with open(DATA_LOG_FILE, "r") as f:
                        logs = json.load(f)
                else:
                    logs = []
            except Exception:
                logs = []

            logs.append(timestamped_entry)

            # Keep only the last 24 hours of data
            cutoff = datetime.utcnow() - MAX_LOG_DURATION
            logs = [
                entry for entry in logs
                if datetime.fromisoformat(entry["timestamp"]) > cutoff
            ]

            with open(DATA_LOG_FILE, "w") as f:
                json.dump(logs, f)

            await asyncio.sleep(LOG_INTERVAL_SECONDS)

    asyncio.create_task(log_readings())

LOCAL_API_KEY = os.getenv("LOCAL_API_KEY")

# EPA AQI Breakpoints for PM2.5 (ug/m3)
PM25_BUCKETS = [
    (0.0, 12.0, "good"),
    (12.1, 35.4, "moderate"),
    (35.5, 55.4, "unhealthy for sensitive groups"),
    (55.5, 150.4, "unhealthy"),
    (150.5, 250.4, "very unhealthy"),
    (250.5, 500.0, "hazardous")
]

def get_robot_options():
    return RobotClient.Options.with_api_key(
        api_key=os.getenv("VIAM_API_KEY"),
        api_key_id=os.getenv("VIAM_API_KEY_ID")
    )

def bucket_pm25(value):
    for low, high, label in PM25_BUCKETS:
        if low <= value <= high:
            return label
    return "beyond index"

def assess_air_quality(readings):
    status = {}
    pm25 = readings.get("pm2_5_atm") or readings.get("pm2_5_CF1")
    if pm25 is not None:
        status["pm2_5_category"] = bucket_pm25(pm25)
    return status

async def get_viam_readings():
    try:
        print("Getting robot options...")
        options = get_robot_options()

        print("Connecting to robot...")
        robot = await RobotClient.at_address(os.getenv("VIAM_ROBOT_ADDR"), options)

        print("Getting sensor...")
        sensor = Sensor.from_robot(robot, "sensor-1")

        print("Getting readings...")
        readings = await sensor.get_readings()

        print("Closing robot...")
        await robot.close()

        status = assess_air_quality(readings)
        return {"readings": readings, "status": status}
    except Exception as e:
        print("Error in get_viam_readings:", e)
        return {"error": str(e)}

@app.get("/get_readings")
async def get_readings(request: Request):
    api_key = request.headers.get("X-API-Key")
    if api_key != LOCAL_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return await get_viam_readings()

@app.get("/history")
async def get_history(request: Request):
    api_key = request.headers.get("X-API-Key")
    if api_key != LOCAL_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if not os.path.exists(DATA_LOG_FILE):
        return {"history": []}

    with open(DATA_LOG_FILE, "r") as f:
        logs = json.load(f)

    return {"history": logs}

@app.get("/ping")
def ping():
    return {"message": "pong"}

@app.get("/")
def root():
    return {"message": "Air Sensor API is running"}

@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
def serve_manifest():
    return FileResponse(".well-known/ai-plugin.json", media_type="application/json")

@app.get("/openapi.yaml", include_in_schema=False)
def serve_openapi():
    return FileResponse("openapi.yaml", media_type="text/yaml")
