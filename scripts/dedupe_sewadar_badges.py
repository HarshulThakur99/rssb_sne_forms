"""
Sewadar Badge Dedup Script
==========================
The sewadar master list has duplicate rows for people who registered more than
once: an older row with no (or a legacy/placeholder) Badge_Number, and a newer
row where they were actually issued a current badge (Badge_Number populated).
This script finds, for every row with an empty Badge_Number, whether another
row for the SAME person (matched by Sewadar_Name + Father_Husband_Name + Centre)
already has a real Badge_Number. If so, that empty-badge row is a stale
duplicate and is dropped, keeping only the row with the current badge. Anyone
who never received a badge at all (no matching "new" row anywhere) is left
untouched.

Usage:
    python scripts/dedupe_sewadar_badges.py <input.xlsx|input.csv> <output.csv>

Writes two files:
    <output.csv>          - the cleaned dataset, ready to upload
    <output>_removed.csv  - every row that was dropped, for manual review
"""

import csv
import sys

import pandas as pd
import openpyxl


def normalize(value):
    if pd.isna(value):
        return ""
    return str(value).strip().upper()


def load_table(path):
    """Returns (header, dataframe). Header is read from the raw file so that
    duplicate column names (e.g. 'Age' appearing twice) are preserved exactly."""
    if path.lower().endswith(('.xlsx', '.xlsm')):
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        header = [("" if c.value is None else str(c.value).strip()) for c in next(ws.iter_rows(min_row=1, max_row=1))]
        df = pd.read_excel(path, sheet_name=ws.title, dtype=str)
    else:
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        header = list(df.columns)
    return header, df


def write_csv(path, header, frame):
    values = frame.iloc[:, :len(header)].fillna('').values.tolist()
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(values)


def process(input_path, output_path, removed_path):
    header, df = load_table(input_path)

    badge = df['Badge_Number'].map(normalize)
    name = df['Sewadar_Name'].map(normalize)
    key = name + '|' + df['Father_Husband_Name'].map(normalize) + '|' + df['Centre'].map(normalize)

    new_keys = set(key[badge != ''])
    is_duplicate_of_new = (badge == '') & (name != '') & key.isin(new_keys)

    kept = df[~is_duplicate_of_new]
    removed = df[is_duplicate_of_new]

    write_csv(output_path, header, kept)
    write_csv(removed_path, header, removed)

    print(f"Total rows read:              {len(df)}")
    print(f"Rows with a current badge:    {(badge != '').sum()}")
    print(f"Stale duplicate rows removed: {len(removed)} (superseded by a current-badge row for the same person)")
    print(f"Rows kept:                    {len(kept)}")
    print(f"\nCleaned file written to: {output_path}")
    print(f"Removed rows saved to:   {removed_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/dedupe_sewadar_badges.py <input.xlsx|csv> <output.csv>")
        sys.exit(1)
    in_path, out_path = sys.argv[1], sys.argv[2]
    removed_out = out_path.rsplit('.', 1)[0] + '_removed.csv'
    process(in_path, out_path, removed_out)
