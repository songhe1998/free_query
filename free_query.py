import json
import os
import sqlite3
import pandas as pd
from openai import OpenAI

# Initialize ChatGPT API client
oai_client = OpenAI(api_key='Akwh-w91wAmGahcNXuRfJjwwVpTsMyBWVQlRc_vmRpP_V_XCJw1nZ5C27xzdWgrKxkX1wNeKfT1HJFkblbT3RbXU8POI0qw1gb9HA_RbJfcZAFH9hQBZWUI5ND6PohLLgm5XayD_fJkOvvO3hn_jCsmD4OUAp1M-jorp-ks'[::-1])

# -------------------------
# File paths and settings
# -------------------------
BASE_INFO_PATH = "extracted_clauses.csv"
LEDGAR_PATH = "/Users/songhewang/Downloads/LEDGAR_2016-2019_clean.jsonl"
CLAUSE_LIMIT = 100  # for testing; remove or adjust as needed
SQL_DB_PATH = "clauses.db"
TABLE_NAME = "clauses"

# -------------------------
# Step 1: Load or Extract LEDGAR clauses
# -------------------------
if not os.path.exists(BASE_INFO_PATH):
    print("Extracting base information from LEDGAR data...")
    with open(LEDGAR_PATH, "r") as f:
        # Limit to CLAUSE_LIMIT clauses for this example
        clauses = [json.loads(line)['provision'] for line in f.readlines()][:CLAUSE_LIMIT]

    # -------------------------
    # Extraction Agent (Structured)
    # -------------------------
    def extract_clause_info_structured(clause, fields):
        # Build a JSON schema from the given fields (ensuring keys use underscore)
        properties = {}
        for field in fields:
            field_key = field.replace(" ", "_")
            properties[field_key] = {"type": "string"}
        schema = {
            "type": "object",
            "properties": properties,
            "required": list(properties.keys()),
            "additionalProperties": False
        }
        
        response = oai_client.responses.create(
            model="gpt-4o-mini",
            input=[
                {"role": "system", "content": "Extract clause information using a JSON schema."},
                {"role": "user", "content": (
                    f"Extract the following fields from the clause if they exist: {', '.join(fields)}. "
                    f"If any field is not present, return null. Clause: '''{clause}'''"
                )}
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "clause_info",
                    "schema": schema,
                    "strict": True
                }
            }
        )
        try:
            result = json.loads(response.output_text)
        except Exception as e:
            print("Error parsing structured output:", e)
            result = {field.replace(" ", "_"): None for field in fields}
        # Include the original clause for context
        result["clause"] = clause
        return result

    # Set base extraction fields (use underscore style keys)
    base_fields = ["date", "money", "company_name"]
    extracted = [extract_clause_info_structured(clause, base_fields) for clause in clauses]
    df_base = pd.DataFrame(extracted)
    df_base.to_csv(BASE_INFO_PATH, index=False)
else:
    print("Loading extracted base information from CSV...")
    df_base = pd.read_csv(BASE_INFO_PATH)
    base_fields = [col for col in df_base.columns if col != "clause"]

print("Currently extracted fields:", base_fields)

# -------------------------
# Step 2: Store Data into SQL
# -------------------------
def store_data_in_sql(df, db_path, table_name):
    conn = sqlite3.connect(db_path)
    # Replace the table if it already exists
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()
    print(f"Data stored into SQL table '{table_name}' in database {db_path}.")

store_data_in_sql(df_base, SQL_DB_PATH, TABLE_NAME)

# -------------------------
# Agent 1: Query Decision Agent
# -------------------------
def decide_query_type(query, known_fields):
    print("Known fields:", known_fields)
    prompt = (f'''We have a dataset of legal documents with the extracted fields: {', '.join(known_fields)}. 
Determine if the query: '{query}' is asking for information that is already extracted (a "hit") or is asking for a field that is not yet extracted (a "miss"). 
Return only the word "hit" or "miss".''')
    try:
        response = oai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a query decision agent."},
                {"role": "user", "content": prompt}
            ]
        )
        decision = response.choices[0].message.content.strip().lower()
        if decision not in ["hit", "miss"]:
            raise ValueError("Invalid decision response")
    except Exception as e:
        print("Decision agent error:", e)
        decision = "hit" if any(field.lower() in query.lower() for field in known_fields) else "miss"
    print(f"[Query Decision Agent] Query decision: {decision}")
    return decision

