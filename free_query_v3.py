import json
import os
import sqlite3
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, create_model
from openai import OpenAI
from tqdm import tqdm

# Try to import streamlit for secrets, fallback to environment variable
def get_openai_client():
    """Get OpenAI client with proper API key handling"""
    try:
        import streamlit as st
        # For Streamlit Cloud deployment - check if secrets are available
        if hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
            return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        else:
            # Streamlit is available but secrets are not configured
            raise KeyError("OPENAI_API_KEY not in streamlit secrets")
    except (ImportError, KeyError):
        # For local development - you can set this as an environment variable
        # or temporarily put your key here for local testing
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            api_key = 'your_api_key_here_for_local_testing'
        return OpenAI(api_key=api_key)

# Legacy support - but we'll use get_openai_client() in functions
oai_client = get_openai_client()

# -------------------------
# File paths and settings
# -------------------------
LEDGAR_PATH  = "synthetic_clauses.jsonl"
CLAUSE_LIMIT = 10
SQL_DB_PATH  = "clauses.db"
TABLE_NAME   = "clauses"

# -------------------------
# Utility Functions
# -------------------------
def random_date() -> str:
    start = datetime(2000, 1, 1)
    end   = datetime(2030, 12, 31)
    delta_days = (end - start).days
    res = (start + timedelta(days=random.randint(0, delta_days))).strftime("%Y-%m-%d")
    # print(res)
    return res

def _try_parse_float(s: str) -> bool:
    try:
        float(s)
        return True
    except:
        return False

def _try_parse_date(s: str) -> bool:
    try:
        datetime.fromisoformat(s)
        return True
    except:
        return False

def infer_sql_column_type_rule_list(
    values: List[Any], column_name: str, threshold: float = 0.8
) -> str:
    """
    Use LLM to infer SQL column type based on column name and sample values.
    Returns "REAL", "DATE", or "TEXT".
    """
    try:
        # Get a sample of values (up to 5) for context
        sample_values = [str(v) for v in values if v is not None][:5]
        sample_str = ", ".join(sample_values) if sample_values else "No values"

        prompt = f"""
        Given a column named '{column_name}' with sample values: [{sample_str}]
        Determine the most appropriate SQL column type from these options:
        - REAL: for numeric values, including money amounts
        - DATE: for date values in any format
        - TEXT: for any other type of data

        Return ONLY one of these exact words: REAL, DATE, or TEXT
        """

        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a SQL schema inference agent. Return only the type name."},
                {"role": "user", "content": prompt}
            ]
        )

        result = response.choices[0].message.content.strip().upper()
        
        # Validate the response is one of the expected types
        if result not in ["REAL", "DATE", "TEXT"]:
            print(f"[Warning] LLM returned unexpected type '{result}', defaulting to TEXT")
            return "TEXT"
            
        return result

    except Exception as e:
        print(f"[Error] Type inference failed: {str(e)}, defaulting to TEXT")
        return "TEXT"

def sanitize_field_name(field_name: str) -> str:
    """
    Sanitize field name for SQLite by replacing spaces with underscores
    and ensuring it's a valid identifier.
    """
    # Replace spaces and special characters with underscores
    sanitized = ''.join(c if c.isalnum() else '_' for c in field_name.strip().lower())
    # Ensure it starts with a letter or underscore
    if not sanitized[0].isalpha() and sanitized[0] != '_':
        sanitized = '_' + sanitized
    return sanitized

