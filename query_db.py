import json
import os
import sqlite3
from typing import Dict, Any, List, Optional
from openai import OpenAI

# -------------------------
# File paths and settings
# -------------------------
JSONL_PATH = "synthetic_clauses.jsonl"
SQL_DB_PATH = "clauses.db"
TABLE_NAME = "clauses"

# Initialize OpenAI client
oai_client = OpenAI(api_key="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")

def load_clauses_from_jsonl() -> List[str]:
    """Load clauses from JSONL file."""
    if not os.path.exists(JSONL_PATH):
        raise FileNotFoundError(f"JSONL file {JSONL_PATH} not found. Please run synthesize_db.py first.")
    
    clauses = []
    with open(JSONL_PATH, 'r') as f:
        for line in f:
            data = json.loads(line)
            clauses.append(data['provision'])
    return clauses

def extract_fields_from_clause(clause: str, fields: List[str]) -> Dict[str, Any]:
    """Extract specified fields from a clause using LLM."""
    try:
        fields_str = ", ".join(fields)
        prompt = f"""
        Extract the following fields from this clause: {fields_str}
        
        Clause: {clause}
        
        For numeric fields:
        - Return the numeric value without currency symbols or commas
        - For percentages, return the decimal value (e.g., 10% should be 0.1)
        - If no numeric value is found, return null
        
        For date fields:
        - Return dates in YYYY-MM-DD format
        - If no date is found, return null
        
        For text fields:
        - Return the exact text found
        - If no text is found, return null
        
        Return ONLY a JSON object with the extracted fields.
        """
        
        response = oai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an extraction agent."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        result['clause'] = clause
        return result
        
    except Exception as e:
        print(f"[Error] Extraction failed: {str(e)}")
        return {field: None for field in fields}

def store_records_sql(records: List[Dict[str, Any]], db_path: str, table_name: str) -> Dict[str, str]:
    """Store records in SQLite database with inferred schema."""
    schema: Dict[str, str] = {}
    sample = records[0]
    
    # Create field mapping and infer schema
    field_mapping = {}
    for col in sample.keys():
        sanitized_col = col.replace(" ", "_").lower()
        field_mapping[col] = sanitized_col
        vals = [r[col] for r in records if r.get(col) is not None]
        schema[sanitized_col] = "REAL" if any(isinstance(v, (int, float)) for v in vals) else "TEXT"

    # Create table
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cols_ddl = []
    for col, dtype in schema.items():
        cols_ddl.append(f'"{col}" {dtype}')
    
    ddl = f'DROP TABLE IF EXISTS "{table_name}"; CREATE TABLE "{table_name}" ({", ".join(cols_ddl)});'
    cur.executescript(ddl)

    # Insert records
    cols_list = [field_mapping[col] for col in sample.keys()]
    placeholders = ", ".join("?" for _ in cols_list)
    quoted_cols = ", ".join(f'"{col}"' for col in cols_list)
    insert_sql = f'INSERT INTO "{table_name}" ({quoted_cols}) VALUES ({placeholders})'
    
    transformed_rows = []
    for record in records:
        row = []
        for col in sample.keys():
            row.append(record.get(col))
        transformed_rows.append(row)
    
    cur.executemany(insert_sql, transformed_rows)
    conn.commit()
    conn.close()

    print(f"\nStored {len(transformed_rows)} rows with schema:")
    print(json.dumps(schema, indent=2))
    return schema

def load_schema() -> Dict[str, str]:
    """Load the database schema."""
    if not os.path.exists(SQL_DB_PATH):
        raise FileNotFoundError(f"Database file {SQL_DB_PATH} not found. Please run a query first.")
    
    conn = sqlite3.connect(SQL_DB_PATH)
    cur = conn.cursor()
    cur.execute(f'PRAGMA table_info("{TABLE_NAME}")')
    schema = {col[1]: "TEXT" for col in cur.fetchall()}
    conn.close()
    return schema

