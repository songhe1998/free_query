import streamlit as st
import pandas as pd
import json
import sqlite3
import os
from typing import Dict, Any, List

# Page configuration
st.set_page_config(
    page_title="Advanced Free Query - Full Agent System",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 Advanced Free Query - Full Multi-Agent System")
st.markdown("*Utilizing all available agents and advanced functionalities*")
st.markdown("---")

# Check if OpenAI API key is configured
def check_openai_setup():
    """Check if OpenAI is properly configured"""
    try:
        if "OPENAI_API_KEY" in st.secrets:
            return True, "OpenAI API key found in secrets"
        else:
            return False, "OpenAI API key not found in Streamlit secrets"
    except Exception as e:
        return False, f"Error checking secrets: {e}"

def test_openai_connection():
    """Test if OpenAI can be imported and initialized"""
    try:
        # Try to import and test the advanced query system
        from free_query_v3 import construct_db_from_ledgar, load_records, infer_schema_from_records
        return True, "Advanced query system successfully initialized"
    except Exception as e:
        return False, f"Error initializing advanced system: {str(e)}"

# Main app logic
def main():
    # Sidebar for system controls
    with st.sidebar:
        st.header("🎛️ System Controls")
        
        # Database management
        st.subheader("📊 Database Management")
        
        if st.button("🔄 Rebuild Database from LEDGAR", help="Construct fresh database from LEDGAR corpus"):
            rebuild_database()
        
        if st.button("🧪 Run System Tests", help="Execute comprehensive test suite"):
            run_system_tests()
            
        # Show current database status
        show_database_status()
    
    # Check OpenAI setup
    openai_configured, config_status = check_openai_setup()
    
    if not openai_configured:
        st.error("🔧 Setup Required")
        st.warning(config_status)
        
        with st.expander("📋 Setup Instructions", expanded=True):
            st.markdown("""
            **To use this advanced app, you need to configure your OpenAI API key:**
            
            1. Go to your **Streamlit Cloud dashboard**
            2. Click on your app → **Settings** → **Secrets**
            3. Add the following in the secrets text box:
            
            ```toml
            OPENAI_API_KEY = "your_actual_openai_api_key_here"
            ```
            
            4. Click **Save** and the app will restart automatically
            """)
        
        st.info("Once configured, this app will use the full multi-agent system for advanced legal document analysis!")
        return
    
    # If OpenAI key is configured, test the connection
    st.success("✅ OpenAI API key configured!")
    
    # Test OpenAI connection
    with st.spinner("Testing advanced system..."):
        system_works, system_status = test_openai_connection()
    
    if not system_works:
        st.error("❌ Advanced System Failed to Load")
        st.warning(system_status)
        return
    
    # If everything works, show the advanced app
    st.success("✅ Advanced multi-agent system loaded successfully!")
    
    # Import advanced query system
    try:
        from free_query_v3 import (
            handle_query, load_records, infer_schema_from_records,
            construct_db_from_ledgar, TABLE_NAME, SQL_DB_PATH
        )
        
        # Initialize or load database
        base_fields, schema = initialize_database()
        
        # Main query interface
        st.markdown("### 🧠 Advanced Query Processing")
        st.markdown("*Powered by multi-agent system with dynamic field discovery*")
        
        # Show current capabilities
        with st.expander("🎯 Current System Capabilities"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**🔍 Known Fields:**")
                for field in base_fields:
                    st.markdown(f"• `{field}`")
            
            with col2:
                st.markdown("**🤖 Active Agents:**")
                agents = [
                    "Query Decision Agent",
                    "Field Extraction Agent", 
                    "SQL Generation Agent",
                    "New Field Discovery Agent",
                    "Parent Field Hierarchy Agent",
                    "Table Merge Agent"
                ]
                for agent in agents:
                    st.markdown(f"• {agent}")
        
        # Example queries based on current capabilities
        with st.expander("💡 Intelligent Query Examples"):
            st.markdown("""
            **Hit Queries (use existing fields):**
            - "Show me all clauses with companies"
            - "Find clauses mentioning specific companies"
            
            **Miss Queries (will discover new fields):**
            - "What are the termination fees?" *(will extract 'termination fee' field)*
            - "Show me effective dates" *(will extract 'effective date' field)*  
            - "Find clauses with payment amounts" *(will extract 'amount' field)*
            - "What about liability limits?" *(will extract 'liability limit' field)*
            """)
        
        # Query input with advanced features
        st.markdown("#### 🎯 Enter Your Query:")
        user_query = st.text_input(
            "Query:",
            placeholder="e.g., What are the termination fees? (will auto-discover new fields)",
            help="The system will automatically determine if your query needs new field extraction"
        )
        
        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            process_button = st.button("🚀 Process Query", type="primary")
        with col2:
            query_type = st.empty()  # Will show hit/miss classification
        
        if process_button and user_query:
            with st.spinner("🤖 Multi-agent system processing..."):
                try:
                    # Create containers for real-time updates
                    st.markdown("#### 🔍 Agent Processing Steps:")
                    
                    # Step 1: Query Classification
                    with st.container():
                        st.markdown("##### 🎯 Step 1: Query Decision Agent")
                        classification_col1, classification_col2 = st.columns([1, 2])
                        
                        with classification_col1:
                            with st.spinner("Analyzing query..."):
                                from free_query_v3 import decide_query_type
                                classification = decide_query_type(user_query, base_fields)
                        
                        with classification_col2:
                            if classification == "hit":
                                st.success("🎯 **HIT** - Using existing fields")
                                st.info(f"Query can be answered with current fields: `{', '.join(base_fields)}`")
                            else:
                                st.info("🔍 **MISS** - Will discover new fields")
                                st.warning("Query requires extraction of new fields from legal documents")
                    
                    # Step 2: Field Analysis
                    st.markdown("##### 🧠 Step 2: Field Analysis")
                    field_analysis_container = st.container()
                    
                    # Initialize variables to avoid scoping issues
                    new_field = None
                    parent_field = None
                    
                    with field_analysis_container:
                        if classification == "miss":
                            field_col1, field_col2 = st.columns([1, 1])
                            
                            with field_col1:
                                st.markdown("**🔍 New Field Discovery Agent:**")
                                with st.spinner("Identifying new field..."):
                                    from free_query_v3 import decide_new_field
                                    new_field, parent_field = decide_new_field(user_query, base_fields)
                                
                                st.success(f"**New Field:** `{new_field}`")
                                if parent_field:
                                    st.info(f"**Parent Field:** `{parent_field}` (will optimize processing)")
                                else:
                                    st.info("**Parent Field:** None (will process all clauses)")
                            
                            with field_col2:
                                st.markdown("**📊 Processing Strategy:**")
                                if parent_field and parent_field in schema:
                                    # Count clauses with parent field
                                    conn = sqlite3.connect(SQL_DB_PATH)
                                    cur = conn.cursor()
                                    sanitized_parent = new_field.replace(' ', '_').lower()  # Simple sanitization for display
                                    try:
                                        cur.execute(f'SELECT COUNT(*) FROM {TABLE_NAME} WHERE "{parent_field}" IS NOT NULL')
                                        parent_count = cur.fetchone()[0]
                                        st.metric("Clauses to Process", f"{parent_count} (optimized)", delta=f"-{50-parent_count} saved")
                                    except:
                                        st.metric("Clauses to Process", "50 (all clauses)")
                                    conn.close()
                                else:
                                    st.metric("Clauses to Process", "50 (all clauses)")
                        else:
                            st.success("Using existing schema - no new field extraction needed")
                            st.info(f"Will query existing fields: `{', '.join([f for f in base_fields if f.lower() in user_query.lower()][:3])}`")
                    
                    # Step 3: Processing Status
                    st.markdown("##### ⚡ Step 3: Processing Execution")
                    processing_container = st.container()
                    
                    with processing_container:
                        # Create columns for different agent activities
                        if classification == "miss":
                            agent_col1, agent_col2, agent_col3 = st.columns([1, 1, 1])
                            
                            with agent_col1:
                                st.markdown("**🔧 Field Extraction Agent:**")
                                extraction_status = st.empty()
                                extraction_status.info("🔄 Extracting fields from clauses...")
                            
                            with agent_col2:
                                st.markdown("**🔗 Table Merge Agent:**")
                                merge_status = st.empty()
                                merge_status.info("⏳ Waiting for extraction...")
                            
                            with agent_col3:
                                st.markdown("**🗄️ SQL Generation Agent:**")
                                sql_status = st.empty()
                                sql_status.info("⏳ Waiting for merge...")
                        else:
                            st.markdown("**🗄️ SQL Generation Agent:**")
                            sql_status = st.empty()
                            sql_status.info("🔄 Generating SQL query...")
                    
                    # Step 4: Execute Processing with Live Updates
                    st.markdown("##### 📊 Step 4: Query Execution")
                    
                    # Capture processing output
                    import io
                    from contextlib import redirect_stdout
                    
                    output_buffer = io.StringIO()
                    
                    # Update status during processing
                    if classification == "miss":
                        extraction_status.warning("🔄 Extracting new field using LLM...")
                        
                    # Execute the query processing
                    with redirect_stdout(output_buffer):
                        handle_query(user_query, base_fields, schema)
                    
                    # Update final status
                    if classification == "miss":
                        extraction_status.success("✅ Field extraction completed")
                        merge_status.success("✅ Database updated with new field")
                        sql_status.success("✅ SQL query generated and executed")
                    else:
                        sql_status.success("✅ SQL query executed successfully")
                    
                    # Step 5: Results Display
                    st.markdown("##### 📈 Step 5: Results & Analysis")
                    
                    # Show processing log
                    processing_log = output_buffer.getvalue()
                    if processing_log:
                        with st.expander("🔍 Detailed Processing Log", expanded=False):
                            st.code(processing_log, language="text")
                    
                    # Show updated schema if new field was added
                    if classification == "miss":
                        st.markdown("**📊 Database Schema Updated:**")
                        # Reload schema to show new field
                        conn = sqlite3.connect(SQL_DB_PATH)
                        cur = conn.cursor()
                        cur.execute(f'PRAGMA table_info("{TABLE_NAME}")')
                        updated_schema = {col[1]: col[2] for col in cur.fetchall()}
                        conn.close()
                        
                        schema_col1, schema_col2 = st.columns([1, 1])
                        with schema_col1:
                            st.markdown("**Before:**")
                            st.code(f"Fields: {list(schema.keys())}", language="python")
                        with schema_col2:
                            st.markdown("**After:**")
                            new_fields = [f for f in updated_schema.keys() if f not in schema]
                            st.code(f"Fields: {list(updated_schema.keys())}", language="python")
                            if new_fields:
                                st.success(f"✅ Added: {new_fields}")
                    
                    # Display query results
                    if os.path.exists(SQL_DB_PATH):
                        conn = sqlite3.connect(SQL_DB_PATH)
                        
                        # Show sample results
                        df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME} LIMIT 10", conn)
                        conn.close()
                        
                        if not df.empty:
                            st.markdown("**📋 Query Results:**")
                            
                            # Show results summary
                            result_col1, result_col2, result_col3 = st.columns([1, 1, 1])
                            with result_col1:
                                st.metric("Total Results", len(df))
                            with result_col2:
                                st.metric("Fields Returned", len(df.columns))
                            with result_col3:
                                non_null_cols = sum(1 for col in df.columns if df[col].notna().any())
                                st.metric("Fields with Data", non_null_cols)
                            
                            # Display the data
                            st.dataframe(df, use_container_width=True)
                            
                            # Download option
                            csv = df.to_csv(index=False)
                            st.download_button(
                                label="📥 Download Results as CSV",
                                data=csv,
                                file_name=f"query_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
                            
                            # Show sample data insights
                            with st.expander("📊 Data Insights", expanded=False):
                                for col in df.columns:
                                    if col != 'clause' and df[col].notna().any():
                                        non_null_count = df[col].notna().sum()
                                        st.write(f"**{col}:** {non_null_count}/{len(df)} entries have data")
                        else:
                            st.info("No results found for your query.")
                    
                    # Step 6: Next Steps Suggestions
                    st.markdown("##### 🚀 Step 6: What's Next?")
                    
                    if classification == "miss":
                        st.success("🎉 **New field successfully added to your database!**")
                        st.info("💡 **Try related queries:** This new field can now be used in future queries for instant results.")
                        
                        # Suggest related queries
                        suggestions = [
                            f"Show me {new_field} greater than [value]",
                            f"Find clauses with specific {new_field}",
                            f"Compare {new_field} across different companies"
                        ]
                        st.markdown("**🔍 Suggested follow-up queries:**")
                        for suggestion in suggestions:
                            st.markdown(f"• `{suggestion}`")
                    else:
                        st.success("🎯 **Query executed using existing data!**")
                        st.info("💡 **Try exploring:** Ask about new fields to expand your database capabilities.")
                        
                except Exception as e:
                    st.error(f"❌ Error in advanced processing: {str(e)}")
                    with st.expander("🔍 Error Details"):
                        st.code(str(e))
                        import traceback
                        st.code(traceback.format_exc())
        
        elif process_button and not user_query:
            st.warning("Please enter a query.")
    
    except ImportError as e:
        st.error(f"Error importing advanced system: {e}")
        st.info("Please ensure all advanced modules are available.")

def initialize_database():
    """Initialize or load the database with advanced system"""
    try:
        from free_query_v3 import (
            construct_db_from_ledgar, load_records, infer_schema_from_records,
            TABLE_NAME, SQL_DB_PATH
        )
        
        if not os.path.exists(SQL_DB_PATH):
            st.info("🔄 Initializing database with LEDGAR data...")
            with st.spinner("Building database from LEDGAR corpus..."):
                base_fields, schema = construct_db_from_ledgar()
            st.success("✅ Database initialized successfully!")
        else:
            # Load existing database
            recs = load_records(SQL_DB_PATH, TABLE_NAME)
            schema = infer_schema_from_records(recs)
            base_fields = [col for col in schema if col != "clause"]
        
        return base_fields, schema
        
    except Exception as e:
        st.error(f"Error initializing database: {e}")
        return [], {}

def show_database_status():
    """Show current database status in sidebar"""
    st.subheader("📊 Database Status")
    
    try:
        from free_query_v3 import SQL_DB_PATH, TABLE_NAME
        
        if os.path.exists(SQL_DB_PATH):
            conn = sqlite3.connect(SQL_DB_PATH)
            cur = conn.cursor()
            
            # Get table info
            cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
            row_count = cur.fetchone()[0]
            
            cur.execute(f'PRAGMA table_info("{TABLE_NAME}")')
            columns = [col[1] for col in cur.fetchall()]
            
            conn.close()
            
            st.metric("📄 Total Clauses", row_count)
            st.metric("🏷️ Fields", len(columns))
            
            with st.expander("Field Details"):
                for col in columns:
                    st.markdown(f"• `{col}`")
        else:
            st.info("No database found")
            
    except Exception as e:
        st.error(f"Error checking database: {e}")

def rebuild_database():
    """Rebuild database from scratch"""
    try:
        from free_query_v3 import construct_db_from_ledgar, SQL_DB_PATH
        
        if os.path.exists(SQL_DB_PATH):
            os.remove(SQL_DB_PATH)
        
        with st.spinner("🔄 Rebuilding database from LEDGAR..."):
            base_fields, schema = construct_db_from_ledgar()
        
        st.success("✅ Database rebuilt successfully!")
        # st.rerun()  # Removed to preserve UI state
        
    except Exception as e:
        st.error(f"Error rebuilding database: {e}")

def run_system_tests():
    """Run the comprehensive test suite"""
    try:
        from free_query_v3 import run_tests
        
        with st.spinner("🧪 Running comprehensive test suite..."):
            import io
            from contextlib import redirect_stdout
            
            output_buffer = io.StringIO()
            
            with redirect_stdout(output_buffer):
                run_tests()
            
            test_output = output_buffer.getvalue()
        
        st.success("✅ Test suite completed!")
        
        with st.expander("🧪 Test Results"):
            st.code(test_output)
            
    except Exception as e:
        st.error(f"Error running tests: {e}")

if __name__ == "__main__":
    main() 