import pandas as pd
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 250)
pd.set_option('display.max_colwidth', 40)
path = r"C:\Users\RST\Downloads\CHD 1 Sewadar List.xlsx"
xl = pd.ExcelFile(path)
print("SHEETS:", xl.sheet_names)
for sheet in xl.sheet_names:
    df = pd.read_excel(path, sheet_name=sheet, dtype=str)
    print("\n==== SHEET:", sheet, "shape:", df.shape, "====")
    print("COLUMNS:", list(df.columns))
    print("\n-- first 10 rows --")
    print(df.head(10).to_string())
    print("\n-- last 5 rows --")
    print(df.tail(5).to_string())
