import pandas as pd

file_path = "asset_tracker.xlsx"

df = pd.read_excel(file_path)

print("\nColumnas del archivo:")
print(df.columns)

print("\nPrimeras filas:")
print(df.head())