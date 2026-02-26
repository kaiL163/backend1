import asyncio
import httpx

async def main():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://127.0.0.1:8000/kodik/by-shikimori/5114", timeout=15.0)
            print("STATUS:", resp.status_code)
            print("JSON 5114 FOUND:", resp.json()["found"], resp.json().get("metadata", {}).get("title"))
    except Exception as e:
        print("HTTPX Error:", type(e), e)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://127.0.0.1:8000/kodik/by-shikimori/11061", timeout=15.0)
            print("STATUS 11061:", resp.status_code)
            print("JSON 11061 FOUND:", resp.json()["found"])
    except Exception as e:
        print("HTTPX Error 11061:", type(e), e)

if __name__ == "__main__":
    asyncio.run(main())
