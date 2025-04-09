from fastapi import FastAPI, Request, HTTPException
import asyncio
import os
from dotenv import load_dotenv
from viam.rpc.dial import DialOptions
from viam.robot.client import RobotClient
from viam.components.sensor import Sensor

load_dotenv()

app = FastAPI()

LOCAL_API_KEY = os.getenv("LOCAL_API_KEY")

# EPA AQI Breakpoints for PM2.5 (ug/m3)
# Based on 24-hour average
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
    # Use pm2_5_atm or pm2_5_CF1 if available
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

@app.get("/ping")
def ping():
    return {"message": "pong"}

@app.get("/")
def root():
    return {"message": "Air Sensor API is running"}
