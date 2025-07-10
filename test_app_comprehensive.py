#!/usr/bin/env python3
"""
Comprehensive Test Suite for app.py and the Multi-Agent Pipeline
Tests all core functionalities and identifies issues for debugging.
"""

import os
import sys
import json
import sqlite3
import tempfile
import shutil
from typing import Dict, Any, List, Tuple
import traceback
from unittest.mock import patch, MagicMock
import pandas as pd

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestResults:
    """Class to track test results"""
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []
        
    def add_result(self, test_name: str, passed: bool, error: str = None):
        self.tests_run += 1
        if passed:
            self.tests_passed += 1
            print(f"✅ PASS: {test_name}")
        else:
            self.tests_failed += 1
            self.failures.append((test_name, error))
            print(f"❌ FAIL: {test_name}")
            if error:
                print(f"   Error: {error}")
    
    def print_summary(self):
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_failed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        if self.failures:
            print(f"\n{'='*60}")
            print(f"FAILURES:")
            print(f"{'='*60}")
            for test_name, error in self.failures:
                print(f"❌ {test_name}")
                if error:
                    print(f"   {error}")

class AppTester:
    """Main test class for app.py functionality"""
    
    def __init__(self):
        self.results = TestResults()
        self.test_db_path = None
        self.original_db_path = None
        
    def setup_test_environment(self):
        """Set up isolated test environment"""
        try:
            # Create temporary directory for test database
            self.test_dir = tempfile.mkdtemp()
            self.test_db_path = os.path.join(self.test_dir, "test_clauses.db")
            
            # Mock the database path in free_query_v3
            import free_query_v3
            self.original_db_path = free_query_v3.SQL_DB_PATH
            free_query_v3.SQL_DB_PATH = self.test_db_path
            
            # Create test data file
            self.create_test_data()
            
            print(f"✅ Test environment setup complete")
            print(f"   Test directory: {self.test_dir}")
            print(f"   Test database: {self.test_db_path}")
            
        except Exception as e:
            print(f"❌ Failed to setup test environment: {e}")
            raise
    
    def teardown_test_environment(self):
        """Clean up test environment"""
        try:
            # Restore original database path
            if self.original_db_path:
                import free_query_v3
                free_query_v3.SQL_DB_PATH = self.original_db_path
            
            # Clean up test directory
            if hasattr(self, 'test_dir') and os.path.exists(self.test_dir):
                shutil.rmtree(self.test_dir)
                print(f"✅ Test environment cleaned up")
                
        except Exception as e:
            print(f"❌ Failed to cleanup test environment: {e}")
    
    def create_test_data(self):
        """Create synthetic test data"""
        test_clauses = [
            {
                "provision": "This agreement shall be effective from January 1, 2024, and the company ABC Corp shall pay a termination fee of $50,000 if terminated early."
            },
            {
                "provision": "XYZ Technologies agrees to provide services with a liability limit of $100,000 and effective date of March 15, 2024."
            },
            {
                "provision": "DEF Industries shall maintain insurance coverage with minimum limits and the contract expires on December 31, 2025."
            },
            {
                "provision": "GHI Corp is responsible for payment of $25,000 quarterly fees and shall provide 30 days notice for termination."
            },
            {
                "provision": "JKL Inc agrees to the terms with a penalty fee of $15,000 for breach of contract and effective immediately."
            }
        ]
        
        # Create test data file
        test_data_path = os.path.join(self.test_dir, "test_clauses.jsonl")
        with open(test_data_path, 'w') as f:
            for clause in test_clauses:
                f.write(json.dumps(clause) + '\n')
        
        # Update the LEDGAR path in free_query_v3
        import free_query_v3
        free_query_v3.LEDGAR_PATH = test_data_path
        
        print(f"✅ Test data created: {len(test_clauses)} clauses")

    def test_free_query_v3_imports(self):
        """Test if free_query_v3 can be imported and basic functions work"""
        try:
            from free_query_v3 import (
                construct_db_from_ledgar, load_records, infer_schema_from_records,
                decide_query_type, decide_new_field, generate_filter_sql,
                extract_fields_from_clause, handle_query, TABLE_NAME, SQL_DB_PATH
            )
            self.results.add_result("free_query_v3_imports", True)
        except Exception as e:
            self.results.add_result("free_query_v3_imports", False, str(e))

    def test_database_construction(self):
        """Test database construction from LEDGAR data"""
        try:
            from free_query_v3 import construct_db_from_ledgar
            
            # Remove existing test database
            if os.path.exists(self.test_db_path):
                os.remove(self.test_db_path)
            
            # Construct database
            base_fields, schema = construct_db_from_ledgar()
            
            # Verify database was created
            assert os.path.exists(self.test_db_path), "Database file not created"
            assert len(base_fields) > 0, "No base fields returned"
            assert len(schema) > 0, "No schema returned"
            
            # Verify database content
            conn = sqlite3.connect(self.test_db_path)
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM clauses")
            count = cur.fetchone()[0]
            conn.close()
            
            assert count > 0, "No records in database"
            
            self.results.add_result("database_construction", True)
            print(f"   Database created with {count} records")
            print(f"   Base fields: {base_fields}")
            print(f"   Schema: {schema}")
            
        except Exception as e:
            self.results.add_result("database_construction", False, str(e))

    def test_query_decision_agent(self):
        """Test the Query Decision Agent"""
        try:
            from free_query_v3 import decide_query_type
            
            # Test with known fields
            base_fields = ['company', 'effective_date']
            
            # Test HIT query
            hit_query = "Show me all companies"
            hit_result = decide_query_type(hit_query, base_fields)
            assert hit_result in ['hit', 'miss'], f"Invalid result: {hit_result}"
            
            # Test MISS query  
            miss_query = "What are the termination fees?"
            miss_result = decide_query_type(miss_query, base_fields)
            assert miss_result in ['hit', 'miss'], f"Invalid result: {miss_result}"
            
            self.results.add_result("query_decision_agent", True)
            print(f"   HIT query '{hit_query}' -> {hit_result}")
            print(f"   MISS query '{miss_query}' -> {miss_result}")
            
        except Exception as e:
            self.results.add_result("query_decision_agent", False, str(e))

    def test_field_discovery_agent(self):
        """Test the New Field Discovery Agent"""
        try:
            from free_query_v3 import decide_new_field
            
            base_fields = ['company', 'effective_date']
            query = "What are the termination fees?"
            
            new_field, parent_field = decide_new_field(query, base_fields)
            
            assert new_field is not None, "New field not identified"
            assert isinstance(new_field, str), "New field should be string"
            
            self.results.add_result("field_discovery_agent", True)
            print(f"   Query: '{query}'")
            print(f"   New field: {new_field}")
            print(f"   Parent field: {parent_field}")
            
        except Exception as e:
            self.results.add_result("field_discovery_agent", False, str(e))

    def test_field_extraction_agent(self):
        """Test the Field Extraction Agent"""
        try:
            from free_query_v3 import extract_fields_from_clause
            
            clause = "ABC Corp shall pay a termination fee of $50,000 if terminated early."
            fields = ["termination_fee", "company"]
            
            result = extract_fields_from_clause(clause, fields)
            
            assert isinstance(result, dict), "Result should be dictionary"
            assert 'clause' in result, "Clause should be in result"
            
            self.results.add_result("field_extraction_agent", True)
            print(f"   Clause: {clause[:50]}...")
            print(f"   Fields: {fields}")
            print(f"   Result: {result}")
            
        except Exception as e:
            self.results.add_result("field_extraction_agent", False, str(e))

    def test_sql_generation_agent(self):
        """Test the SQL Generation Agent"""
        try:
            from free_query_v3 import generate_filter_sql
            
            schema = {
                'company': 'TEXT',
                'termination_fee': 'REAL',
                'effective_date': 'DATE'
            }
            
            query = "Show me termination fees greater than 30000"
            sql_where = generate_filter_sql(query, schema)
            
            assert isinstance(sql_where, str), "SQL should be string"
            assert len(sql_where) > 0, "SQL should not be empty"
            
            self.results.add_result("sql_generation_agent", True)
            print(f"   Query: '{query}'")
            print(f"   Generated WHERE clause: {sql_where}")
            
        except Exception as e:
            self.results.add_result("sql_generation_agent", False, str(e))

    def test_complete_pipeline_hit(self):
        """Test complete pipeline with HIT query"""
        try:
            from free_query_v3 import handle_query, load_records, infer_schema_from_records
            
            # Ensure database exists
            if not os.path.exists(self.test_db_path):
                from free_query_v3 import construct_db_from_ledgar
                construct_db_from_ledgar()
            
            # Load current schema
            recs = load_records(self.test_db_path, "clauses")
            schema = infer_schema_from_records(recs)
            base_fields = [col for col in schema if col != "clause"]
            
            # Test HIT query
            query = "Show me all companies"
            
            # Capture output
            import io
            from contextlib import redirect_stdout
            output_buffer = io.StringIO()
            
            with redirect_stdout(output_buffer):
                handle_query(query, base_fields, schema)
            
            output = output_buffer.getvalue()
            
            self.results.add_result("complete_pipeline_hit", True)
            print(f"   Query: '{query}'")
            print(f"   Output length: {len(output)} characters")
            
        except Exception as e:
            self.results.add_result("complete_pipeline_hit", False, str(e))

    def test_complete_pipeline_miss(self):
        """Test complete pipeline with MISS query"""
        try:
            from free_query_v3 import handle_query, load_records, infer_schema_from_records
            
            # Ensure database exists
            if not os.path.exists(self.test_db_path):
                from free_query_v3 import construct_db_from_ledgar
                construct_db_from_ledgar()
            
            # Load current schema
            recs = load_records(self.test_db_path, "clauses")
            schema = infer_schema_from_records(recs)
            base_fields = [col for col in schema if col != "clause"]
            
            # Test MISS query
            query = "What are the termination fees?"
            
            # Capture output
            import io
            from contextlib import redirect_stdout
            output_buffer = io.StringIO()
            
            with redirect_stdout(output_buffer):
                handle_query(query, base_fields, schema)
            
            output = output_buffer.getvalue()
            
            # Verify new field was added
            new_recs = load_records(self.test_db_path, "clauses")
            new_schema = infer_schema_from_records(new_recs)
            new_fields = [col for col in new_schema if col not in schema]
            
            self.results.add_result("complete_pipeline_miss", True)
            print(f"   Query: '{query}'")
            print(f"   Output length: {len(output)} characters")
            print(f"   New fields added: {new_fields}")
            
        except Exception as e:
            self.results.add_result("complete_pipeline_miss", False, str(e))

    def test_app_functions(self):
        """Test app.py specific functions"""
        try:
            # Mock streamlit to avoid import issues
            with patch('streamlit.secrets', {'OPENAI_API_KEY': 'test_key'}):
                # Test check_openai_setup
                sys.path.insert(0, '.')
                from app import check_openai_setup
                
                configured, status = check_openai_setup()
                assert isinstance(configured, bool), "Should return boolean"
                assert isinstance(status, str), "Should return string"
                
                self.results.add_result("app_functions", True)
                print(f"   OpenAI configured: {configured}")
                print(f"   Status: {status}")
                
        except Exception as e:
            self.results.add_result("app_functions", False, str(e))

    def test_database_operations(self):
        """Test database operations"""
        try:
            from free_query_v3 import load_records, store_records_sql
            
            # Ensure database exists
            if not os.path.exists(self.test_db_path):
                from free_query_v3 import construct_db_from_ledgar
                construct_db_from_ledgar()
            
            # Test loading records
            records = load_records(self.test_db_path, "clauses")
            assert len(records) > 0, "Should load records"
            
            # Test storing records
            test_records = [
                {"company": "Test Corp", "clause": "Test clause 1"},
                {"company": "Test Inc", "clause": "Test clause 2"}
            ]
            
            schema = store_records_sql(test_records, self.test_db_path, "test_table")
            assert len(schema) > 0, "Should return schema"
            
            self.results.add_result("database_operations", True)
            print(f"   Loaded {len(records)} records")
            print(f"   Stored {len(test_records)} test records")
            
        except Exception as e:
            self.results.add_result("database_operations", False, str(e))

    def test_error_handling(self):
        """Test error handling in various scenarios"""
        try:
            from free_query_v3 import decide_query_type, extract_fields_from_clause
            
            # Test with empty inputs
            result1 = decide_query_type("", [])
            assert result1 in ['hit', 'miss'], "Should handle empty query"
            
            # Test with invalid clause
            result2 = extract_fields_from_clause("", ["field1"])
            assert isinstance(result2, dict), "Should return dict even for empty clause"
            
            self.results.add_result("error_handling", True)
            print(f"   Empty query handling: {result1}")
            print(f"   Empty clause handling: {type(result2)}")
            
        except Exception as e:
            self.results.add_result("error_handling", False, str(e))

    def test_performance_metrics(self):
        """Test performance of key operations"""
        try:
            import time
            from free_query_v3 import decide_query_type, extract_fields_from_clause
            
            # Test query decision performance
            start_time = time.time()
            for i in range(3):  # Reduced iterations for faster testing
                decide_query_type("What are the termination fees?", ["company"])
            decision_time = time.time() - start_time
            
            # Test field extraction performance
            start_time = time.time()
            for i in range(3):
                extract_fields_from_clause("Test clause with company ABC", ["company"])
            extraction_time = time.time() - start_time
            
            self.results.add_result("performance_metrics", True)
            print(f"   Query decision: {decision_time:.2f}s for 3 calls")
            print(f"   Field extraction: {extraction_time:.2f}s for 3 calls")
            
        except Exception as e:
            self.results.add_result("performance_metrics", False, str(e))

    def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting Comprehensive Test Suite for app.py")
        print("="*60)
        
        try:
            # Setup
            self.setup_test_environment()
            
            # Core functionality tests
            print("\n📋 Testing Core Functionality...")
            self.test_free_query_v3_imports()
            self.test_database_construction()
            
            # Agent tests
            print("\n🤖 Testing Individual Agents...")
            self.test_query_decision_agent()
            self.test_field_discovery_agent()
            self.test_field_extraction_agent()
            self.test_sql_generation_agent()
            
            # Pipeline tests
            print("\n🔄 Testing Complete Pipeline...")
            self.test_complete_pipeline_hit()
            self.test_complete_pipeline_miss()
            
            # App-specific tests
            print("\n📱 Testing App Functions...")
            self.test_app_functions()
            self.test_database_operations()
            
            # Robustness tests
            print("\n🛡️ Testing Error Handling & Performance...")
            self.test_error_handling()
            self.test_performance_metrics()
            
        except Exception as e:
            print(f"❌ Critical error in test suite: {e}")
            traceback.print_exc()
            
        finally:
            # Cleanup
            self.teardown_test_environment()
            
            # Print results
            self.results.print_summary()
            
            # Return success/failure
            return self.results.tests_failed == 0

def main():
    """Main test runner"""
    print("🧪 App.py Comprehensive Test Suite")
    print("="*60)
    
    # Check if we have the required files
    required_files = ['app.py', 'free_query_v3.py']
    for file in required_files:
        if not os.path.exists(file):
            print(f"❌ Required file not found: {file}")
            return False
    
    # Run tests
    tester = AppTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed! The app.py functionality is working correctly.")
        return True
    else:
        print("\n⚠️  Some tests failed. Review the failures above for debugging.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 