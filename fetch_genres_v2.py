import httpx
import asyncio
import json

async def test():
    gql_query = "query { genres(kind: \"anime\") { id name russian } }"
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            res = await client.post(
                "https://shikimori.one/api/graphql",
                json={"query": gql_query},
                headers={"User-Agent": "NekoStream/2.0"},
                follow_redirects=True
            )
            print(f"Status: {res.status_code}")
            data = res.json()
            if "data" in data and "genres" in data["data"]:
                genres = data["data"]["genres"]
                print(json.dumps(genres, indent=2, ensure_ascii=False))
            else:
                print("No data in response")
                print(json.dumps(data, indent=2))
        except Exception as e:
            print(f"Exception: {type(e).__name__} - {e}")

if __name__ == "__main__":
    asyncio.run(test())