# -------------------------
# SQL Storage (sqlite3 only)
# -------------------------
def store_records_sql(
    records: List[Dict[str, Any]],
    db_path: str,
    table_name: str,
    parent_field: Optional[str] = None
) -> Dict[str, str]:
    """
    Given a list of dict-records, infer each column's SQL type,
    CREATE TABLE (dropping existing), and BULK INSERT.
    Returns the inferred schema mapping col → ("REAL"|"DATE"|"TEXT").
    """
    # Infer schema
    schema: Dict[str, str] = {}
    sample = records[0]
    
    # Create mapping of original field names to sanitized names
    field_mapping = {}
    for col in sample.keys():
        sanitized_col = sanitize_field_name(col)
        field_mapping[col] = sanitized_col
        vals = [r[col] for r in records if r.get(col) is not None]
        schema[sanitized_col] = infer_sql_column_type_rule_list(vals, col)

    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    # Add parent_field to schema if provided
    if parent_field:
        sanitized_parent = sanitize_field_name(parent_field)
        schema['parent_field'] = "TEXT"
        field_mapping['parent_field'] = 'parent_field'  # Add parent_field to mapping
        for record in records:
            record['parent_field'] = parent_field

    # Ensure clause column exists in schema
    if 'clause' not in schema:
        schema['clause'] = "TEXT"
        field_mapping['clause'] = 'clause'

    # Re-create table
    cols_ddl = []
    for col, dtype in schema.items():
        sql_type = "REAL" if dtype == "REAL" else "TEXT"
        cols_ddl.append(f'"{col}" {sql_type}')
    ddl = f'DROP TABLE IF EXISTS "{table_name}"; CREATE TABLE "{table_name}" ({", ".join(cols_ddl)});'
    cur.executescript(ddl)

    # Bulk insert
    cols_list = [field_mapping[col] for col in sample.keys()]
    if parent_field:
        cols_list.append('parent_field')
    if 'clause' not in cols_list:
        cols_list.append('clause')
    placeholders = ", ".join("?" for _ in cols_list)
    quoted_cols = ", ".join(f'"{col}"' for col in cols_list)
    insert_sql = f'INSERT INTO "{table_name}" ({quoted_cols}) VALUES ({placeholders})'
    
    # Transform records to use sanitized column names
    transformed_rows = []
    for record in records:
        row = []
        for col in sample.keys():
            row.append(record.get(col))
        if parent_field:
            row.append(record.get('parent_field'))
        if 'clause' not in sample.keys():
            row.append(record.get('clause'))
        transformed_rows.append(row)
    
    cur.executemany(insert_sql, transformed_rows)

    conn.commit()
    conn.close()

    print(f"Stored {len(transformed_rows)} rows into '{table_name}' with schema: {schema}")
    return schema

