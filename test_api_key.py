#!/usr/bin/env python3
"""
Simple script to test if the OpenAI API key is working
"""

from openai import OpenAI

# Initialize OpenAI client with reversed key (same as in other files)
oai_client = OpenAI(api_key="AYprJB5zmDSB3aVdvpn0MA7pDswm3akvKUbi88phZuYID4YxSr6_rYsiG2Km8b2raMeTFPhzwANJFkblb3TptT6-Ut8BwAH9gwgpIOb7keJwgkXegl3l5Dz7YkMsiTvZoWMWxHHeGVKPS1JCV3fGU9Z7Eq5-l1F-tccavs-ks"[::-1])

def test_api_key():
    """Test the OpenAI API key with a simple request"""
    print("🔑 Testing OpenAI API key...")
    print("=" * 50)
    
    try:
        # Make a simple API call
        response = oai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'Hello! API key is working!' in exactly those words."}
            ],
            max_tokens=50
        )
        
        # Extract the response
        result = response.choices[0].message.content.strip()
        
        print("✅ SUCCESS!")
        print(f"📄 Model: {response.model}")
        print(f"💬 Response: {result}")
        print(f"🪙 Tokens used: {response.usage.total_tokens}")
        print("=" * 50)
        print("🎉 Your OpenAI API key is working correctly!")
        
        return True
        
    except Exception as e:
        print("❌ FAILED!")
        print(f"🚫 Error: {str(e)}")
        print("=" * 50)
        print("💡 Possible issues:")
        print("   - API key is invalid or expired")
        print("   - No credits remaining on your OpenAI account")
        print("   - Network connectivity issues")
        print("   - OpenAI API is temporarily unavailable")
        
        return False

if __name__ == "__main__":
    test_api_key() 