import pandas as pd
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 250)
pd.set_option('display.max_colwidth', 60)
path = r"C:\Users\RST\Downloads\CHD 1 Sewadar List.xlsx"
df = pd.read_excel(path, sheet_name="Sheet1", dtype=str)

def norm(s):
    if pd.isna(s):
        return ""
    return str(s).strip().upper()

df['_badge'] = df['Badge_Number'].map(norm)
df['_old'] = df['Old_Badge_Number'].map(norm)

print("Total rows:", len(df))
print("Rows with non-empty Badge_Number:", (df['_badge']!='').sum())
print("Rows with empty Badge_Number:", (df['_badge']=='').sum())

print("\nDistinct Old_Badge_Number values among rows with EMPTY Badge_Number (value counts, top 20):")
print(df.loc[df['_badge']=='', '_old'].value_counts().head(20))

print("\nDoes any Badge_Number value match the pattern of an old-style code (not starting with 'MO')? Count:")
non_mo = df[(df['_badge']!='') & (~df['_badge'].str.startswith('MO'))]
print(len(non_mo))
print(non_mo[['Badge_Number','Old_Badge_Number','Sewadar_Name']].head(20).to_string())

print("\nFor rows with EMPTY Badge_Number, check if their Old_Badge_Number (excluding blank/'-'/'FORM' value also appears as the Old_Badge_Number of ANOTHER row that DOES have a non-empty Badge_Number (i.e. true duplicate old+new pair for the same old code):")
real_old_codes = df.loc[(df['_badge']=='') & (~df['_old'].isin(['', '-', 'FORM'])), '_old']
print("count of such standalone old-only codes:", len(real_old_codes))
dupe_old_in_new_rows = df[(df['_badge']!='') & (df['_old'].isin(set(real_old_codes)))]
print("How many of those old codes are ALSO referenced by a row that has a new Badge_Number:", len(dupe_old_in_new_rows))
print(dupe_old_in_new_rows[['Badge_Number','Old_Badge_Number','Sewadar_Name']].head(20).to_string())

print("\nCheck for duplicate Badge_Number values (exact duplicates):")
dup_badges = df[df['_badge']!=''].groupby('_badge').size()
dup_badges = dup_badges[dup_badges>1]
print(len(dup_badges), "duplicated Badge_Number values")
print(dup_badges.head(20))

print("\nCheck for duplicate (Sewadar_Name + Father_Husband_Name) combos appearing in MULTIPLE rows:")
df['_key'] = df['Sewadar_Name'].map(norm) + '|' + df['Father_Husband_Name'].map(norm)
dup_people = df.groupby('_key').size()
dup_people = dup_people[dup_people>1]
print(len(dup_people), "names appearing more than once")
sample_key = dup_people.index[0] if len(dup_people) else None
if sample_key:
    print(df[df['_key']==sample_key][['Badge_Number','Old_Badge_Number','Sewadar_Name','Father_Husband_Name']].to_string())
