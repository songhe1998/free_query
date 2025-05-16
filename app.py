# streamlit_app.py
"""
Simple Streamlit front‑end for the clause‑querying demo.
Assumes the helper functions from your earlier script are available
(either in this file or imported from a utils module).
"""

from pathlib import Path
import os
import json
import sqlite3
import streamlit as st
from typing import Dict, List, Any

# ──────────────────── 1.  IMPORT HELPERS ────────────────────
# You pasted the big script in utils.py?  Then:
#   from utils import (
#       construct_db_from_ledgar, load_records, infer_schema_from_records,
#       decide_query_type, generate_filter_sql, execute_generated_sql,
#       decide_new_field, extract_fields_from_clause, store_records_sql,
#       random_date, LEDGAR_PATH, CLAUSE_LIMIT, SQL_DB_PATH, TABLE_NAME
#   )
#
# For a quick demo you can also copy‑paste the helper functions
# directly here (omitted for brevity).

# Below we import **only** what we call in the UI.
from utils import (                         # type: ignore
    construct_db_from_ledgar,
    load_records,
    infer_schema_from_records,
    decide_query_type,
    generate_filter_sql,
    execute_generated_sql,
    decide_new_field,
    extract_fields_from_clause,
    random_date,
    store_records_sql,
    LEDGAR_PATH,
    CLAUSE_LIMIT,
    SQL_DB_PATH,
    TABLE_NAME,
)

# ──────────────────── 2.  INITIALISE DB ONCE ────────────────────
@st.cache_resource(show_spinner="Building or loading database…")
def init_db() -> Dict[str, str]:
    if not Path(SQL_DB_PATH).exists():
        base_fields, schema = construct_db_from_ledgar()
    else:
        records = load_records(SQL_DB_PATH, TABLE_NAME)
        schema  = infer_schema_from_records(records)
        base_fields = [c for c in schema if c != "clause"]
    return {"schema": schema, "base_fields": base_fields}

state = init_db()
schema      = state["schema"]
base_fields = state["base_fields"]

# ──────────────────── 3.  STREAMLIT UI ────────────────────
st.title("Clause‑QL demo")

query = st.text_input(
    "Ask a question about the clauses:",
    placeholder="e.g. clauses with zebra percentage > 0.5",
)

if st.button("Run query") and query.strip():
    with st.spinner("Thinking…"):
        decision = decide_query_type(query, base_fields)

        # ----- HIT branch -----
        if decision == "hit":
            sql = generate_filter_sql(query, schema, TABLE_NAME)
            sql_clean = sql.replace("```sql", "").replace("```", "").strip().strip('"""')
            st.code(sql_clean, language="sql")

            # Execute & display
            conn = sqlite3.connect(SQL_DB_PATH)
            df   = None
            try:
                df = st.session_state.get("pd", __import__("pandas")).read_sql_query(sql_clean, conn)
            finally:
                conn.close()

            if df is not None and not df.empty:
                st.dataframe(df)
            else:
                st.info("No rows returned.")

        # ----- MISS branch -----
        else:
            new_field = decide_new_field(query)
            st.warning(f"Field “{new_field}” not extracted yet ‑‑ extracting now…")

            # Re‑extract the new field for all raw clauses
            with open(LEDGAR_PATH, "r") as f:
                raw = [json.loads(line)["provision"] for line in f][:CLAUSE_LIMIT]
            clauses = [
                c + (f" effective date: {random_date()}" if os.urandom(1)[0] < 128 else "")
                for c in raw
            ]
            records   = [
                extract_fields_from_clause(c, [new_field]) for c in clauses
            ]
            new_table = f"extracted_{new_field}"
            new_schema = store_records_sql(records, SQL_DB_PATH, new_table)

            sql = generate_filter_sql(query, new_schema, new_table)
            sql_clean = sql.replace("```sql", "").replace("```", "").strip().strip('"""')
            st.code(sql_clean, language="sql")

            # Execute & display
            conn = sqlite3.connect(SQL_DB_PATH)
            df   = None
            try:
                df = st.session_state.get("pd", __import__("pandas")).read_sql_query(sql_clean, conn)
            finally:
                conn.close()

            if df is not None and not df.empty:
                st.dataframe(df)
            else:
                st.info("No rows returned.")

# ──────────────────── 4.  FOOTER ────────────────────
st.caption(
    "All GPT calls powered by the OpenAI SDK ‑ set your key in "
    "the environment variable **OPENAI_API_KEY** before running."
)