def load_records(db_path: str, table_name: str) -> List[Dict[str, Any]]:
    """Fetch all rows from a table as a list of dicts."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table_name}")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def infer_schema_from_records(records: List[Dict[str, Any]]) -> Dict[str, str]:
    """Re-infer schema by sampling existing table rows."""
    if not records:
        return {}
    schema = {}
    for col in records[0].keys():
        vals = [r[col] for r in records if r.get(col) is not None]
        schema[col] = infer_sql_column_type_rule_list(vals, col)
    return schema

def get_schema_description_list(schema: Dict[str, str]) -> str:
    """Build the plain-language schema description for prompts."""
    parts = []
    for col, dtype in schema.items():
        if dtype == "REAL":
            desc = "REAL (expected output: number)"
        elif dtype == "DATE":
            desc = "DATE (expected output: YYYY-MM-DD)"
        else:
            desc = "TEXT (expected output: string)"
        parts.append(f"{col} ({desc})")
    return ", ".join(parts)


# -------------------------
# Agent 3: Field Extraction Agent
# -------------------------
def extract_fields_from_clause(clause: str, fields: List[str]) -> Dict[str, Any]:
    """
    Extract specified fields from a clause using an LLM.
    """
    try:
        fields_str = ", ".join(f'"{f}"' for f in fields)
        prompt = f"""
        Extract the following fields from the clause below: {fields_str}
        
        Clause: "{clause}"
        
        Return ONLY a JSON object with the extracted fields.
        - If a field is not present, the value should be null.
        - If a date is found, format it as YYYY-MM-DD.
        """
        
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a field extraction agent. Return only JSON."},
                {"role": "user", "content": prompt}
            ]
        )
        
        extracted_data = json.loads(response.choices[0].message.content)
        
        # Add the original clause to the output
        extracted_data['clause'] = clause
        return extracted_data

    except Exception as e:
        print(f"Field extraction failed for clause: {clause[:50]}... Error: {str(e)}")
        return {"clause": clause}

# -------------------------
# Step 1: Construct DB from LEDGAR
# -------------------------
def construct_db_from_ledgar() -> (List[str], Dict[str, str]):
    """
    Load clauses from the LEDGAR JSONL file, extract initial fields,
    and store them in a new SQLite database.
    """
    print(f"Constructing database from '{LEDGAR_PATH}'...")
    with open(LEDGAR_PATH, "r") as f:
        # Load raw clauses from the JSONL file
        raw = [json.loads(line)["provision"] for line in f][:CLAUSE_LIMIT]

    # Add a random date to each clause for testing date functionality
    clauses = [
        c + (f" effective date: {random_date()}" if random.random() < 0.5 else "")
        for c in raw
    ]

    base_fields = ['company']
    records = [extract_fields_from_clause(c, base_fields) for c in tqdm(clauses)]
    schema  = store_records_sql(records, SQL_DB_PATH, TABLE_NAME)
    return base_fields, schema

# -------------------------
# Agent 1: Query Decision Agent
# -------------------------
def decide_query_type(query: str, known_fields: List[str]) -> str:
    """
    Decide if the query is a "hit" (can be answered by existing fields)
    or a "miss" (requires extracting new fields).
    """
    try:
        # Create a prompt that asks the model to classify the query
        known_fields_str = ", ".join(known_fields)
        prompt = f"""
        Given the available fields: [{known_fields_str}]
        
        Classify the following user query as either a "hit" or a "miss".
        - A "hit" means the query can be answered using only the available fields.
        - A "miss" means the query requires extracting new information not covered by the available fields.
        
        Query: "{query}"
        
        Return ONLY the word "hit" or "miss".
        """
        
        # Use a less powerful model for this simpler task
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a query classification agent."},
                {"role": "user", "content": prompt}
            ]
        )
        
        # The result should be either "hit" or "miss"
        result = response.choices[0].message.content.strip().lower()
        
        # Basic validation
        if result not in ["hit", "miss"]:
            print(f"[Warning] Unexpected classification: {result}, defaulting to 'miss'")
            return "miss"
            
        return result

    except Exception as e:
        print(f"[Error] Query classification failed: {str(e)}, defaulting to 'miss'")
        return "miss"


# -------------------------
# Agent 4: SQL Generation Agent
# -------------------------
def generate_filter_sql(
    query: str,
    schema: Dict[str, str],
    table_name: str = TABLE_NAME
) -> str:
    """
    Given a query and a db schema, use an LLM to generate a SQL WHERE clause.
    """
    try:
        schema_desc = get_schema_description_list(schema)
        prompt = f"""
        Given the database schema:
        - Table name: {table_name}
        - Columns: {schema_desc}
        
        Generate a SQL WHERE clause for the following user query.
        - Query: "{query}"
        - The clause should be syntactically correct for SQLite.
        - Do NOT include the "WHERE" keyword itself.
        - If a column is of type REAL, you may need to CAST it for comparison.
        - Return ONLY the SQL condition, without any markdown formatting, code blocks, or backticks.
        - Do NOT wrap the response in ```sql``` or any other formatting.
        
        IMPORTANT GUIDELINES:
        1. If the query is asking for content within clauses (like "clauses that contain X"), search within the 'clause' column using LIKE patterns
        2. Use LIKE '%keyword%' for text searches within clause content
        3. For queries about small companies, search for terms like 'small', 'SME', 'small to medium', 'small-sized' in the clause text
        4. If a specific field exists but might be empty, also search the clause text as a fallback
        5. Use OR conditions to search multiple related terms
        6. For duration/term queries, search for 'duration', 'term', 'period', 'months', 'years' in clause text
        7. For payment queries, search for 'payment', 'pay', 'fee', 'compensation', 'payable' in clause text
        
        Examples:
        - "Show amounts over 1000": CAST(amount AS REAL) > 1000
        - "Find clauses about small companies": clause LIKE '%small%' OR clause LIKE '%SME%' OR clause LIKE '%small to medium%'
        - "What clauses mention termination": clause LIKE '%termination%' OR clause LIKE '%terminate%'
        - "Find agreement duration": clause LIKE '%duration%' OR clause LIKE '%term%' OR clause LIKE '%period%' OR clause LIKE '%months%' OR clause LIKE '%years%'
        - "Find payment terms": clause LIKE '%payment%' OR clause LIKE '%pay%' OR clause LIKE '%fee%' OR clause LIKE '%compensation%' OR clause LIKE '%payable%'
        """
        
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a SQL generation agent for SQLite. Generate appropriate WHERE conditions for content searches. Return only the SQL condition without any formatting."},
                {"role": "user", "content": prompt}
            ]
        )
        
        result = response.choices[0].message.content.strip()
        
        # Clean up any remaining markdown formatting
        result = result.replace('```sql', '').replace('```', '').strip()
        
        return result
        
    except Exception as e:
        print(f"SQL generation failed: {str(e)}")
        return "1=0" # Return a condition that returns no results

def execute_generated_sql(sql_code: str, db_path: str):
    sql = sql_code.strip()
    
    # Clean up the SQL query - remove markdown formatting
    if sql.startswith('```sql'):
        sql = sql[6:]  # Remove ```sql
    if sql.startswith('```'):
        sql = sql[3:]   # Remove ```
    if sql.endswith('```'):
        sql = sql[:-3]  # Remove trailing ```
    
    # Remove comments and clean up
    lines = sql.split('\n')
    clean_lines = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith('--'):
            clean_lines.append(line)
    sql = ' '.join(clean_lines)
    
    # Remove triple quotes if present (but not individual quotes)
    if sql.startswith('"""') and sql.endswith('"""'):
        sql = sql[3:-3]
    elif sql.startswith("'''") and sql.endswith("'''"):
        sql = sql[3:-3]
    
    # Additional cleaning for common markdown artifacts
    sql = sql.replace('```sql', '').replace('```', '')
    sql = sql.strip()
    
    print(f"Executing SQL:\n{sql}\n")
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        for row in rows:
            print(dict(zip(cols, row)))
    except sqlite3.Error as e:
        print(f"SQL Error: {e}")
        print("Attempting to fix and retry...")
        # Try to fix common issues with column names and table name
        fixed_sql = sql.replace("clause", TABLE_NAME)
        fixed_sql = fixed_sql.replace("black company percentage", '"black_company_percentage"')
        print(f"Retrying with fixed SQL:\n{fixed_sql}\n")
        try:
            cur.execute(fixed_sql)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []
            for row in rows:
                print(dict(zip(cols, row)))
        except sqlite3.Error as e2:
            print(f"Fixed SQL also failed: {e2}")
            raise e2
    finally:
        conn.close()

# Agent 2: New Field Discovery Agent
# -------------------------
def decide_new_field(query: str, known_fields: List[str]) -> (str, Optional[str]):
    """
    From a "miss" query, decide what new field to extract.
    Also, try to find a parent field to optimize processing.
    """
    try:
        known_fields_str = ", ".join(known_fields)
        prompt = f"""
        A user query could not be answered with the available fields: [{known_fields_str}].
        
        User Query: "{query}"
        
        Based on this query, what is the single most likely new field the user wants to extract?
        - Name the field using snake_case (e.g., termination_fee, effective_date).
        - The field should be a column in a database.
        
        Also, does this new field seem to be a sub-category of any of the existing fields?
        - If yes, name the parent field from the available fields list.
        - If no, the parent field is "None".
        
        Return a JSON object with two keys: "new_field" and "parent_field".
        """
        
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a field discovery agent. Return only JSON."},
                {"role": "user", "content": prompt}
            ]
        )
        
        data = json.loads(response.choices[0].message.content)
        new_field = data.get("new_field")
        parent_field = data.get("parent_field")
        
        if parent_field == "None" or parent_field not in known_fields:
            parent_field = None
            
        return new_field, parent_field

    except Exception as e:
        print(f"Field discovery failed: {str(e)}")
        # Fallback: create a simple field name from the query
        new_field = "extracted_" + query.lower().replace(" ", "_")[:20]
        return new_field, None

def merge_new_fields_to_main_table(
    new_table_name: str,
    new_field: str,
    parent_field: Optional[str],
    db_path: str,
    main_table: str = TABLE_NAME
) -> None:
    """
    Merge newly extracted fields back into the main table.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        # Get the schema of the main table
        cur.execute(f'PRAGMA table_info("{main_table}")')
        main_columns = [col[1] for col in cur.fetchall()]

        # Sanitize field names
        sanitized_new_field = sanitize_field_name(new_field)
        sanitized_parent = sanitize_field_name(parent_field) if parent_field else None

        # Add new field to main table if it doesn't exist
        if sanitized_new_field not in main_columns:
            cur.execute(f'ALTER TABLE "{main_table}" ADD COLUMN "{sanitized_new_field}" TEXT')
            print(f"Added new column '{sanitized_new_field}' to main table")

        # Add parent_field column if it doesn't exist
        if 'parent_field' not in main_columns:
            cur.execute(f'ALTER TABLE "{main_table}" ADD COLUMN "parent_field" TEXT')
            print("Added parent_field column to main table")

        # Update main table with new field values
        update_sql = f"""
        UPDATE "{main_table}"
        SET "{sanitized_new_field}" = (
            SELECT "{sanitized_new_field}"
            FROM "{new_table_name}"
            WHERE "{main_table}".clause = "{new_table_name}".clause
        ),
        parent_field = (
            SELECT parent_field
            FROM "{new_table_name}"
            WHERE "{main_table}".clause = "{new_table_name}".clause
        )
        WHERE EXISTS (
            SELECT 1
            FROM "{new_table_name}"
            WHERE "{main_table}".clause = "{new_table_name}".clause
        )
        """
        cur.execute(update_sql)
        conn.commit()
        print(f"Updated main table with values from {new_table_name}")

    except sqlite3.Error as e:
        print(f"Error merging fields: {e}")
        conn.rollback()
    finally:
        conn.close()

