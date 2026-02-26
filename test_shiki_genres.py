import httpx
import json

async def test():
    gql_query = """
    query {
      animes(limit: 5, genre: "Action") {
        id
        name
        russian
        genres { name }
      }
    }
    """
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://shikimori.one/api/graphql",
            json={"query": gql_query},
            headers={"User-Agent": "NekoStream/2.0"}
        )
        print("GENRE NAME RESPONSE:", res.status_code)
        print(json.dumps(res.json(), indent=2, ensure_ascii=False))

    gql_query_id = """
    query {
      animes(limit: 5, genre: "1") {
        id
        name
        russian
        genres { name }
      }
    }
    """
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://shikimori.one/api/graphql",
            json={"query": gql_query_id},
            headers={"User-Agent": "NekoStream/2.0"}
        )
        print("\nGENRE ID RESPONSE:", res.status_code)
        print(json.dumps(res.json(), indent=2, ensure_ascii=False))

import asyncio
asyncio.run(test())
