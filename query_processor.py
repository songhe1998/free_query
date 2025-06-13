import json
import os
import sqlite3
import random
from datetime import datetime
from typing import Optional, List, Dict, Any

from openai import OpenAI

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
def sanitize_field_name(field_name: str) -> str:
    """Sanitize field name for SQLite by replacing spaces with underscores."""
    sanitized = ''.join(c if c.isalnum() else '_' for c in field_name.strip().lower())
    if not sanitized[0].isalpha() and sanitized[0] != '_':
        sanitized = '_' + sanitized
    return sanitized

def infer_sql_column_type(values: List[Any], column_name: str) -> str:
    """Infer SQL column type based on column name and sample values."""
    try:
        # First try to detect numeric values
        numeric_count = 0
        for val in values:
            if val is None:
                continue
            # Try to convert to float, handling percentage strings
            try:
                if isinstance(val, str) and '%' in val:
                    # Handle percentage values
                    numeric_count += 1
                else:
                    float(str(val).replace('$', '').replace(',', ''))
                    numeric_count += 1
            except ValueError:
                pass

        # If more than 50% of non-null values are numeric, it's a REAL
        if numeric_count > len([v for v in values if v is not None]) * 0.5:
            return "REAL"

        # For date detection
        date_count = 0
        for val in values:
            if val is None:
                continue
            try:
                # Try to parse as date in various formats
                if isinstance(val, str):
                    # Common date formats
                    formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']
                    for fmt in formats:
                        try:
                            datetime.strptime(val, fmt)
                            date_count += 1
                            break
                        except ValueError:
                            continue
            except:
                pass

        # If more than 50% of non-null values are dates, it's a DATE
        if date_count > len([v for v in values if v is not None]) * 0.5:
            return "DATE"

        # If column name suggests numeric type
        numeric_indicators = ['amount', 'price', 'cost', 'fee', 'percentage', 'rate', 'number', 'count', 'quantity']
        if any(indicator in column_name.lower() for indicator in numeric_indicators):
            return "REAL"

        # If column name suggests date type
        date_indicators = ['date', 'time', 'deadline', 'expiry', 'expiration', 'start', 'end']
        if any(indicator in column_name.lower() for indicator in date_indicators):
            return "DATE"

        # Default to TEXT
        return "TEXT"

    except Exception as e:
        print(f"[Error] Type inference failed: {str(e)}, defaulting to TEXT")
        return "TEXT"

