import sqlite3
import json
from query_processor import extract_fields_from_clause, store_records_sql

FIELDS = [
    "company",
    "effective_date",
    "expiration_date",
    "amount",
    "fee",
    "risk_score",
    "risk_level",
    "payment_frequency",
    "currency",
    "term_length",
    "term_unit",
    "risk_factors"
]

DB_PATH = "clauses.db"
TABLE_NAME = "clauses"


def clean_record(record):
    """Clean record to handle list values and other SQLite incompatible types."""
    cleaned = {}
    for key, value in record.items():
        if isinstance(value, list):
            # Convert lists to JSON strings
            cleaned[key] = json.dumps(value)
        elif isinstance(value, dict):
            # Convert dicts to JSON strings
            cleaned[key] = json.dumps(value)
        else:
            cleaned[key] = value
    return cleaned


def main():
    # Connect to the existing database
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(f'SELECT clause FROM {TABLE_NAME}')
    clauses = [row[0] for row in cur.fetchall()]
    conn.close()

    print(f"Extracting fields for {len(clauses)} clauses...")
    records = []
    for i, clause in enumerate(clauses):
        print(f"Processing clause {i+1}/{len(clauses)}...")
        record = extract_fields_from_clause(clause, FIELDS)
        cleaned_record = clean_record(record)
        records.append(cleaned_record)

    print("Storing structured records in the database...")
    store_records_sql(records, DB_PATH, TABLE_NAME)
    print("Done! The database is now structured and ready for querying.")

if __name__ == "__main__":
    main() 