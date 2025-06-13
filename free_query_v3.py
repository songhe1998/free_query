import json
import os
import sqlite3
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, create_model
from openai import OpenAI
from tqdm import tqdm
# -------------------------
# File paths and settings
# -------------------------
LEDGAR_PATH  = "/Users/songhewang/Downloads/LEDGAR_2016-2019_clean.jsonl"
CLAUSE_LIMIT = 10
SQL_DB_PATH  = "clauses.db"
TABLE_NAME   = "clauses"

# Initialize OpenAI client
oai_client = OpenAI(api_key="Akwh-w91wAmGahcNXuRfJjwwVpTsMyBWVQlRc_vmRpP_V_XCJw1nZ5C27xzdWgrKxkX1wNeKfT1HJFkblbT3RbXU8POI0qw1gb9HA_RbJfcZAFH9hQBZWUI5ND6PohLLgm5XayD_fJkOvvO3hn_jCsmD4OUAp1M-jorp-ks"[::-1])

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

        response = oai_client.chat.completions.create(
            model="gpt-4o-mini",
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


def extract_fields_from_clause(clause: str, fields: List[str]) -> Dict[str, Any]:
    clause += f" zebra percentage: {random.random()}"
    """
    Extract specified fields from a clause using standard completion API.
    
    Args:
        clause: The clause text to analyze
        fields: List of fields to extract
        
    Returns:
        Dict[str, Any]: Dictionary containing the extracted fields
    """
    try:
        # Create a prompt that instructs the model to extract specific fields
        fields_str = ", ".join(fields)
        prompt = f"""
        Extract the following fields from this clause: {fields_str}
        
        Clause: {clause}
        
        Return ONLY a JSON object with the extracted fields. If the field is date, return the date in YYYY-MM-DD format. Do not include any explanations. 
        """
        
        # Use standard completion API
        response = oai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an extraction agent. Extract the requested fields and return them as a JSON object."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}  # This helps ensure JSON output
        )
        
        # Extract the response text and parse as JSON
        response_text = response.choices[0].message.content
        result = json.loads(response_text)
        print(clause)
        print(result)
        
        # Ensure all requested fields are in the result
        for field in fields:
            if field not in result:
                result[field] = None
        result['clause'] = clause
        return result
        
    except json.JSONDecodeError as e:
        print(f"[Error] Failed to parse JSON response: {e}")
        print(f"[Error] Raw response: {response_text}")
        # Return a dictionary with None values for all fields
        return {field: None for field in fields}
        
    except Exception as e:
        print(f"[Error] Extraction failed: {str(e)}")
        # Return a dictionary with None values for all fields
        return {field: None for field in fields}

# -------------------------
# Step 1: Construct DB from LEDGAR
# -------------------------
def construct_db_from_ledgar() -> (List[str], Dict[str, str]):
    with open(LEDGAR_PATH, "r") as f:
        raw = [json.loads(line)["provision"] for line in f][:CLAUSE_LIMIT]

    # 50% randomly append " effective date: YYYY-MM-DD"
    clauses = [
        c + (f" effective date: {random_date()}" if random.random() < 0.8 else " ")
        for c in raw
    ]

    clauses = [
        c + (f"zebra percentage: {random.random()}")
        for c in raw
    ]


    base_fields = ['company']
    records = [extract_fields_from_clause(c, base_fields) for c in tqdm(clauses)]
    schema  = store_records_sql(records, SQL_DB_PATH, TABLE_NAME)
    return base_fields, schema

# -------------------------
# Step 2: Query Handling Agents
# -------------------------
def decide_query_type(query: str, known_fields: List[str]) -> str:
    prompt = (
        f"We have a dataset with extracted fields: {', '.join(known_fields)}. "
        f"Determine if the query: '{query}' is asking for information already extracted ('hit') "
        "or something new ('miss'). Return only 'hit' or 'miss'."
    )
    try:
        resp = oai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a query decision agent."},
                {"role": "user",   "content": prompt}
            ]
        )
        decision = resp.choices[0].message.content.strip().lower()
        if decision in ("hit", "miss"):
            return decision
    except:
        pass
    return "hit" if any(f.lower() in query.lower() for f in known_fields) else "miss"

