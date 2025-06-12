from query_processor import process_query
import sqlite3

# Test specific queries
queries = [
    'Show me clauses from Tech Innovations',
    'Find clauses with amount over 100000',
    'Show me clauses with risk score above 70',
    'Find clauses effective in 2024'
]

for query in queries:
    print(f'\n=== Testing: {query} ===')
    result = process_query(query)
    if result:
        print(f'Found {len(result)} results')
        if result:
            print('Sample result:', result[0]['company'] if result[0].get('company') else 'No company', 
                  '- Amount:', result[0].get('amount'), '- Risk Score:', result[0].get('risk_score'))
    else:
        print('No results found') 