# -------------------------
# Agent 2: SQL Query Generation Agent with Schema Information
# -------------------------
def generate_filter_sql(query, field, table_name="clauses"):
    # Build a description of the table schema
    if table_name == "clauses":
        # For the main clauses table
        schema_description = "Table clauses schema: clause (TEXT), date (TEXT), money (TEXT), company_name (TEXT)."
    else:
        # For dynamically extracted new field tables
        schema_description = f"Table {table_name} schema: clause (TEXT), {field} (TEXT)."
    
    prompt = (
        f"Given the SQL table structure: {schema_description} "
        f"Based on the query: '{query}', generate SQL code to retrieve rows from the table '{table_name}'. "
        f"Return only the SQL query in a triple-quoted string."
    )
    try:
        response = oai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a SQL query generation agent."},
                {"role": "user", "content": prompt}
            ]
        )
        sql_code = response.choices[0].message.content.strip()
    except Exception as e:
        print("SQL generation error:", e)

    return sql_code

# -------------------------
# Agent 3: SQL Execution Agent
# -------------------------
def execute_generated_sql(sql_code, db_path):
    sql_code = sql_code.replace('```sql', '').replace('```', '')
    print(f"Executing SQL:\n{sql_code}\n")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(sql_code)
        rows = cursor.fetchall()
        # Get column names from the cursor description, if available
        columns = [description[0] for description in cursor.description] if cursor.description else []
        result_df = pd.DataFrame(rows, columns=columns)
        conn.close()
        print("[SQL Execution Agent] Query executed successfully. Results:")
        print(result_df)
    except Exception as e:
        print("SQL execution error:", e)

# -------------------------
# Revised Full Automated Query Handler Using SQL
# -------------------------
def handle_query(query):
    # Decide if the query is a hit (using known fields) or a miss (requires new extraction)
    decision = decide_query_type(query, base_fields)
    
    if decision == "hit":
        for field in base_fields:
            # Check both underscore and space variants
            if field in query.lower() or field.replace("_", " ") in query.lower():
                sql_code = generate_filter_sql(query, field, table_name=TABLE_NAME)
                execute_generated_sql(sql_code, SQL_DB_PATH)
                break
    else:
        # For a miss, assume the new field is the last word in the query (this is just a simplistic heuristic)
        new_field = query.lower().split()[-1]
        print(f"[Miss] New field '{new_field}' extraction initiated.")
        
        # Re-read original LEDGAR clauses if needed
        with open(LEDGAR_PATH, "r") as f:
            clauses = [json.loads(line)['provision'] for line in f.readlines()][:CLAUSE_LIMIT]
        
        def extract_new_field(clause, fields):
            properties = {}
            for field in fields:
                field_key = field.replace(" ", "_")
                properties[field_key] = {"type": "string"}
            schema = {
                "type": "object",
                "properties": properties,
                "required": list(properties.keys()),
                "additionalProperties": False
            }
            
            response = oai_client.responses.create(
                model="gpt-o3-mini",
                input=[
                    {"role": "system", "content": "Extract clause information using a JSON schema."},
                    {"role": "user", "content": (
                        f"Extract the following field from the clause if it exists: {', '.join(fields)}. "
                        f"If the field is not present, return null. Clause: '''{clause}'''"
                    )}
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "clause_info",
                        "schema": schema,
                        "strict": True
                    }
                }
            )
            try:
                result = json.loads(response.output_text)
            except Exception as e:
                print("Error parsing structured output for new field:", e)
                result = {field.replace(" ", "_"): None for field in fields}
            result["clause"] = clause
            return result
        
        new_data = [extract_new_field(clause, [new_field]) for clause in clauses]
        df_new = pd.DataFrame(new_data)
        new_table = f"extracted_{new_field}"
        store_data_in_sql(df_new, SQL_DB_PATH, new_table)
        
        sql_code = generate_filter_sql(query, new_field, table_name=new_table)
        execute_generated_sql(sql_code, SQL_DB_PATH)

# -------------------------
# Example usage:
# -------------------------
if __name__ == "__main__":
    # Test a "hit" query
    user_query = "I want all the clauses that's in Daleware"
    print("Handling query:", user_query)
    handle_query(user_query)
    
    # Uncomment below to test a "miss" query (new field extraction)
    # user_query = "Find clauses that talk about number of employees"
    # print("Handling query:", user_query)
    # handle_query(user_query)