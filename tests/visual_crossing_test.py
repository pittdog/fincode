import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from agent.tools.visual_crossing_client import VisualCrossingClient

# Load env from .env file explicitly if needed, though usually python-dotenv handles this
load_dotenv()

async def test_api_connectivity():
    api_key = os.getenv("VISUAL_CROSSING_API_KEY")
    print(f"DEBUG: Loaded API Key: {api_key[:5]}...{api_key[-5:] if api_key else 'None'}")
    
    if not api_key:
        print("ERROR: VISUAL_CROSSING_API_KEY not found in environment.")
        return

    client = VisualCrossingClient(api_key=api_key)
    
    try:
        print("\nTesting connectivity for London, 2024-01-01...")
        weather_data = await client.get_day_weather("London", "2026-01-01")
        
        if weather_data:
            print("SUCCESS: Weather data received!")
            print(f"Max Temp: {weather_data.get('tempmax')} F")
            print(f"Min Temp: {weather_data.get('tempmin')} F")
            print(f"Conditions: {weather_data.get('conditions')}")
        else:
            print("FAILURE: No data returned (possible auth error or invalid request).")
            
    except Exception as e:
        print(f"EXCEPTION: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_api_connectivity())
