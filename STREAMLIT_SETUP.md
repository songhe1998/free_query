# Streamlit Cloud Setup Guide

## How to Configure OpenAI API Key for Streamlit Cloud

Since we can't put API keys directly in public GitHub repositories (OpenAI automatically disables them), we use Streamlit's built-in secrets management.

### Steps:

1. **Deploy your app to Streamlit Cloud**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Connect your GitHub repository
   - Deploy the app

2. **Add your OpenAI API Key as a secret**
   - Go to your app dashboard on Streamlit Cloud
   - Click "Settings" → "Secrets"
   - Add the following in the secrets text box:

   ```toml
   OPENAI_API_KEY = "your_actual_openai_api_key_here"
   ```

3. **Save and restart the app**
   - Click "Save"
   - Streamlit will automatically restart your app
   - Your app will now securely access the API key via `st.secrets["OPENAI_API_KEY"]`

### For Local Development:

You can either:
- Set environment variable: `export OPENAI_API_KEY="your_key"`
- Or temporarily replace `'your_api_key_here_for_local_testing'` in the code files

### Security Benefits:
- ✅ API key is not visible in your public GitHub repository
- ✅ OpenAI won't automatically disable the key
- ✅ Streamlit Cloud securely manages the secret
- ✅ The key is only accessible to your deployed app

### Files Updated:
- `synthesize_db.py`
- `free_query_v3.py`
- `free_query_v2.py`
- `query_processor.py`
- `free_query.py`
- `query_db.py`

All files now use the pattern:
```python
try:
    import streamlit as st
    oai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except (ImportError, KeyError):
    api_key = os.environ.get('OPENAI_API_KEY', 'your_api_key_here_for_local_testing')
    oai_client = OpenAI(api_key=api_key)
``` 