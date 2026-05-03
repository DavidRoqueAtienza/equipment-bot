import pandas as pd

FILE_PATH = "asset_tracker.xlsx"
SERIAL_COLUMN = "Serial Number"
ID_REQUEST_COLUMN = "ID request"

serial_to_find = input("Enter Serial Number: ").strip()
command = input("Enter command (OUT OExxx or RETURN): ").strip()

df = pd.read_excel(FILE_PATH)
df.columns = df.columns.str.strip()

df[SERIAL_COLUMN] = df[SERIAL_COLUMN].astype(str).str.strip()

result = df[df[SERIAL_COLUMN].str.upper() == serial_to_find.upper()]

if result.empty:
    print(f"No equipment found with Serial Number: {serial_to_find}")
else:
    index = result.index[0]
    command_upper = command.upper()

    if command_upper.startswith("OUT"):
        parts = command.split()

        if len(parts) < 2:
            print("Error: use OUT OExxx")
        else:
            id_request = parts[1].strip()
            df.at[index, ID_REQUEST_COLUMN] = id_request

            df.to_excel(FILE_PATH, index=False)

            print("\nUpdated successfully:")
            print(f"Serial Number: {serial_to_find}")
            print(f"ID request: {id_request}")

    elif command_upper == "RETURN":
        df.at[index, ID_REQUEST_COLUMN] = ""

        df.to_excel(FILE_PATH, index=False)

        print("\nUpdated successfully:")
        print(f"Serial Number: {serial_to_find}")
        print("ID request cleared")

    else:
        print("Unknown command. Use OUT OExxx or RETURN")