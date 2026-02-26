import httpx
import asyncio

async def test():
    # IDs to check
    ids = ["1", "2", "4", "8", "10", "14", "7", "22", "24", "36", "37", "30", "18", "40", "41", "35", "27"]
    gql_query = """
    query {
      genres(kind: "anime") {
        id
        name
        russian
      }
    }
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            res = await client.post(
                "https://shikimori.one/api/graphql",
                json={"query": gql_query},
                headers={"User-Agent": "NekoStream/2.0"}
            )
            data = res.json()
            if "data" in data and "genres" in data["data"]:
                genres = data["data"]["genres"]
                mapping = {g["id"]: g["russian"] for g in genres}
                print(json.dumps(mapping, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"Error: {e}")

import json
asyncio.run(test())