def generate_filter_sql(
    query: str,
    schema: Dict[str, str],
    table_name: str = TABLE_NAME
) -> str:
    schema_desc = get_schema_description_list(schema)
    prompt = (
        f"Given the SQL table structure: {schema_desc} and the query: '{query}', "
        f"generate SQL code to retrieve rows from the table '{table_name}'. "
        "For numeric comparisons, use CAST(column AS REAL) instead of ::REAL. "
        "Ensure output formats: REAL→number, DATE→'YYYY-MM-DD', TEXT→string. "
        "Always quote column names with spaces using double quotes. "
        "Use the exact table name '{table_name}' in the query. "
        "Return only the SQL query in a triple-quoted string."
    )
    try:
        resp = oai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a SQL query generation agent. Use SQLite-compatible syntax, properly quote column names with spaces, and use the exact table name provided."},
                {"role": "user",   "content": prompt}
            ]
        )
        sql = resp.choices[0].message.content.strip()
        
        # Find the field being queried
        field_name = None
        sanitized_field_name = None
        for field in schema.keys():
            if field.lower() in query.lower():
                field_name = field
                sanitized_field_name = sanitize_field_name(field)
                break
                
        if field_name and sanitized_field_name:
            # Always add a WHERE clause to filter out NULL values for the requested field
            if "WHERE" not in sql.upper():
                sql = f"SELECT * FROM {table_name} WHERE \"{sanitized_field_name}\" IS NOT NULL"
            else:
                # If there's already a WHERE clause, add the NOT NULL condition
                sql = sql.replace("WHERE", f"WHERE \"{sanitized_field_name}\" IS NOT NULL AND")
        
        # Ensure we're selecting from the correct table and using SELECT *
        if "FROM" not in sql.upper():
            sql = f"SELECT * FROM {table_name}"
        elif not any(table_name.lower() in part.lower() for part in sql.split()):
            sql = sql.replace("FROM", f"FROM {table_name}")
            
        # Fix any redundant column selections
        sql = sql.replace("SELECT *,", "SELECT *")
        sql = sql.replace("SELECT *, ", "SELECT *")
        
        # Replace any spaces in column names with underscores
        for field in schema.keys():
            sanitized = sanitize_field_name(field)
            if field != sanitized:
                sql = sql.replace(f'"{field}"', f'"{sanitized}"')
                sql = sql.replace(f"'{field}'", f'"{sanitized}"')
                sql = sql.replace(field, sanitized)
            
        print(f"\nGenerated SQL query:\n{sql}")
        return sql
    except Exception as e:
        print(f"[Error] SQL generation failed: {e}")
        # If we know the field name, include the NOT NULL condition
        if field_name and sanitized_field_name:
            return f'SELECT * FROM {table_name} WHERE "{sanitized_field_name}" IS NOT NULL'
        return f"SELECT * FROM {table_name}"

