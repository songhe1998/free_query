import streamlit as st
import pandas as pd
import sqlite3
import json
from query_processor import process_query
import plotly.express as px
import plotly.graph_objects as go

# Page configuration
st.set_page_config(
    page_title="Clause Query System",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .query-example {
        background-color: #e8f4fd;
        padding: 0.5rem;
        border-radius: 0.3rem;
        margin: 0.2rem 0;
        cursor: pointer;
    }
    .result-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border: 1px solid #dee2e6;
    }
</style>
""", unsafe_allow_html=True)

def get_database_stats():
    """Get statistics about the database"""
    try:
        conn = sqlite3.connect('clauses.db')
        cur = conn.cursor()
        
        # Total clauses
        cur.execute("SELECT COUNT(*) FROM clauses")
        total_clauses = cur.fetchone()[0]
        
        # Companies with data
        cur.execute("SELECT COUNT(DISTINCT company) FROM clauses WHERE company IS NOT NULL")
        unique_companies = cur.fetchone()[0]
        
        # Amount statistics
        cur.execute("SELECT MIN(amount), MAX(amount), AVG(amount) FROM clauses WHERE amount IS NOT NULL")
        amount_stats = cur.fetchone()
        
        # Risk score statistics
        cur.execute("SELECT MIN(risk_score), MAX(risk_score), AVG(risk_score) FROM clauses WHERE risk_score IS NOT NULL")
        risk_stats = cur.fetchone()
        
        # Date range
        cur.execute("SELECT MIN(effective_date), MAX(effective_date) FROM clauses WHERE effective_date IS NOT NULL")
        date_range = cur.fetchone()
        
        conn.close()
        
        return {
            'total_clauses': total_clauses,
            'unique_companies': unique_companies,
            'amount_stats': amount_stats,
            'risk_stats': risk_stats,
            'date_range': date_range
        }
    except Exception as e:
        st.error(f"Error getting database stats: {e}")
        return None

def get_sample_data():
    """Get sample data for visualization"""
    try:
        conn = sqlite3.connect('clauses.db')
        
        # Amount distribution
        amount_df = pd.read_sql_query("""
            SELECT amount, company, risk_score 
            FROM clauses 
            WHERE amount IS NOT NULL 
            ORDER BY amount DESC
        """, conn)
        
        # Risk score distribution
        risk_df = pd.read_sql_query("""
            SELECT risk_score, risk_level, company 
            FROM clauses 
            WHERE risk_score IS NOT NULL
        """, conn)
        
        # Company distribution
        company_df = pd.read_sql_query("""
            SELECT company, COUNT(*) as clause_count 
            FROM clauses 
            WHERE company IS NOT NULL 
            GROUP BY company 
            ORDER BY clause_count DESC
        """, conn)
        
        conn.close()
        
        return amount_df, risk_df, company_df
    except Exception as e:
        st.error(f"Error getting sample data: {e}")
        return None, None, None

def display_query_results(results):
    """Display query results in a nice format"""
    if not results:
        st.warning("No results found for your query.")
        return
    
    st.success(f"Found {len(results)} matching clauses!")
    
    for i, result in enumerate(results):
        with st.expander(f"Clause {i+1} - {result.get('company', 'Unknown Company')}", expanded=i<3):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown("**Clause Text:**")
                st.write(result.get('clause', 'No clause text available'))
            
            with col2:
                st.markdown("**Details:**")
                details = []
                if result.get('company'):
                    details.append(f"**Company:** {result['company']}")
                if result.get('amount'):
                    details.append(f"**Amount:** ${result['amount']:,.2f}")
                if result.get('risk_score'):
                    details.append(f"**Risk Score:** {result['risk_score']}")
                if result.get('risk_level'):
                    details.append(f"**Risk Level:** {result['risk_level']}")
                if result.get('effective_date'):
                    details.append(f"**Effective Date:** {result['effective_date']}")
                if result.get('payment_frequency'):
                    details.append(f"**Payment Frequency:** {result['payment_frequency']}")
                
                for detail in details:
                    st.markdown(detail)

def main():
    # Header
    st.markdown('<h1 class="main-header">📋 Clause Query System</h1>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("🔍 Query Examples")
        st.markdown("Click on any example to try it:")
        
        example_queries = [
            "Find clauses with amount over 100000",
            "Show me clauses with risk score above 70", 
            "Find clauses from Tech Innovations",
            "Show clauses effective in 2024",
            "Find clauses with quarterly payments",
            "Show me high risk clauses",
            "Find clauses from XYZ Technologies",
            "Show clauses with USD currency",
            "Find clauses expiring in 2026"
        ]
        
        for query in example_queries:
            if st.button(query, key=f"example_{query}", use_container_width=True):
                st.session_state.query_input = query
        
        st.markdown("---")
        st.header("📊 Database Stats")
        
        stats = get_database_stats()
        if stats:
            st.metric("Total Clauses", stats['total_clauses'])
            st.metric("Unique Companies", stats['unique_companies'])
            
            if stats['amount_stats'][0]:
                st.metric("Amount Range", f"${stats['amount_stats'][0]:,.0f} - ${stats['amount_stats'][1]:,.0f}")
            
            if stats['risk_stats'][0]:
                st.metric("Risk Score Range", f"{stats['risk_stats'][0]:.1f} - {stats['risk_stats'][1]:.1f}")
    
    # Main content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("🔎 Query Interface")
        
        # Query input
        query_input = st.text_input(
            "Enter your query:",
            value=st.session_state.get('query_input', ''),
            placeholder="e.g., Find clauses with amount over 50000",
            key="main_query_input"
        )
        
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
        with col_btn1:
            search_clicked = st.button("🔍 Search", type="primary", use_container_width=True)
        with col_btn2:
            clear_clicked = st.button("🗑️ Clear", use_container_width=True)
        
        if clear_clicked:
            st.session_state.query_input = ""
            st.rerun()
        
        # Process query
        if search_clicked and query_input:
            with st.spinner("Processing your query..."):
                try:
                    results = process_query(query_input)
                    st.session_state.last_results = results
                    st.session_state.last_query = query_input
                except Exception as e:
                    st.error(f"Error processing query: {e}")
                    results = None
        
        # Display results
        if hasattr(st.session_state, 'last_results') and st.session_state.last_results:
            st.markdown("---")
            st.header("📋 Query Results")
            display_query_results(st.session_state.last_results)
    
    with col2:
        st.header("📈 Database Overview")
        
        # Get sample data for visualizations
        amount_df, risk_df, company_df = get_sample_data()
        
        if amount_df is not None and not amount_df.empty:
            # Amount distribution
            st.subheader("💰 Amount Distribution")
            fig_amount = px.histogram(
                amount_df, 
                x='amount', 
                nbins=10,
                title="Distribution of Clause Amounts",
                labels={'amount': 'Amount ($)', 'count': 'Number of Clauses'}
            )
            fig_amount.update_layout(height=300)
            st.plotly_chart(fig_amount, use_container_width=True)
        
        if risk_df is not None and not risk_df.empty:
            # Risk score distribution
            st.subheader("⚠️ Risk Score Distribution")
            fig_risk = px.scatter(
                risk_df, 
                x='risk_score', 
                y='company',
                color='risk_level',
                title="Risk Scores by Company",
                labels={'risk_score': 'Risk Score', 'company': 'Company'}
            )
            fig_risk.update_layout(height=300)
            st.plotly_chart(fig_risk, use_container_width=True)
        
        if company_df is not None and not company_df.empty:
            # Company distribution
            st.subheader("🏢 Top Companies")
            fig_company = px.bar(
                company_df.head(10), 
                x='clause_count', 
                y='company',
                orientation='h',
                title="Clauses by Company",
                labels={'clause_count': 'Number of Clauses', 'company': 'Company'}
            )
            fig_company.update_layout(height=300)
            st.plotly_chart(fig_company, use_container_width=True)
    
    # Footer with tips
    st.markdown("---")
    st.header("💡 Query Tips")
    
    tip_cols = st.columns(3)
    
    with tip_cols[0]:
        st.markdown("""
        **🔢 Numeric Queries:**
        - "amount over 100000"
        - "risk score above 70"
        - "fee less than 1000"
        """)
    
    with tip_cols[1]:
        st.markdown("""
        **🏢 Company Queries:**
        - "clauses from Microsoft"
        - "Tech Innovations contracts"
        - "XYZ Technologies agreements"
        """)
    
    with tip_cols[2]:
        st.markdown("""
        **📅 Date Queries:**
        - "effective in 2024"
        - "expiring in 2026"
        - "clauses from January"
        """)

if __name__ == "__main__":
    main() 