import json
import sqlite3
from query_processor import extract_fields_from_clause, store_records_sql

JSONL_PATH = "synthetic_clauses.jsonl"
DB_PATH = "clauses.db"
TABLE_NAME = "clauses"

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
    # Load clauses from JSONL
    clauses = []
    with open(JSONL_PATH, 'r') as f:
        for line in f:
            data = json.loads(line)
            clauses.append(data['provision'])
    
    print(f"Loaded {len(clauses)} clauses from JSONL")
    
    # Extract fields from each clause
    print("Extracting fields from clauses...")
    records = []
    for i, clause in enumerate(clauses):
        print(f"Processing clause {i+1}/{len(clauses)}...")
        record = extract_fields_from_clause(clause, FIELDS)
        cleaned_record = clean_record(record)
        records.append(cleaned_record)
    
    # Store in database
    print("Storing records in database...")
    store_records_sql(records, DB_PATH, TABLE_NAME)
    
    print("Done! Database is ready for querying.")

if __name__ == "__main__":
    main() 