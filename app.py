from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd

FILE_PATH = "asset_tracker.xlsx"
SERIAL_COLUMN = "Serial Number"
ID_REQUEST_COLUMN = "ID request"

app = FastAPI()


class BotRequest(BaseModel):
    serial_number: str
    command: str


@app.get("/")
def home():
    return {"message": "Equipment chatbot is running"}


@app.post("/update")
def update_asset(request: BotRequest):
    df = pd.read_excel(FILE_PATH)
    df.columns = df.columns.str.strip()

    df[SERIAL_COLUMN] = df[SERIAL_COLUMN].astype(str).str.strip()

    serial = request.serial_number.strip()
    command = request.command.strip()
    command_upper = command.upper()

    result = df[df[SERIAL_COLUMN].str.upper() == serial.upper()]

    if result.empty:
        return {
            "status": "not_found",
            "message": f"No equipment found with Serial Number: {serial}"
        }

    index = result.index[0]

    if command_upper.startswith("OUT"):
        parts = command.split()

        if len(parts) < 2:
            return {
                "status": "error",
                "message": "Use OUT OExxx"
            }

        id_request = parts[1].strip()
        df.at[index, ID_REQUEST_COLUMN] = id_request
        df.to_excel(FILE_PATH, index=False)

        return {
            "status": "updated",
            "serial_number": serial,
            "id_request": id_request,
            "message": f"ID request updated to {id_request}"
        }

    if command_upper == "RETURN":
        df.at[index, ID_REQUEST_COLUMN] = ""
        df.to_excel(FILE_PATH, index=False)

        return {
            "status": "updated",
            "serial_number": serial,
            "id_request": "",
            "message": "ID request cleared"
        }

    return {
        "status": "error",
        "message": "Unknown command. Use OUT OExxx or RETURN"
    }