def handle_query(query: str, base_fields: List[str], schema: Dict[str, str]):
    """
    Main orchestrator for handling a user's query.
    This function coordinates all the agents to process the query.
    """
    print(f"\nHandling query: '{query}'")
    
    # Step 1: Decide query type
    print("\nStep 1: Deciding query type (hit or miss)...")
    classification = decide_query_type(query, base_fields)
    print(f"Query classified as: {classification.upper()}")
    
    if classification == "miss":
        # Step 2: Decide and extract new field
        print("\nStep 2: Deciding new field to extract...")
        new_field, parent_field = decide_new_field(query, base_fields)
        print(f"New field to extract: '{new_field}' (Parent: {parent_field})")
        
        # Load clauses to process
        clauses_to_process = load_records(SQL_DB_PATH, TABLE_NAME)
        if parent_field:
            # Optimize by filtering clauses that have the parent field
            clauses_to_process = [
                r for r in clauses_to_process if r.get(parent_field) is not None
            ]
            print(f"Optimized processing: {len(clauses_to_process)} clauses with parent field '{parent_field}'")

        # Step 3: Extract new field from clauses
        print(f"\nStep 3: Extracting '{new_field}' from {len(clauses_to_process)} clauses...")
        extracted_records = []
        for record in tqdm(clauses_to_process):
            extracted_data = extract_fields_from_clause(record["clause"], [new_field])
            # Ensure the extracted data is a dictionary
            if isinstance(extracted_data, dict):
                record.update(extracted_data)
            extracted_records.append(record)
        
        # Step 4: Merge new field into main table
        print(f"\nStep 4: Merging new field '{new_field}' into main table...")
        if extracted_records:
            # Create a temporary table with the new data
            temp_table_name = f"temp_{sanitize_field_name(new_field)}"
            store_records_sql(extracted_records, SQL_DB_PATH, temp_table_name)
            
            # Merge the temporary table into the main table
            merge_new_fields_to_main_table(
                temp_table_name, new_field, parent_field, SQL_DB_PATH, TABLE_NAME
            )
            
            # Update schema for SQL generation
            recs = load_records(SQL_DB_PATH, TABLE_NAME)
            schema = infer_schema_from_records(recs)
        
    # Step 5: Generate and execute SQL
    print("\nStep 5: Generating and executing SQL query…")
    where_clause = generate_filter_sql(query, schema, TABLE_NAME)
    
    # Construct the full query
    sql_query = f"SELECT * FROM {TABLE_NAME}"
    if where_clause and where_clause.strip() and where_clause != "1=0":
        sql_query += f" WHERE {where_clause}"
    
    print(f"\nExecuting SQL: {sql_query}")
    execute_generated_sql(sql_query, SQL_DB_PATH)

