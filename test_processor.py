from query_processor import process_query
import json

def print_results(query: str, results: list):
    print(f"\n{'='*80}")
    print(f"Query: {query}")
    print(f"Number of results: {len(results)}")
    if results:
        print("\nFirst result:")
        print(json.dumps(results[0], indent=2))
    print('='*80)

def test_queries():
    # Test cases
    test_cases = [
        # Basic company queries
        "Show me clauses about Microsoft",
        "Find clauses mentioning Google",
        "What are the clauses for ABC Tech Solutions",
        
        # Date queries
        "Show me clauses from 2024",
        "Find clauses effective in January 2024",
        
        # Value/amount queries
        "Show me clauses with value over 5000",
        "Find clauses with payment amount of 50000",
        
        # Complex queries
        "Find Microsoft clauses from 2024 with value over 5000",
        "Show me ABC Tech Solutions clauses with payment terms",
        
        # Edge cases
        "Show me all clauses",
        "Find clauses with no company specified"
    ]
    
    print("\nTesting Query Processor...")
    print("Database should be loaded with sample data first")
    
    for query in test_cases:
        results = process_query(query)
        print_results(query, results)

if __name__ == "__main__":
    test_queries() 