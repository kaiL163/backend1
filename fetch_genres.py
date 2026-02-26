import httpx
import json

async def test():
    gql_query = """
    query {
      genres {
        id
        name
        russian
        kind
      }
    }
    """
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://shikimori.one/api/graphql",
            json={"query": gql_query},
            headers={"User-Agent": "NekoStream/2.0"}
        )
        data = res.json()
        if "data" in data and "genres" in data["data"]:
            # Filter for anime genres
            anime_genres = [g for g in data["data"]["genres"] if g["kind"] == "anime"]
            print(json.dumps(anime_genres, indent=2, ensure_ascii=False))

import asyncio
asyncio.run(test())
