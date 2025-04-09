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

def get_robot_options():
    return RobotClient.Options.with_api_key(
        api_key=os.getenv("VIAM_API_KEY"),
        api_key_id=os.getenv("VIAM_API_KEY_ID")
    )

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

        return readings
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