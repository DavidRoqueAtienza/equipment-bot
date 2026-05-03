import re
import cv2
import smartsheet
import pytesseract
import os
from pyzbar.pyzbar import decode
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# ===== CONFIG =====



TELEGRAM_TOKEN = os.getenv("7696157057:AAEVHhM7HRdUHYHq_EExLJ3fu39D8qJkzr0")
SMARTSHEET_TOKEN = os.getenv("M3vmRneTpdBhPuLqYQecdJKjNqNjY5eHR4meM")
SHEET_ID = int(os.getenv("2162883748122500"))


SERIAL_COLUMN = "Serial Number"
ID_REQUEST_COLUMN = "ID request"

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

smartsheet_client = smartsheet.Smartsheet(SMARTSHEET_TOKEN)

# ===== HELPERS =====
def normalize_value(value):
    if value is None:
        return ""

    value = str(value).strip()

    if value.endswith(".0"):
        value = value[:-2]

    return value


# ===== BARCODE READER =====
def read_barcode(file_path):
    image = cv2.imread(file_path)

    if image is None:
        return ""

    barcodes = decode(image)

    if not barcodes:
        return ""

    return normalize_value(barcodes[0].data.decode("utf-8"))


# ===== OCR FALLBACK =====
def read_ocr(file_path):
    try:
        image = cv2.imread(file_path)

        if image is None:
            return ""

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

        thresh = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )[1]

        config = "--psm 6 -c tessedit_char_whitelist=0123456789"
        text = pytesseract.image_to_string(thresh, config=config)

        numbers = re.findall(r"\d+", text)
        candidates = [n for n in numbers if len(n) >= 5]

        if candidates:
            return normalize_value(max(candidates, key=len))

        if numbers:
            return normalize_value(max(numbers, key=len))

        return ""

    except Exception:
        return ""


# ===== SERIAL DETECTION =====
def detect_serial(file_path):
    barcode_value = read_barcode(file_path)

    if barcode_value:
        return barcode_value, "barcode"

    ocr_value = read_ocr(file_path)

    if ocr_value:
        return ocr_value, "ocr"

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
                return "Invalid command. Use: OUT OExxx"

            new_id_request = parts[1].strip()

        elif command_upper == "RETURN":
            new_id_request = ""

        else:
            return "Unknown command. Use: OUT OExxx or RETURN"

        new_row = smartsheet.models.Row()
        new_row.id = target_row.id

        new_cell = smartsheet.models.Cell()
        new_cell.column_id = id_request_col_id
        new_cell.value = new_id_request

        new_row.cells.append(new_cell)

        smartsheet_client.Sheets.update_rows(SHEET_ID, [new_row])

        if new_id_request:
            return (
                "Update successful\n"
                f"Serial Number: {serial_clean}\n"
                f"ID request: {new_id_request}"
            )

        return (
            "Return successful\n"
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
        await update.message.reply_text(
            "Use this format:\n"
            "213260 OUT OE123\n"
            "213260 RETURN"
        )
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
                "No serial detected. Please take a clearer photo of the barcode."
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
                f"{detected_serial} OUT OExxx\n"
                f"{detected_serial} RETURN\n\n"
                "Or send the photo with caption:\n"
                "OUT OExxx\n"
                "RETURN"
            )

    except Exception as e:
        await update.message.reply_text(f"Image processing error: {e}")


# ===== MAIN =====
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("Bot running...")
    app.run_polling()