def run_tests():
    """
    Run a series of tests to verify the system's functionality.
    """
    print("\n=== Starting System Tests ===\n")
    
    # Test 1: Initialize database with test data
    print("Test 1: Initializing database with test data...")
    if os.path.exists(SQL_DB_PATH):
        os.remove(SQL_DB_PATH)
    
    # Add some test data to the clauses
    test_clauses = [
        "This is a test clause with company: Test Corp and effective date: 2024-01-01",
        "Another clause with company: ABC Inc and termination fee: 5000",
        "Third clause with company: XYZ Ltd and black company percentage: 0.75",
        "Fourth clause with company: DEF Corp and black company percentage: 0.25",
        "Fifth clause with company: GHI Inc and black company percentage: 0.90"
    ]
    
    # Store test clauses
    records = [extract_fields_from_clause(c, ['company']) for c in test_clauses]
    schema = store_records_sql(records, SQL_DB_PATH, TABLE_NAME)
    print("✓ Database initialized with test data\n")
    
    # Test 2: Test field extraction and hierarchy
    print("Test 2: Testing field extraction and hierarchy...")
    test_queries = [
        "What is the black company percentage?",
        "Show me clauses with termination fee",
        "Find clauses with effective date"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: {query}")
        handle_query(query, ['company'], schema)
    
    print("\n✓ Field extraction and hierarchy tests completed")
    
    # Test 3: Test querying capabilities
    print("\nTest 3: Testing query capabilities...")
    test_queries = [
        "Show me all clauses with black company percentage greater than 0.5",
        "Find clauses with company containing 'Corp'",
        "Show me clauses with black company percentage less than 0.3"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: {query}")
        handle_query(query, ['company', 'black_company_percentage'], schema)
    
    print("\n✓ Query capability tests completed")
    
    # Test 4: Test field persistence
    print("\nTest 4: Testing field persistence...")
    # Load the database again to verify persistence
    recs = load_records(SQL_DB_PATH, TABLE_NAME)
    schema = infer_schema_from_records(recs)
    base_fields = [col for col in schema if col != "clause"]
    
    print("\nPersisted fields in database:")
    for field in base_fields:
        print(f"- {field}")
    
    print("\n✓ Field persistence tests completed")
    
    print("\n=== All Tests Completed ===\n")

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    if not os.path.exists(SQL_DB_PATH):
        base_fields, schema = construct_db_from_ledgar()
    else:
        print("Database exists, loading schema & fields…")
        recs = load_records(SQL_DB_PATH, TABLE_NAME)
        schema = infer_schema_from_records(recs)
        base_fields = [col for col in schema if col != "clause"]

    print("\nAvailable fields in the database:")
    for field in base_fields:
        print(f"- {field}")

    # Run tests
    run_tests()

    # Example usage
    user_query = "Show me all clauses with black company percentage greater than 0.5"
    print("\nHandling query:", user_query)
    handle_query(user_query, base_fields, schema)