def extract_fields_from_clause(clause: str, fields: List[str]) -> Dict[str, Any]:
    """Extract specified fields from a clause using LLM."""
    try:
        fields_str = ", ".join(fields)
        prompt = f"""
        Extract the following fields from this clause: {fields_str}
        
        Clause: {clause}
        
        For numeric fields (like amounts, percentages, etc.):
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
                {"role": "system", "content": "You are an extraction agent. Extract the requested fields and return them as a JSON object. For numeric fields, return the actual number without formatting."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        print(f"\nExtracted fields from clause:")
        print(json.dumps(result, indent=2))
        
        # Process the extracted values
        for field in fields:
            if field not in result:
                result[field] = None
            else:
                value = result[field]
                if value is not None:
                    # Try to convert to appropriate type
                    try:
                        if isinstance(value, str):
                            # Handle percentage values
                            if '%' in value:
                                result[field] = float(value.strip('%')) / 100
                            # Handle currency values
                            elif '$' in value or ',' in value:
                                result[field] = float(value.replace('$', '').replace(',', ''))
                            # Try to convert to float if it looks numeric
                            elif any(c.isdigit() for c in value):
                                try:
                                    result[field] = float(value)
                                except ValueError:
                                    pass
                    except (ValueError, TypeError):
                        # If conversion fails, keep the original value
                        pass
        
        result['clause'] = clause
        return result
        
    except Exception as e:
        print(f"[Error] Extraction failed: {str(e)}")
        return {field: None for field in fields}

def store_records_sql(records: List[Dict[str, Any]], db_path: str, table_name: str, parent_field: Optional[str] = None) -> Dict[str, str]:
    """Store records in SQLite database with inferred schema."""
    schema: Dict[str, str] = {}
    sample = records[0]
    
    # Create field mapping and infer schema
    field_mapping = {}
    for col in sample.keys():
        sanitized_col = sanitize_field_name(col)
        field_mapping[col] = sanitized_col
        vals = [r[col] for r in records if r.get(col) is not None]
        schema[sanitized_col] = infer_sql_column_type(vals, col)
        
        # Convert values to appropriate type before storage
        if schema[sanitized_col] == "REAL":
            for record in records:
                if record.get(col) is not None:
                    try:
                        if isinstance(record[col], str):
                            # Handle percentage values
                            if '%' in record[col]:
                                record[col] = float(record[col].strip('%')) / 100
                            else:
                                record[col] = float(str(record[col]).replace('$', '').replace(',', ''))
                    except (ValueError, TypeError):
                        record[col] = None
        elif schema[sanitized_col] == "DATE":
            for record in records:
                if record.get(col) is not None:
                    try:
                        if isinstance(record[col], str):
                            # Try common date formats
                            formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']
                            for fmt in formats:
                                try:
                                    record[col] = datetime.strptime(record[col], fmt).strftime('%Y-%m-%d')
                                    break
                                except ValueError:
                                    continue
                    except (ValueError, TypeError):
                        record[col] = None

    # Add parent_field if provided
    if parent_field:
        schema['parent_field'] = "TEXT"
        field_mapping['parent_field'] = 'parent_field'
        for record in records:
            record['parent_field'] = parent_field

    # Ensure clause column exists
    if 'clause' not in schema:
        schema['clause'] = "TEXT"
        field_mapping['clause'] = 'clause'

    # Create table
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cols_ddl = []
    for col, dtype in schema.items():
        sql_type = "REAL" if dtype == "REAL" else "TEXT"
        cols_ddl.append(f'"{col}" {sql_type}')
    
    ddl = f'DROP TABLE IF EXISTS "{table_name}"; CREATE TABLE "{table_name}" ({", ".join(cols_ddl)});'
    cur.executescript(ddl)

    # Insert records
    cols_list = [field_mapping[col] for col in sample.keys()]
    if parent_field:
        cols_list.append('parent_field')
    if 'clause' not in cols_list:
        cols_list.append('clause')
    
    placeholders = ", ".join("?" for _ in cols_list)
    quoted_cols = ", ".join(f'"{col}"' for col in cols_list)
    insert_sql = f'INSERT INTO "{table_name}" ({quoted_cols}) VALUES ({placeholders})'
    
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

    print(f"\nStored {len(transformed_rows)} rows with schema:")
    print(json.dumps(schema, indent=2))
    return schema

def decide_query_type(query: str, known_fields: List[str]) -> str:
    """Determine if query is asking for known or new fields."""
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
                {"role": "user", "content": prompt}
            ]
        )
        decision = resp.choices[0].message.content.strip().lower()
        return decision if decision in ("hit", "miss") else "hit"
    except:
        return "hit" if any(f.lower() in query.lower() for f in known_fields) else "miss"

def decide_new_field(query: str, known_fields: List[str]) -> (str, Optional[str]):
    """Determine new field to extract and potential parent field."""
    known_fields_str = ", ".join(known_fields) if known_fields else "None"
    prompt = f"""
Given the query: '{query}'
And the already known and extracted fields: [{known_fields_str}]

1. Determine the primary new field that needs to be extracted from clauses to answer the query.
2. If this new field is a more specific version or a sub-category of one of the KNOWN fields, identify that known field as the 'parent field'.