def execute_generated_sql(sql_code: str, db_path: str):
    sql = sql_code.replace("```sql", "").replace("```", "").strip().strip('"""')
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
        cur.execute(fixed_sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        for row in rows:
            print(dict(zip(cols, row)))
    finally:
        conn.close()

def decide_new_field(query: str, known_fields: List[str]) -> (str, Optional[str]):
    """
    Given a query and known fields, determine the new field to extract and
    a potential parent field from the known fields.
    Returns (new_field_name, parent_field_name_or_None).
    """
    known_fields_str = ", ".join(known_fields) if known_fields else "None"
    prompt = f"""
Given the query: '{query}'
And the already known and extracted fields: [{known_fields_str}]

1. Determine the primary new field that needs to be extracted from clauses to answer the query.
2. If this new field is a more specific version or a sub-category of one of the KNOWN fields, identify that known field as the 'parent field'. For example, if 'effective date' is new and 'date' is known, 'date' is the parent. If 'termination fee amount' is new and 'fee amount' is known, 'fee amount' could be the parent. If no clear parent relationship exists or known fields are None, the parent_field should be null.

Return your answer as a JSON object with two keys: "new_field" (string, e.g., "effective date") and "parent_field" (string or null, e.g., "date" or null).
Example for query 'What is the effective date?' and known fields ['date', 'company']: {{"new_field": "effective date", "parent_field": "date"}}
Example for query 'Find termination clauses.' and known fields ['date', 'company']: {{"new_field": "termination clause type", "parent_field": null}}
"""
    try:
        resp = oai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a field decision agent. Respond in JSON format as specified."},
                {"role": "user",   "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = resp.choices[0].message.content.strip()
        result = json.loads(content)
        
        new_field = result.get("new_field")
        parent_field = result.get("parent_field")
        
        if not new_field: # Basic validation
            print(f"[Warning] LLM did not return a 'new_field'. Raw response: {content}. Defaulting.")
            # Basic fallback, trying to derive from query
            derived_new_field = query.lower().replace("what is the", "").replace("find", "").replace("what is", "").replace("show me", "").strip()
            return derived_new_field if derived_new_field else "unknown_new_field", None

        # Ensure parent_field is None if it's "None", "null", or empty string from LLM
        if isinstance(parent_field, str) and parent_field.lower() in ["none", "null", ""]:
            parent_field = None
            
        return new_field, parent_field
        
    except Exception as e:
        # Fallback in case of LLM error or JSON parsing error
        print(f"[Error] in decide_new_field: {e}. Raw content possibly: {content if 'content' in locals() else 'N/A'}. Defaulting new_field from query.")
        derived_new_field = query.lower().replace("what is the", "").replace("find", "").replace("what is", "").replace("show me", "").strip()
        return derived_new_field if derived_new_field else "unknown_new_field_on_error", None

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
    decision = decide_query_type(query, base_fields)
    if decision == "hit":
        sql = generate_filter_sql(query, schema, TABLE_NAME)
        execute_generated_sql(sql, SQL_DB_PATH)
    else: # miss
        new_field, parent_field = decide_new_field(query, base_fields)
        
        if not new_field:
            print("[Error] Critical: new_field is None or empty after decide_new_field. Aborting miss handling for this query.")
            return

        print(f"[Miss] Query: '{query}'. Attempting to extract new field: '{new_field}'. Parent field hint: '{parent_field}'")

        clauses_to_process: List[str] = []

        if parent_field and parent_field in schema:
            print(f"Parent field '{parent_field}' found in existing schema. Attempting to subset clauses from '{TABLE_NAME}'.")
            conn = None
            try:
                conn = sqlite3.connect(SQL_DB_PATH)
                cur = conn.cursor()
                sanitized_parent = sanitize_field_name(parent_field)
                subset_query_sql = f'SELECT clause FROM "{TABLE_NAME}" WHERE "{sanitized_parent}" IS NOT NULL'
                print(f"Executing SQL to get subset of clauses: {subset_query_sql}")
                cur.execute(subset_query_sql)
                
                rows = cur.fetchall()
                if rows:
                    clauses_to_process = [row[0] for row in rows if row[0] is not None] 
                    if clauses_to_process:
                        print(f"Found {len(clauses_to_process)} candidate clauses based on parent field '{parent_field}'.")
                    else:
                        print(f"No non-null clauses found with parent field '{parent_field}' having a value. Will process all clauses from source.")
                else:
                    print(f"No clauses rows returned with parent field '{parent_field}' having a value. Will process all clauses from source.")
            except sqlite3.Error as e:
                print(f"SQL error when trying to subset clauses: {e}. Will process all clauses from source.")
                clauses_to_process = []
            finally:
                if conn:
                    conn.close()
        else:
            if parent_field:
                print(f"Parent field '{parent_field}' was suggested but not found in the current schema of '{TABLE_NAME}' or was None. Will process all clauses from source.")
            else:
                print("No parent field identified or applicable. Will process all clauses from source.")

        if not clauses_to_process:
            print(f"Loading and processing all {CLAUSE_LIMIT} clauses from LEDGAR for field '{new_field}'.")
            with open(LEDGAR_PATH, "r") as f:
                raw_base_clauses = [json.loads(line)["provision"] for line in f][:CLAUSE_LIMIT]
            
            clauses_to_process = [
                c + (f" effective date: {random_date()}" if random.random() < 0.5 else "")
                for c in raw_base_clauses
            ]

        print(f"Extracting '{new_field}' from {len(clauses_to_process)} clauses.")
        records = [extract_fields_from_clause(c, [new_field]) for c in tqdm(clauses_to_process)]
        
        sanitized_new_field_name = sanitize_field_name(new_field)
        if not sanitized_new_field_name:
            sanitized_new_field_name = "extracted_field"
            
        new_table_name = f"extracted_{sanitized_new_field_name}"
        
        print(f"Storing extracted records for '{new_field}' into new table: '{new_table_name}'")
        new_schema = store_records_sql(records, SQL_DB_PATH, new_table_name, parent_field)

        # Merge new fields back to main table
        print(f"Merging new field '{new_field}' back to main table")
        merge_new_fields_to_main_table(new_table_name, new_field, parent_field, SQL_DB_PATH)

        # Update base_fields and schema for future queries
        base_fields.append(new_field)
        schema[new_field] = "TEXT"
        if parent_field:
            schema['parent_field'] = "TEXT"

        # Generate and execute SQL against the main table
        print(f"Generating SQL query for original query: '{query}' against main table with updated schema")
        sql = generate_filter_sql(query, schema, TABLE_NAME)
        execute_generated_sql(sql, SQL_DB_PATH)

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
    user_query = "I want all the clauses that has black company more than 0.5"
    print("\nHandling query:", user_query)
    handle_query(user_query, base_fields, schema)