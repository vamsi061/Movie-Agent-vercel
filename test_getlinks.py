#!/usr/bin/env python3
"""
Test script for getlinks_ URL handling
Run this in a new terminal within the Movie_Agent venv
"""

from moviezwap_agent import MoviezWapAgent
import requests
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_getlinks_url():
    print("="*60)
    print("Testing MoviezWap getlinks_ URL handling")
    print("="*60)
    
    # Test URL with send.now link
    test_url = 'https://www.moviezwap.pink/getlinks_66793.html'
    print(f"Testing URL: {test_url}")
    print()
    
    try:
        # Test 1: Direct agent test
        print("1. Testing MoviezWap agent directly...")
        agent = MoviezWapAgent()
        result = agent.resolve_fast_download_server(test_url)
        
        print("Direct agent result:", result)
        print()
        
        # Test 2: Web interface endpoint test
        print("2. Testing web interface /resolve_download endpoint...")
        try:
            response = requests.post('http://localhost:8080/resolve_download', 
                                   json={'url': test_url},
                                   timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Web interface SUCCESS:")
                print(f"   Status: {data.get('status')}")
                print(f"   Final URL: {data.get('final_download_url')}")
                print(f"   Message: {data.get('message')}")
            else:
                print(f"❌ Web interface FAILED: {response.status_code}")
                print(response.text)
                
        except requests.exceptions.ConnectionError:
            print("⚠️  Web interface not running (start with: python web_interface.py)")
        except Exception as e:
            print(f"❌ Web interface ERROR: {str(e)}")
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_getlinks_url()