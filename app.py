import streamlit as st
import pandas as pd
import json
import sqlite3
from typing import Dict, Any, List

# Page configuration
st.set_page_config(
    page_title="Free Query - Legal Document Analysis",
    page_icon="⚖️",
    layout="wide"
)

st.title("⚖️ Free Query - Legal Document Analysis")
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
        # Try to import and test the query processor
        from query_processor import check_openai_client
        if check_openai_client():
            return True, "OpenAI client successfully initialized"
        else:
            return False, "OpenAI client initialization failed"
    except Exception as e:
        return False, f"Error initializing OpenAI: {str(e)}"

# Main app logic
def main():
    # Check OpenAI setup
    openai_configured, config_status = check_openai_setup()
    
    if not openai_configured:
        st.error("🔧 Setup Required")
        st.warning(config_status)
        
        with st.expander("📋 Setup Instructions", expanded=True):
            st.markdown("""
            **To use this app, you need to configure your OpenAI API key:**
            
            1. Go to your **Streamlit Cloud dashboard**
            2. Click on your app → **Settings** → **Secrets**
            3. Add the following in the secrets text box:
            
            ```toml
            OPENAI_API_KEY = "your_actual_openai_api_key_here"
            ```
            
            4. Click **Save** and the app will restart automatically
            
            **Get your OpenAI API key:**
            - Go to [OpenAI Platform](https://platform.openai.com/account/api-keys)
            - Create a new API key
            - Copy and paste it into the Streamlit secrets
            
            **Note:** Make sure your OpenAI account has sufficient credits.
            """)
        
        st.info("Once configured, this app will allow you to analyze legal documents using natural language queries!")
        return
    
    # If OpenAI key is configured, test the connection
    st.success("✅ OpenAI API key configured!")
    
    # Test OpenAI connection
    with st.spinner("Testing OpenAI connection..."):
        openai_works, openai_status = test_openai_connection()
    
    if not openai_works:
        st.error("❌ OpenAI Connection Failed")
        st.warning(openai_status)
        
        with st.expander("🔧 Troubleshooting", expanded=True):
            st.markdown("""
            **Common issues and solutions:**
            
            1. **Invalid API Key**: Check that your API key is correct and hasn't expired
            2. **No Credits**: Ensure your OpenAI account has sufficient credits
            3. **API Key Format**: Make sure the key starts with 'sk-' and is complete
            4. **Compatibility Issue**: The app might need to restart after configuration
            
            **Try these steps:**
            1. Double-check your API key in Streamlit secrets
            2. Verify your OpenAI account has credits
            3. Try restarting the app (modify and save any file to trigger restart)
            """)
        return
    
    # If everything works, show the main app
    st.success("✅ OpenAI connection successful!")
    
    # Import query processor only when everything is working
    try:
        from query_processor import process_query
        
        st.markdown("### 🔍 Query Legal Documents")
        st.markdown("Ask questions about legal documents in natural language!")
        
        # Example queries
        with st.expander("💡 Example Queries"):
            st.markdown("""
            - "Show me clauses with amounts greater than $1000"
            - "Find clauses mentioning Microsoft"
            - "What are the termination clauses?"
            - "Show clauses with effective dates in 2023"
            """)
        
        # Query input
        user_query = st.text_input(
            "Enter your query:",
            placeholder="e.g., Show me clauses with amounts greater than $1000"
        )
        
        col1, col2 = st.columns([1, 4])
        with col1:
            process_button = st.button("🚀 Process Query", type="primary")
        
        if process_button and user_query:
            with st.spinner("Processing your query..."):
                try:
                    results = process_query(user_query)
                    
                    if results:
                        st.success(f"Found {len(results)} results!")
                        
                        # Display results
                        df = pd.DataFrame(results)
                        st.dataframe(df, use_container_width=True)
                        
                        # Download option
                        csv = df.to_csv(index=False)
                        st.download_button(
                            label="📥 Download Results as CSV",
                            data=csv,
                            file_name=f"query_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.info("No results found for your query. Try a different query or check if the database has relevant data.")
                        
                except Exception as e:
                    st.error(f"Error processing query: {str(e)}")
                    with st.expander("🔍 Error Details"):
                        st.code(str(e))
                    st.info("Please try a different query or check your API key configuration.")
        
        elif process_button and not user_query:
            st.warning("Please enter a query.")
    
    except ImportError as e:
        st.error(f"Error importing query processor: {e}")
        st.info("There might be an issue with the OpenAI configuration. Please check the setup instructions above.")

if __name__ == "__main__":
    main() 