import httpx
import json
import asyncio

async def test_links():
    tokens = ["a0457eb45312af80bbb9f3fb33de3e93", "447d179e875efe44217f20d1ee2146be"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://kodik.info/"
    }
    async with httpx.AsyncClient() as client:
        for token in tokens:
            print(f"\n--- Testing token: {token} ---")
            url = "https://kodikapi.com/search"
            params = {
                "token": token,
                "shikimori_id": 1535,
                "with_link": "true",
                "with_episodes": "true",
                "limit": 1
            }
            try:
                res = await client.get(url, params=params, headers=headers)
                print(f"Status: {res.status_code}")
                data = res.json()
                results = data.get("results", [])
                if results:
                    first = results[0]
                    print(f"Keys: {list(first.keys())}")
                    if "links" in first:
                        print("Direct links found at root!")
                    
                    seasons = first.get("seasons", [])
                    if seasons:
                        print(f"Number of seasons: {len(seasons)}")
                        first_s = seasons[0]
                        eps = first_s.get("episodes", [])
                        if eps:
                            first_e = eps[0]
                            print(f"First episode keys: {list(first_e.keys())}")
                            if "links" in first_e:
                                print("Direct links found in episode!")
                            else:
                                print("NO DIRECT LINKS in episode")
                        else:
                            print("No episodes found in season")
                    else:
                        print("No seasons field")
                else:
                    print("No results found")
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_links())
