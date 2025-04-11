import os
import json
import asyncio
from datetime import datetime, timedelta

from viam.robot.client import RobotClient
from viam.components.sensor import Sensor

# Constants
PM25_BUCKETS = [
    (0.0, 12.0, "good"),
    (12.1, 35.4, "moderate"),
    (35.5, 55.4, "unhealthy for sensitive groups"),
    (55.5, 150.4, "unhealthy"),
    (150.5, 250.4, "very unhealthy"),
    (250.5, 500.0, "hazardous")
]

DATA_LOG_FILE = "air_quality_robot/air_quality_log.json"
LOG_INTERVAL_SECONDS = 300  # 5 minutes
MAX_LOG_DURATION = timedelta(hours=24)

# Robot connection
def get_robot_options():
    return RobotClient.Options.with_api_key(
        api_key=os.getenv("VIAM_AIRSENSOR_API_KEY"),
        api_key_id=os.getenv("VIAM_AIRSENSOR_API_KEY_ID")
    )

async def get_air_readings():
    try:
        options = get_robot_options()
        robot = await RobotClient.at_address(os.getenv("VIAM_AIRSENSOR_ROBOT_ADDR"), options)
        sensor = Sensor.from_robot(robot, os.getenv("VIAM_AIRSENSOR_NAME"))
        readings = await sensor.get_readings()
        await robot.close()

        return {
            "readings": readings,
            "status": assess_air_quality(readings)
        }
    except Exception as e:
        print("Error in get_air_readings:", e)
        return {"error": str(e)}

def bucket_pm25(value):
    for low, high, label in PM25_BUCKETS:
        if low <= value <= high:
            return label
    return "beyond index"

def assess_air_quality(readings):
    pm25 = readings.get("pm2_5_atm") or readings.get("pm2_5_CF1")
    return {"pm2_5_category": bucket_pm25(pm25)} if pm25 else {}

# Logging helper
async def start_logger():
    while True:
        data = await get_air_readings()
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

        # Trim logs to last 24 hours
        cutoff = datetime.utcnow() - MAX_LOG_DURATION
        logs = [
            entry for entry in logs
            if datetime.fromisoformat(entry["timestamp"]) > cutoff
        ]

        with open(DATA_LOG_FILE, "w") as f:
            json.dump(logs, f)

        await asyncio.sleep(LOG_INTERVAL_SECONDS)

def get_air_history():
    if not os.path.exists(DATA_LOG_FILE):
        return []
    with open(DATA_LOG_FILE, "r") as f:
        return json.load(f)
