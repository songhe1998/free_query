import streamlit as st
import pandas as pd
import json
from query_processor import process_query
import sqlite3
from typing import Dict, Any, List

st.set_page_config(page_title="Clause Query Tester", layout="wide")

def get_db_schema() -> Dict[str, str]:
    """Get the current database schema."""
    conn = sqlite3.connect("clauses.db")
    cur = conn.cursor()
    cur.execute('PRAGMA table_info("clauses")')
    schema = {col[1]: col[2] for col in cur.fetchall()}
    conn.close()
    return schema

def get_sample_data() -> pd.DataFrame:
    """Get a sample of data from the database."""
    conn = sqlite3.connect("clauses.db")
    df = pd.read_sql_query("SELECT * FROM clauses LIMIT 5", conn)
    conn.close()
    return df

def main():
    st.title("Clause Query Tester")
    
    # Sidebar for test controls
    st.sidebar.header("Test Controls")
    test_mode = st.sidebar.radio(
        "Test Mode",
        ["Single Query", "Batch Test"]
    )
    
    if test_mode == "Single Query":
        # Single query testing
        query = st.text_input("Enter your query:")
        
        if st.button("Run Query"):
            if query:
                with st.spinner("Processing query..."):
                    # Process the query
                    results = process_query(query)
                    
                    # Display results
                    st.subheader("Query Results")
                    if results:
                        st.json(results)
                    else:
                        st.warning("No results found")
                    
                    # Display database schema
                    st.subheader("Current Database Schema")
                    schema = get_db_schema()
                    st.json(schema)
                    
                    # Display sample data
                    st.subheader("Sample Data")
                    sample_data = get_sample_data()
                    st.dataframe(sample_data)
            else:
                st.error("Please enter a query")
    
    else:
        # Batch testing
        st.subheader("Batch Test Cases")
        
        # Test cases
        test_cases = [
            {
                "name": "Basic Company Query",
                "query": "Show me clauses about Microsoft",
                "expected_hit": True,
                "expected_field": "company"
            },
            {
                "name": "Date Range Query",
                "query": "Find clauses from 2023",
                "expected_hit": True,
                "expected_field": "effective_date"
            },
            {
                "name": "Numeric Value Query",
                "query": "Show clauses with value greater than 1000000",
                "expected_hit": True,
                "expected_field": "value"
            },
            {
                "name": "Complex Query",
                "query": "Find Microsoft clauses from 2023 with value over 1 million",
                "expected_hit": True,
                "expected_fields": ["company", "effective_date", "value"]
            }
        ]
        
        if st.button("Run Batch Tests"):
            results = []
            for test in test_cases:
                with st.spinner(f"Running test: {test['name']}"):
                    # Process query
                    query_results = process_query(test['query'])
                    
                    # Analyze results
                    hit = bool(query_results)
                    fields = set()
                    if query_results:
                        fields = set(query_results[0].keys()) - {'clause'}
                    
                    # Record test results
                    test_result = {
                        "Test Name": test['name'],
                        "Query": test['query'],
                        "Expected Hit": test['expected_hit'],
                        "Actual Hit": hit,
                        "Expected Field": test.get('expected_field', test.get('expected_fields', [])),
                        "Actual Fields": list(fields),
                        "Result Count": len(query_results) if query_results else 0
                    }
                    results.append(test_result)
            
            # Display test results
            st.subheader("Test Results")
            results_df = pd.DataFrame(results)
            st.dataframe(results_df)
            
            # Display detailed results for each test
            for i, test in enumerate(test_cases):
                with st.expander(f"Details for {test['name']}"):
                    st.json(results[i])

if __name__ == "__main__":
    main() 