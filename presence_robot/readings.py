import os
import asyncio
from datetime import datetime

from viam.robot.client import RobotClient
from viam.components.sensor import Sensor

LOG_INTERVAL_SECONDS = 30  # or whatever polling interval you prefer

# Robot connection
def get_robot_options():
    return RobotClient.Options.with_api_key(
        api_key=os.getenv("VIAM_MMWAVE_API_KEY"),
        api_key_id=os.getenv("VIAM_MMWAVE_API_KEY_ID")
    )

async def get_presence_readings():
    try:
        options = get_robot_options()
        robot = await RobotClient.at_address(os.getenv("VIAM_MMWAVE_ROBOT_ADDR"), options)
        sensor = Sensor.from_robot(robot, os.getenv("VIAM_MMWAVE_NAME"))
        readings = await sensor.get_readings()
        await robot.close()

        print(f"[DEBUG] Raw readings: {readings} (type: {type(readings)})")
        status = readings.get("detection_status") if isinstance(readings, dict) else None

        return {
            "readings": readings,
            "presence_state": status
        }
    except Exception as e:
        print("Error in get_presence_readings:", e)
        return {"error": str(e)}

# Logger (for console/debug only, no file)
async def start_logger():
    while True:
        result = await get_presence_readings()
        print(f"[{datetime.utcnow().isoformat()}] Presence: {result}")
        await asyncio.sleep(LOG_INTERVAL_SECONDS)
