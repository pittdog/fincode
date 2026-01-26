import asyncio
from agent.tools.polymarket_tool import PolymarketClient
from dotenv import load_dotenv

load_dotenv()

async def list_seoul_markets():
    client = PolymarketClient()
    # Search for closed and active markets
    markets = await client.gamma_search("weather Seoul", status="all", limit=500)
    
    # Filter for "highest temperature" and sort by date and threshold
    relevant = []
    for m in markets:
        if "highest temperature" in m.question.lower() and "Seoul" in m.question:
            relevant.append(m)
            
    # Sort by end_date
    relevant.sort(key=lambda x: x.end_date)
    
    print(f"Found {len(relevant)} Seoul temperature markets:")
    for m in relevant:
        print(f"{m.id} | {m.end_date[:10]} | {m.question}")
        
    await client.close()

if __name__ == "__main__":
    asyncio.run(list_seoul_markets())
