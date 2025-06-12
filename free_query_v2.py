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
oai_client = OpenAI(api_key="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")

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

# -------------------------
# SQL Storage (sqlite3 only)
# -------------------------
def store_records_sql(
    records: List[Dict[str, Any]],
    db_path: str,
    table_name: str
) -> Dict[str, str]:
    """
    Given a list of dict-records, infer each column's SQL type,
    CREATE TABLE (dropping existing), and BULK INSERT.
    Returns the inferred schema mapping col → ("REAL"|"DATE"|"TEXT").
    """
    # Infer schema
    schema: Dict[str, str] = {}
    sample = records[0]
    for col in sample.keys():
        vals = [r[col] for r in records if r.get(col) is not None]
        schema[col] = infer_sql_column_type_rule_list(vals, col)

    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    # Re-create table
    cols_ddl = []
    for col, dtype in schema.items():
        sql_type = "REAL" if dtype == "REAL" else "TEXT"
        cols_ddl.append(f"{col} {sql_type}")
    ddl = f"DROP TABLE IF EXISTS {table_name}; CREATE TABLE {table_name} ({', '.join(cols_ddl)});"
    cur.executescript(ddl)

    # Bulk insert
    cols_list    = list(sample.keys())
    placeholders = ", ".join("?" for _ in cols_list)
    insert_sql   = f"INSERT INTO {table_name} ({', '.join(cols_list)}) VALUES ({placeholders})"
    rows         = [[r.get(col) for col in cols_list] for r in records]
    cur.executemany(insert_sql, rows)

    conn.commit()
    conn.close()

    print(f"Stored {len(rows)} rows into '{table_name}' with schema: {schema}")
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
        "Ensure output formats: REAL→number, DATE→'YYYY-MM-DD', TEXT→string. "
        "Return only the SQL query in a triple-quoted string."
    )
    try:
        resp = oai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a SQL query generation agent."},
                {"role": "user",   "content": prompt}
            ]
        )
        return resp.choices[0].message.content.strip()
    except:
        return f'''SELECT * FROM {table_name} LIMIT 10;'''

def execute_generated_sql(sql_code: str, db_path: str):
    sql = sql_code.replace("```sql", "").replace("```", "").strip().strip('"""')
    print(f"Executing SQL:\n{sql}\n")
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    conn.close()
    for row in rows:
        print(dict(zip(cols, row)))

def decide_new_field(query: str) -> str:
    prompt = (
        f"Given the query: '{query}', determine what new field should be extracted "
        "from clauses to answer it. Return only the field name."
    )
    try:
        resp = oai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a field decision agent."},
                {"role": "user",   "content": prompt}
            ]
        )
        return resp.choices[0].message.content.strip()
    except:
        return "new_field"

def handle_query(query: str, base_fields: List[str], schema: Dict[str, str]):
    decision = decide_query_type(query, base_fields)
    if decision == "hit":
        sql = generate_filter_sql(query, schema, TABLE_NAME)
        execute_generated_sql(sql, SQL_DB_PATH)
    else:
        new_field = decide_new_field(query)
        print(f"[Miss] extracting new field: {new_field}")

        with open(LEDGAR_PATH, "r") as f:
            raw = [json.loads(line)["provision"] for line in f][:CLAUSE_LIMIT]
        clauses = [
            c + (f" effective date: {random_date()}" if random.random() < 0.5 else "")
            for c in raw
        ]

        records   = [extract_fields_from_clause(c, [new_field]) for c in tqdm(clauses)]
        new_table = f"extracted_{new_field}"
        new_schema = store_records_sql(records, SQL_DB_PATH, new_table)

        sql = generate_filter_sql(query, new_schema, new_table)
        execute_generated_sql(sql, SQL_DB_PATH)

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

    # Example usage
    user_query = "I want all the clauses that has zebra percentage greater than 0.5"
    print("\nHandling query:", user_query)
    handle_query(user_query, base_fields, schema)