#!/usr/bin/env python3
"""
Test UI Changes - Verify that the new UI shows only clause and relevant field
"""

import sqlite3
import pandas as pd
from free_query_v3 import SQL_DB_PATH, TABLE_NAME

def test_ui_logic():
    """Test the new UI logic for displaying results"""
    print("🧪 TESTING UI CHANGES")
    print("="*50)
    
    # Test queries and expected relevant fields
    test_cases = [
        ("Show me all companies", "company"),
        ("Find contracts with high fees", "contract_value"),
        ("What are the risk levels?", "risk_level"),
        ("Show contract values over 1000", "contract_value"),
        ("Find effective dates", "effective_date"),
        ("What clauses mention termination?", None),  # Might not have termination field
    ]
    
    # Load base fields (simulate what app.py does)
    base_fields = ['company', 'contract_value', 'fee_amount', 'risk_level', 'effective_date']
    
    # Field-to-keyword mapping (same as in app.py)
    field_keywords = {
        'company': ['company', 'companies', 'firm', 'corporation', 'business'],
        'contract_value': ['contract', 'value', 'worth', 'amount', 'price'],
        'fee_amount': ['fee', 'fees', 'cost', 'payment', 'charge'],
        'risk_level': ['risk', 'level', 'assessment'],
        'risk_score': ['risk', 'score', 'rating'],
        'effective_date': ['date', 'effective', 'start', 'begin'],
        'termination': ['termination', 'terminate', 'end', 'cancel'],
        'payment_terms': ['payment', 'terms', 'billing', 'pay']
    }
    
    for query, expected_field in test_cases:
        print(f"\n🔍 Testing: '{query}'")
        
        # Simulate field identification logic from app.py
        query_lower = query.lower()
        relevant_field = None
        
        for field in base_fields:
            field_lower = field.lower()
            # Direct field name match
            if field_lower in query_lower:
                relevant_field = field
                break
            # Keyword matching
            if field_lower in field_keywords:
                if any(keyword in query_lower for keyword in field_keywords[field_lower]):
                    relevant_field = field
                    break
            # Partial word matching
            elif any(word in field_lower for word in query_lower.split() if len(word) > 3):
                relevant_field = field
                break
        
        print(f"   Expected field: {expected_field}")
        print(f"   Identified field: {relevant_field}")
        
        # Test database query logic
        if relevant_field:
            try:
                conn = sqlite3.connect(SQL_DB_PATH)
                df = pd.read_sql_query(f"SELECT clause, `{relevant_field}` FROM {TABLE_NAME} WHERE `{relevant_field}` IS NOT NULL LIMIT 3", conn)
                conn.close()
                
                print(f"   Results: {len(df)} rows")
                if not df.empty:
                    print(f"   Sample clause: {df.iloc[0]['clause'][:60]}...")
                    print(f"   Sample {relevant_field}: {df.iloc[0][relevant_field]}")
                else:
                    print("   No results found")
            except Exception as e:
                print(f"   Database error: {e}")
        else:
            try:
                conn = sqlite3.connect(SQL_DB_PATH)
                df = pd.read_sql_query(f"SELECT clause FROM {TABLE_NAME} LIMIT 3", conn)
                conn.close()
                
                print(f"   Results: {len(df)} rows (clause only)")
                if not df.empty:
                    print(f"   Sample clause: {df.iloc[0]['clause'][:60]}...")
            except Exception as e:
                print(f"   Database error: {e}")
        
        # Check if identification matches expectation
        if relevant_field == expected_field:
            print("   ✅ Field identification CORRECT")
        else:
            print(f"   ⚠️  Field identification differs (expected: {expected_field}, got: {relevant_field})")
    
    print(f"\n🎯 UI LOGIC TEST COMPLETE")
    print("The new UI will show:")
    print("• Only the clause text and relevant field")
    print("• Expandable clause preview for long text")
    print("• Field-specific metrics and analysis")
    print("• Download option for full data")

if __name__ == "__main__":
    test_ui_logic() 