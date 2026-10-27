import pandas as pd
pd.set_option('display.max_rows', None)
path = r"C:\Users\RST\Downloads\CHD 1 Sewadar List.xlsx"
df = pd.read_excel(path, sheet_name="Sheet1", dtype=str)

def norm(s):
    if pd.isna(s):
        return ""
    return str(s).strip().upper()

df['_badge'] = df['Badge_Number'].map(norm)
df['_old'] = df['Old_Badge_Number'].map(norm)

empty_badge = df[df['_badge']=='']
print("FULL value_counts of Old_Badge_Number for empty-Badge_Number rows:")
print(empty_badge['_old'].value_counts().to_string())

print("\nDistinct Centre values overall:")
print(df['Centre'].value_counts(dropna=False).to_string())

# Now apply name+father+centre matching
df['_key'] = df['Sewadar_Name'].map(norm) + '|' + df['Father_Husband_Name'].map(norm) + '|' + df['Centre'].map(norm)
new_rows = df[df['_badge']!='']
legacy_candidates = df[(df['_badge']=='') & (~df['_old'].isin(['', '-', 'FORM', 'TEMP FORM', 'SEWA FORM', 'CANCELLED', 'OPEN', 'FORM AVAILABLE', 'PATHI']))]
print("\nLegacy candidate rows (empty badge, old value not a placeholder):", len(legacy_candidates))

new_keys = new_rows.groupby('_key').size()
match_counts = legacy_candidates['_key'].map(lambda k: new_keys.get(k, 0))
print("\nOf legacy candidates, how many have exactly 1 matching new row (by name+father+centre):", (match_counts==1).sum())
print("how many have 0 matches:", (match_counts==0).sum())
print("how many have 2+ matches (ambiguous):", (match_counts>=2).sum())

print("\nSample of legacy candidates with 0 matches (first 15):")
print(legacy_candidates[match_counts==0][['Badge_Number','Old_Badge_Number','Sewadar_Name','Father_Husband_Name','Centre']].head(15).to_string())

print("\nSample of legacy candidates with 2+ matches (first 10), if any:")
print(legacy_candidates[match_counts>=2][['Badge_Number','Old_Badge_Number','Sewadar_Name','Father_Husband_Name','Centre']].head(10).to_string())
