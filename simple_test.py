#!/usr/bin/env python3
"""
Simple Test Suite for Core Query Functionality
Tests SQL generation and direct query execution
"""

import sqlite3
from free_query_v3 import (
    generate_filter_sql, load_records, infer_schema_from_records, 
    SQL_DB_PATH, TABLE_NAME
)

def test_core_queries():
    """Test core query functionality"""
    print("🧪 CORE QUERY FUNCTIONALITY TEST")
    print("="*50)
    
    # Load database state
    records = load_records(SQL_DB_PATH, TABLE_NAME)
    schema = infer_schema_from_records(records)
    
    print(f"Database: {len(records)} records")
    print(f"Schema: {len(schema)} fields")
    
    # Test queries
    test_cases = [
        ("Small Company Search", "Find clauses about small companies", 4),
        ("Termination Search", "What clauses mention termination?", 4),
        ("Risk Assessment", "Show me clauses about risk assessment", 9),
        ("Agreement Duration", "Find clauses about agreement duration", 9),
        ("High Fee Search", "Show contracts with fees over $3000", 3),
        ("Contract Value", "Find contracts worth more than $100,000", 1),
        ("Company Listing", "Show me all companies", 5),
        ("Date Search", "What clauses mention dates?", 3),
        ("Effective Date", "Find clauses with effective dates", 2),
        ("Monthly Fee", "Show clauses with monthly fees", 3),
        ("Payment Terms", "Find payment terms", 9),
        ("Risk Level", "What are the risk levels?", 8),
        ("Risk Score", "Show clauses with risk scores", 8),
        ("Industry Search", "What industries are mentioned?", 3),
        ("Liability Search", "Show me liability clauses", 0),
    ]
    
    passed = 0
    total = len(test_cases)
    
    for name, query, expected_count in test_cases:
        print(f"\n🧪 {name}")
        print(f"   Query: '{query}'")
        
        try:
            # Generate SQL
            where_clause = generate_filter_sql(query, schema, TABLE_NAME)
            
            # Construct full SQL
            if where_clause and where_clause.strip() and where_clause != "1=0":
                full_sql = f"SELECT * FROM {TABLE_NAME} WHERE {where_clause}"
            else:
                full_sql = f"SELECT * FROM {TABLE_NAME}"
            
            # Execute query
            conn = sqlite3.connect(SQL_DB_PATH)
            cur = conn.cursor()
            cur.execute(full_sql)
            results = cur.fetchall()
            conn.close()
            
            result_count = len(results)
            
            # Check results
            if result_count == expected_count:
                print(f"   ✅ PASS: {result_count} results (expected {expected_count})")
                passed += 1
            else:
                print(f"   ❌ FAIL: {result_count} results (expected {expected_count})")
            
            # Show sample result
            if results:
                columns = [desc[0] for desc in cur.description] if cur.description else []
                sample = dict(zip(columns, results[0])) if columns else {}
                clause = sample.get('clause', '')[:60] + "..." if sample.get('clause') else "N/A"
                print(f"   Sample: {clause}")
            
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
    
    print(f"\n📊 SUMMARY")
    print(f"Passed: {passed}/{total} ({(passed/total)*100:.1f}%)")
    
    if passed == total:
        print("🎉 ALL CORE TESTS PASSED!")
    else:
        print(f"⚠️  {total-passed} test(s) failed")

if __name__ == "__main__":
    test_core_queries() 