def generate_filter_sql(query: str, schema: Dict[str, str]) -> str:
    """Generate SQL query based on natural language query and schema."""
    schema_desc = ", ".join(f"{col} ({dtype})" for col, dtype in schema.items())
    prompt = f"""
    Given the SQL table structure: {schema_desc} and the query: '{query}'
    Generate a SQL query to retrieve rows from the table '{TABLE_NAME}'.
    
    Rules:
    1. For numeric fields (REAL type):
       - Use CAST(column AS REAL) for comparisons
       - Handle percentages as decimals (e.g., 0.1 for 10%)
       - Use >, <, >=, <=, = for numeric comparisons
       - Always exclude NULL values unless specifically requested
    2. For text fields:
       - Use LIKE for partial matches
       - Use = for exact matches
       - Always exclude NULL values unless specifically requested
    3. For date fields:
       - Use date format 'YYYY-MM-DD'
       - Use date comparison operators
       - Always exclude NULL values unless specifically requested
    4. Always quote column names with spaces using double quotes
    5. Use the exact table name '{TABLE_NAME}'
    6. If no specific condition is mentioned:
       - For a specific field query, return rows where that field is NOT NULL
       - For a general query, return all rows
    7. Always include the clause column in the results
    8. Use SELECT * to get all columns
    9. Use the exact column names from the schema
    
    Return only the SQL query.
    """
    try:
        resp = oai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a SQL query generation agent."},
                {"role": "user", "content": prompt}
            ]
        )
        sql = resp.choices[0].message.content.strip()
        sql = sql.replace("```sql", "").replace("```", "").strip().strip('"""')
        
        # Find the field being queried
        field_name = None
        for field in schema.keys():
            if field.lower() in query.lower():
                field_name = field
                break
                
        if field_name:
            # Always add a WHERE clause to filter out NULL values for the requested field
            if "WHERE" not in sql.upper():
                sql = f"SELECT * FROM {TABLE_NAME} WHERE \"{field_name}\" IS NOT NULL"
            else:
                # If there's already a WHERE clause, add the NOT NULL condition
                sql = sql.replace("WHERE", f"WHERE \"{field_name}\" IS NOT NULL AND")
        
        # Ensure we're selecting from the correct table
        if "FROM" not in sql.upper():
            sql = f"SELECT * FROM {TABLE_NAME}"
        elif not any(TABLE_NAME.lower() in part.lower() for part in sql.split()):
            sql = sql.replace("FROM", f"FROM {TABLE_NAME}")
            
        print(f"\nGenerated SQL query:\n{sql}")
        return sql
        
    except Exception as e:
        print(f"[Error] SQL generation failed: {e}")
        if field_name:
            return f'SELECT * FROM {TABLE_NAME} WHERE "{field_name}" IS NOT NULL'
        return f"SELECT * FROM {TABLE_NAME}"

def execute_query(sql: str) -> List[Dict[str, Any]]:
    """Execute SQL query and return results."""
    conn = sqlite3.connect(SQL_DB_PATH)
    cur = conn.cursor()
    try:
        # First, check if the table has any data
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        count = cur.fetchone()[0]
        print(f"Total rows in table: {count}")
        
        # Execute the main query
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        
        if not rows:
            print("\nNo results found. Checking table contents...")
            # Show a sample of the table contents
            cur.execute(f"SELECT * FROM {TABLE_NAME} LIMIT 5")
            sample_rows = cur.fetchall()
            if sample_rows:
                print("\nSample table contents:")
                for row in sample_rows:
                    print(json.dumps(dict(zip(cols, row)), indent=2))
            return []
        else:
            print(f"\nFound {len(rows)} results:")
            results = []
            for row in rows:
                result = dict(zip(cols, row))
                print(json.dumps(result, indent=2))
                results.append(result)
            return results
                
    except sqlite3.Error as e:
        print(f"SQL Error: {e}")
        print("Attempting to fix and retry...")
        # Try to fix common issues
        fixed_sql = sql.replace("clause", TABLE_NAME)
        print(f"Retrying with fixed SQL:\n{fixed_sql}\n")
        try:
            cur.execute(fixed_sql)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []
            if rows:
                print(f"\nFound {len(rows)} results after fix:")
                results = []
                for row in rows:
                    result = dict(zip(cols, row))
                    print(json.dumps(result, indent=2))
                    results.append(result)
                return results
            else:
                print("\nNo results found after fix.")
                return []
        except sqlite3.Error as e2:
            print(f"Second attempt failed: {e2}")
            return []
    finally:
        conn.close()

def process_query(query: str) -> List[Dict[str, Any]]:
    """Process a natural language query and return results."""
    print(f"\nProcessing query: {query}")
    
    try:
        # Load clauses from JSONL
        clauses = load_clauses_from_jsonl()
        print(f"\nLoaded {len(clauses)} clauses from JSONL")
        
        # Extract fields from clauses
        fields_to_extract = ['company']  # Start with basic fields
        records = [extract_fields_from_clause(c, fields_to_extract) for c in clauses]
        
        # Store in database
        schema = store_records_sql(records, SQL_DB_PATH, TABLE_NAME)
        print(f"\nAvailable fields: {', '.join(schema.keys())}")
        
        # Generate and execute SQL
        sql = generate_filter_sql(query, schema)
        results = execute_query(sql)
        
        return results
        
    except Exception as e:
        print(f"Error processing query: {e}")
        return []

if __name__ == "__main__":
    while True:
        query = input("\nEnter your query (or 'quit' to exit): ")
        if query.lower() == 'quit':
            break
        process_query(query) 