Return your answer as a JSON object with two keys: "new_field" (string) and "parent_field" (string or null).
"""
    try:
        resp = oai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a field decision agent. Respond in JSON format as specified."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        result = json.loads(resp.choices[0].message.content)
        
        new_field = result.get("new_field")
        parent_field = result.get("parent_field")
        
        if not new_field:
            derived_new_field = query.lower().replace("what is the", "").replace("find", "").replace("what is", "").replace("show me", "").strip()
            return derived_new_field if derived_new_field else "unknown_new_field", None

        if isinstance(parent_field, str) and parent_field.lower() in ["none", "null", ""]:
            parent_field = None
            
        return new_field, parent_field
        
    except Exception as e:
        print(f"[Error] in decide_new_field: {e}")
        derived_new_field = query.lower().replace("what is the", "").replace("find", "").replace("what is", "").replace("show me", "").strip()
        return derived_new_field if derived_new_field else "unknown_new_field_on_error", None

def generate_filter_sql(query: str, schema: Dict[str, str], table_name: str = TABLE_NAME) -> str:
    """Generate SQL query based on natural language query and schema."""
    schema_desc = ", ".join(f"{col} ({dtype})" for col, dtype in schema.items())
    prompt = f"""
    Given the SQL table structure: {schema_desc} and the query: '{query}'
    Generate a SQL query to retrieve rows from the table '{table_name}'.
    
    Rules:
    1. For numeric fields (REAL type):
       - Use CAST(column AS REAL) for comparisons
       - Handle percentages as decimals (e.g., 0.1 for 10%)
       - Use >, <, >=, <=, = for numeric comparisons
       - Always exclude NULL values unless specifically requested
    2. For text fields:
       - Use = for exact matches
       - Use LIKE with % for partial matches
       - Always exclude NULL values unless specifically requested
    3. For date fields:
       - Use date format 'YYYY-MM-DD'
       - Use date comparison operators
       - Always exclude NULL values unless specifically requested
    4. Always quote column names with spaces using double quotes
    5. Use the exact table name '{table_name}'
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
                sql = f"SELECT * FROM {table_name} WHERE \"{field_name}\" IS NOT NULL"
            else:
                # If there's already a WHERE clause, add the NOT NULL condition
                sql = sql.replace("WHERE", f"WHERE \"{field_name}\" IS NOT NULL AND")
        
        # Ensure we're selecting from the correct table
        if "FROM" not in sql.upper():
            sql = f"SELECT * FROM {table_name}"
        elif not any(table_name.lower() in part.lower() for part in sql.split()):
            sql = sql.replace("FROM", f"FROM {table_name}")
            
        print(f"\nGenerated SQL query:\n{sql}")
        return sql
        
    except Exception as e:
        print(f"[Error] SQL generation failed: {e}")
        if field_name:
            return f'SELECT * FROM {table_name} WHERE "{field_name}" IS NOT NULL'
        return f"SELECT * FROM {table_name}"

def execute_generated_sql(sql_code: str, db_path: str):
    """Execute generated SQL query and return results."""
    sql = sql_code.replace("```sql", "").replace("```", "").strip().strip('"""')
    print(f"\nExecuting SQL:\n{sql}\n")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    results = []
    
    try:
        # First, let's check if the table has any data
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        count = cur.fetchone()[0]
        print(f"Total rows in table: {count}")
        
        # Execute the main query
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        
        if not rows:
            print("\nNo results found. Checking table contents...")
            # Show a sample of the table contents to help debug
            cur.execute(f"SELECT * FROM {TABLE_NAME} LIMIT 5")
            sample_rows = cur.fetchall()
            if sample_rows:
                print("\nSample table contents:")
                for row in sample_rows:
                    print(json.dumps(dict(zip(cols, row)), indent=2))
        else:
            print(f"\nFound {len(rows)} results:")
            for row in rows:
                result_dict = dict(zip(cols, row))
                results.append(result_dict)
                print(json.dumps(result_dict, indent=2))
                
    except sqlite3.Error as e:
        print(f"SQL Error: {e}")
        print("Attempting to fix and retry...")
        # Try to fix common issues
        fixed_sql = sql.replace("clause", TABLE_NAME)
        fixed_sql = fixed_sql.replace("black company percentage", '"black_company_percentage"')
        print(f"Retrying with fixed SQL:\n{fixed_sql}\n")
        try:
            cur.execute(fixed_sql)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []
            if rows:
                print(f"\nFound {len(rows)} results after fix:")
                for row in rows:
                    result_dict = dict(zip(cols, row))
                    results.append(result_dict)
                    print(json.dumps(result_dict, indent=2))
            else:
                print("\nNo results found after fix. Checking table contents...")
                cur.execute(f"SELECT * FROM {TABLE_NAME} LIMIT 5")
                sample_rows = cur.fetchall()
                if sample_rows:
                    print("\nSample table contents:")
                    for row in sample_rows:
                        print(json.dumps(dict(zip(cols, row)), indent=2))
        except sqlite3.Error as e2:
            print(f"Second attempt failed: {e2}")
    finally:
        conn.close()
    
    return results

