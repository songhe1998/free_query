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

# Main app logic
def main():
    # Check OpenAI setup
    openai_available, openai_status = check_openai_setup()
    
    if not openai_available:
        st.error("🔧 Setup Required")
        st.warning(openai_status)
        
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
            """)
        
        st.info("Once configured, this app will allow you to analyze legal documents using natural language queries!")
        return
    
    # If OpenAI is configured, show the main app
    st.success("✅ OpenAI API key configured successfully!")
    
    # Import query processor only when OpenAI is available
    try:
        from query_processor import process_query
        
        st.markdown("### 🔍 Query Legal Documents")
        
        # Query input
        user_query = st.text_input(
            "Enter your query about legal documents:",
            placeholder="e.g., Show me clauses with amounts greater than $1000"
        )
        
        if st.button("🚀 Process Query", type="primary"):
            if user_query:
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
                            st.info("No results found for your query.")
                            
                    except Exception as e:
                        st.error(f"Error processing query: {str(e)}")
                        st.info("Please check your API key configuration and try again.")
            else:
                st.warning("Please enter a query.")
    
    except ImportError as e:
        st.error(f"Error importing query processor: {e}")
        st.info("There might be an issue with the OpenAI configuration. Please check the setup instructions above.")

if __name__ == "__main__":
    main() 