import os
import cv2
import smartsheet

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from flask import Flask
import threading


# ===== CONFIG =====

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SMARTSHEET_TOKEN = os.getenv("SMARTSHEET_TOKEN")
SHEET_ID = int(os.getenv("SHEET_ID"))

SERIAL_COLUMN = "Serial Number"
ID_REQUEST_COLUMN = "ID request"

smartsheet_client = smartsheet.Smartsheet(SMARTSHEET_TOKEN)


# ===== HELPERS =====

def normalize_value(value):
    if value is None:
        return ""

    value = str(value).strip()

    if value.endswith(".0"):
        value = value[:-2]

    return value


def get_help_message(serial=None):
    message = (
        "❌ Command not recognized.\n\n"
        "Use one of these commands:\n\n"
        "➡️ OUT OExxx\n"
        "➡️ RETURN\n\n"
        "Examples:\n"
        "213260 OUT OE123\n"
        "213260 RETURN"
    )

    if serial:
        message += (
            "\n\nWith the detected serial:\n"
            f"{serial} OUT OE123\n"
            f"{serial} RETURN"
        )

    return message


# ===== QR / BARCODE READER =====

def read_barcode(file_path):
    image = cv2.imread(file_path)

    if image is None:
        return ""

    detector = cv2.QRCodeDetector()
    data, bbox, _ = detector.detectAndDecode(image)

    if not data:
        return ""

    return normalize_value(data)


# ===== SERIAL DETECTION =====

def detect_serial(file_path):
    barcode_value = read_barcode(file_path)

    if barcode_value:
        return barcode_value, "barcode"

    return "", "none"


# ===== SMARTSHEET UPDATE =====

def update_smartsheet(serial, command):
    try:
        serial_clean = normalize_value(serial)

        sheet = smartsheet_client.Sheets.get_sheet(SHEET_ID)

        columns = {col.title.strip(): col.id for col in sheet.columns}

        if SERIAL_COLUMN not in columns:
            return f"Column not found in Smartsheet: {SERIAL_COLUMN}"

        if ID_REQUEST_COLUMN not in columns:
            return f"Column not found in Smartsheet: {ID_REQUEST_COLUMN}"

        serial_col_id = columns[SERIAL_COLUMN]
        id_request_col_id = columns[ID_REQUEST_COLUMN]

        target_row = None

        for row in sheet.rows:
            for cell in row.cells:
                if cell.column_id == serial_col_id:
                    cell_value = normalize_value(cell.value)

                    if cell_value.upper() == serial_clean.upper():
                        target_row = row
                        break

            if target_row:
                break

        if target_row is None:
            return f"Equipment not found with Serial Number: {serial_clean}"

        command = command.strip()
        command_upper = command.upper()

        if command_upper.startswith("OUT"):
            parts = command.split()

            if len(parts) < 2:
                return get_help_message(serial_clean)

            new_id_request = parts[1].strip()

        elif command_upper == "RETURN":
            new_id_request = ""

        else:
            return get_help_message(serial_clean)

        new_row = smartsheet.models.Row()
        new_row.id = target_row.id

        new_cell = smartsheet.models.Cell()
        new_cell.column_id = id_request_col_id
        new_cell.value = new_id_request

        new_row.cells.append(new_cell)

        smartsheet_client.Sheets.update_rows(SHEET_ID, [new_row])

        if new_id_request:
            return (
                "✅ Update successful\n"
                f"Serial Number: {serial_clean}\n"
                f"ID request: {new_id_request}"
            )

        return (
            "✅ Return successful\n"
            f"Serial Number: {serial_clean}\n"
            "ID request cleared"
        )

    except Exception as e:
        return f"Smartsheet error: {e}"


# ===== TEXT MESSAGE HANDLER =====

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    try:
        serial, command = text.split(maxsplit=1)
    except ValueError:
        await update.message.reply_text(get_help_message())
        return

    response = update_smartsheet(serial, command)
    await update.message.reply_text(response)


# ===== PHOTO HANDLER =====

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Photo received. Processing...")

    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()

        file_path = "temp_image.jpg"
        await file.download_to_drive(file_path)

        detected_serial, method = detect_serial(file_path)

        if not detected_serial:
            await update.message.reply_text(
                "No serial detected. Please take a clearer photo of the QR/barcode."
            )
            return

        caption = update.message.caption

        if caption:
            command = caption.strip()
            response = update_smartsheet(detected_serial, command)

            await update.message.reply_text(
                f"Serial detected: {detected_serial}\n"
                f"Method: {method}\n\n"
                f"{response}"
            )

        else:
            await update.message.reply_text(
                f"Serial detected: {detected_serial}\n"
                f"Method: {method}\n\n"
                "Now send one of these commands:\n"
                f"{detected_serial} OUT OE123\n"
                f"{detected_serial} RETURN\n\n"
                "Or send the photo with caption:\n"
                "OUT OE123\n"
                "RETURN"
            )

    except Exception as e:
        await update.message.reply_text(f"Image processing error: {e}")


# ===== KEEP ALIVE SERVER =====

app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "Bot is alive"

@app_web.route("/health")
def health():
    return "OK"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)


# ===== MAIN =====

if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        raise ValueError("Missing TELEGRAM_TOKEN environment variable")

    if not SMARTSHEET_TOKEN:
        raise ValueError("Missing SMARTSHEET_TOKEN environment variable")

    if not SHEET_ID:
        raise ValueError("Missing SHEET_ID environment variable")

	threading.Thread(target=run_web, daemon=True).start()    
	app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("Bot running...")
    app.run_polling()