def generate_synthetic_clauses(field: str, num_clauses: int = 10) -> List[str]:
    """Generate synthetic clauses using ChatGPT, with about 50% containing the specified field."""
    try:
        prompt = f"""
        Generate {num_clauses} different legal contract clauses. For about 50% of them, include information about '{field}'.
        Make the clauses diverse and realistic. Each clause should be a complete sentence or paragraph.
        
        For numeric fields (like amounts, percentages):
        - Include actual numbers (e.g., "1000", "$5,000", "10%")
        - Make the numbers realistic for the context
        
        For date fields:
        - Include dates in various formats (e.g., "2024-01-01", "01/01/2024")
        
        For text fields:
        - Include clear, specific text values
        
        Return the clauses as a JSON array of strings.
        """
        
        response = oai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a legal contract clause generation agent. Generate realistic and diverse clauses with specific values."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        clauses = json.loads(response.choices[0].message.content)
        if isinstance(clauses, dict) and "clauses" in clauses:
            clauses = clauses["clauses"]
        elif not isinstance(clauses, list):
            clauses = [str(clauses)]
            
        print(f"\nGenerated {len(clauses)} synthetic clauses")
        return clauses
        
    except Exception as e:
        print(f"[Error] Failed to generate synthetic clauses: {e}")
        # Fallback to simple template-based generation with numeric values
        base_clauses = [
            f"The {field} shall be $1,000 per month.",
            f"Any changes to the {field} require written notice.",
            f"The parties agree to maintain confidentiality.",
            f"All disputes shall be resolved through arbitration.",
            f"The {field} may be adjusted annually, starting at 10%.",
            f"Payment terms are net 30 days.",
            f"The {field} is subject to market conditions, currently set at $5,000.",
            f"Termination requires 30 days notice.",
            f"Intellectual property rights are retained.",
            f"The {field} shall be reviewed quarterly, with a minimum of $2,500."
        ]
        return base_clauses

def process_query(query: str):
    """Process a natural language query and return results."""
    print(f"\nProcessing query: {query}")
    
    try:
        # Check if database exists
        if not os.path.exists(SQL_DB_PATH):
            print("Database does not exist. Please run synthesize_db.py first.")
            return []
            
        # Get current schema
        conn = sqlite3.connect(SQL_DB_PATH)
        cur = conn.cursor()
        cur.execute(f'PRAGMA table_info("{TABLE_NAME}")')
        schema = {col[1]: col[2] for col in cur.fetchall()}
        conn.close()
        
        if not schema:
            print("No schema found in database. Please run synthesize_db.py first.")
            return []
            
        print("\nKnown fields:", ", ".join(schema.keys()))
        
        # Generate and execute SQL
        sql = generate_filter_sql(query, schema)
        results = execute_generated_sql(sql, SQL_DB_PATH)
        
        return results if results is not None else []
        
    except Exception as e:
        print(f"Error processing query: {e}")
        return []

def merge_new_fields_to_main_table(
    new_table_name: str,
    new_field: str,
    parent_field: Optional[str],
    db_path: str,
    main_table: str = TABLE_NAME
) -> None:
    """Merge newly extracted fields back into the main table."""
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

        # First, get all the new values
        cur.execute(f'SELECT clause, "{sanitized_new_field}", parent_field FROM "{new_table_name}"')
        new_values = cur.fetchall()
        
        # For each new value, either update existing row or insert new row
        for clause, value, parent in new_values:
            if value is not None:  # Only process non-null values
                # Check if the clause exists in the main table
                cur.execute(f'SELECT 1 FROM "{main_table}" WHERE clause = ?', (clause,))
                exists = cur.fetchone() is not None
                
                if exists:
                    # Update existing row
                    update_sql = f"""
                    UPDATE "{main_table}"
                    SET "{sanitized_new_field}" = ?,
                        parent_field = ?
                    WHERE clause = ?
                    """
                    cur.execute(update_sql, (value, parent, clause))
                else:
                    # Insert new row
                    insert_sql = f"""
                    INSERT INTO "{main_table}" (clause, "{sanitized_new_field}", parent_field)
                    VALUES (?, ?, ?)
                    """
                    cur.execute(insert_sql, (clause, value, parent))
        
        conn.commit()
        print(f"Updated main table with values from {new_table_name}")

    except sqlite3.Error as e:
        print(f"Error merging fields: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    # Example usage
    query = input("Enter your query: ")
    process_query(query) 