import sqlite3
import pandas as pd

print('Testing database connection...')
conn = sqlite3.connect('clauses.db')
cur = conn.cursor()

# Test basic queries
cur.execute('SELECT COUNT(*) FROM clauses WHERE amount IS NOT NULL')
amount_count = cur.fetchone()[0]
print(f'Clauses with amounts: {amount_count}')

cur.execute('SELECT COUNT(*) FROM clauses WHERE company IS NOT NULL')
company_count = cur.fetchone()[0]
print(f'Clauses with companies: {company_count}')

cur.execute('SELECT COUNT(*) FROM clauses WHERE risk_score IS NOT NULL')
risk_count = cur.fetchone()[0]
print(f'Clauses with risk scores: {risk_count}')

# Test pandas queries
print('\nTesting pandas queries...')
try:
    amount_df = pd.read_sql_query("""
        SELECT amount, company, risk_score 
        FROM clauses 
        WHERE amount IS NOT NULL 
        ORDER BY amount DESC
    """, conn)
    print(f'Amount dataframe shape: {amount_df.shape}')
    print(f'Sample amounts: {amount_df.head(3)["amount"].tolist()}')
except Exception as e:
    print(f'Error with amount query: {e}')

try:
    company_df = pd.read_sql_query("""
        SELECT company, COUNT(*) as clause_count 
        FROM clauses 
        WHERE company IS NOT NULL 
        GROUP BY company 
        ORDER BY clause_count DESC
    """, conn)
    print(f'Company dataframe shape: {company_df.shape}')
    print(f'Top companies: {company_df.head(3)["company"].tolist()}')
except Exception as e:
    print(f'Error with company query: {e}')

conn.close()
print('Database tests completed successfully!') 