"""
AnimeSite Python Backend v3.0
All data from Kodik API (primary) with Kinobox as secondary players.
Run: uvicorn main:app --reload --port 8000
"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
import re
import os
import asyncio
import datetime

# Database and Auth imports
from database import engine, Base
import models
from routers import users
from fastapi.staticfiles import StaticFiles

# Create database tables
Base.metadata.create_all(bind=engine)

os.makedirs("static/avatars", exist_ok=True)

KODIK_TOKEN = "a0457eb45312af80bbb9f3fb33de3e93" # Fallback

async def get_kodik_token():
    """Returns the hardcoded Kodik token as requested."""
    return "a0457eb45312af80bbb9f3fb33de3e93"

# ── HTTP CLIENTS ──────────────────────────────────────────────
# We use separate transports to control retry behavior effectively.
shikimori_transport = httpx.AsyncHTTPTransport(retries=0)
kodik_transport = httpx.AsyncHTTPTransport(retries=0)

http_client = httpx.AsyncClient(
    transport=shikimori_transport,
    limits=httpx.Limits(max_keepalive_connections=10, max_connections=100),
    timeout=httpx.Timeout(5.0), # Stricter global timeout
    http2=False
)

app = FastAPI(title="NekoStream API", version="3.1.0")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://0.0.0.0:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Kodik Token that refreshes
KODIK_TOKEN = "a0457eb45312af80bbb9f3fb33de3e93" # Initial fallback

@app.on_event("startup")
async def startup_event():
    global KODIK_TOKEN
    # Token is now hardcoded as requested by user
    print(f"[Startup] Using pre-defined Kodik token: {KODIK_TOKEN[:5]}...")

kodik_client = httpx.AsyncClient(
    transport=kodik_transport,
    limits=httpx.Limits(max_keepalive_connections=10, max_connections=100),
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json",
    },
    timeout=httpx.Timeout(30.0), 
    http2=False
)

from typing import Optional, Tuple, Any

SHIKIMORI_DOMAINS = ["shikimori.io", "shikimori.one", "shikimori.me"]
_STICKY_DOMAIN = "shikimori.io"

# API domains (working mirrors for backend search)
KODIK_API_DOMAINS = ["kodikapi.com", "kodik-api.com", "kodikas.biz", "kodiapi.com"]
_KODIK_STICKY_API = "kodikapi.com"

# Player domains (browser mirrors preferred by user)
# Player domains (browser mirrors preferred by user)
KODIK_PLAYER_DOMAINS = ["kodikapi.com", "kodik.info", "kodik.cc", "kodikdb.com"]

async def fetch_shikimori_graphql(query: str, variables: Optional[dict] = None) -> Tuple[Optional[Any], Optional[str]]:
    global _STICKY_DOMAIN
    ordered = [_STICKY_DOMAIN] + [d for d in SHIKIMORI_DOMAINS if d != _STICKY_DOMAIN]
    for domain in ordered:
        try:
            res = await http_client.post(
                f"https://{domain}/api/graphql",
                json={"query": query, "variables": variables} if variables else {"query": query},
                headers={"User-Agent": "NekoStream/2.0", "Connection": "close"},
                timeout=2.0
            )
            if res.status_code == 200:
                _STICKY_DOMAIN = domain
                return res, domain
        except: continue
    return None, None

async def fetch_kodik_api(endpoint: str, params: dict) -> Tuple[list, Optional[str]]:
    global _KODIK_STICKY_API, KODIK_TOKEN
    
    # Prioritize sticky, then others
    ordered = [_KODIK_STICKY_API] + [d for d in KODIK_API_DOMAINS if d != _KODIK_STICKY_API]
    
    for domain in ordered:
        try:
            full_params = {"token": KODIK_TOKEN, **params}
            url = f"https://{domain}{endpoint}"
            # Use a fresh client for each mirror to avoid session issues if needed, 
            # but kodik_client is fine.
            res = await kodik_client.get(url, params=full_params) 
            
            if res.status_code == 200:
                data = res.json()
                results = data.get("results", [])
                if results:
                    if domain != _KODIK_STICKY_API:
                        print(f"[Kodik/api] Sticky switch: {domain}")
                        _KODIK_STICKY_API = domain
                    return results, domain
                else:
                    print(f"[Kodik/api] {domain} returned 0 results for {params.get('shikimori_id')}")
            else:
                # Log status and truncated token for debugging on Render
                masked_token = f"{KODIK_TOKEN[:4]}...{KODIK_TOKEN[-4:]}" if KODIK_TOKEN else "None"
                print(f"[Kodik/api] {domain} error {res.status_code} (Token: {masked_token})")
        except Exception as e:
            # print(f"[Kodik/api] {domain} failed: {e}")
            continue
            
    return [], None


def sanitize_description(text: str) -> str:
    if not text:
        return ""
    # Strip BBCode-like tags: [anime=123]Content[/anime] -> Content
    # Removes both [tag=...] and [/tag]
    cleaned = re.sub(r'\[/?(?:anime|character|person|comment|club|style|entry|url|img|b|i|u|s|size|span|color|quote|code|list|item|br)[^\]]*\]', '', text)
    return cleaned.strip()

# Static and Routers
app.mount("/avatars", StaticFiles(directory="static/avatars"), name="avatars")
app.include_router(users.router)


# ── Health ────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"status": "ok", "version": "3.0.0", "primary": "kodik"}



# ═════════════════════════════════════════════════════════════
# KODIK — SEARCH (for player + title metadata)
# ═════════════════════════════════════════════════════════════

@app.get("/kodik/search")
async def kodik_search(title: str = Query(...)):
    """
    Search Kodik by Russian/English title.
    Returns translations grouped by translation_id + metadata.
    """
    try:
        r = await kodik_client.get("https://kodikapi.com/search", params={
            "token": KODIK_TOKEN,
            "title": title,
            "with_material_data": "true",
            "limit": 50,
            "types": "anime,anime-serial",
        })

        if r.status_code != 200:
            return {"results": [], "error": f"HTTP {r.status_code}"}

        data = r.json()
        raw: list[dict] = data.get("results", [])

        seen: dict[str, dict] = {}
        kinopoisk_id = None
        shikimori_id = None

        for item in raw:
            if not kinopoisk_id and item.get("kinopoisk_id"):
                kinopoisk_id = str(item["kinopoisk_id"])
            if not shikimori_id and item.get("shikimori_id"):
                shikimori_id = str(item["shikimori_id"])

            t = item.get("translation", {})
            key = str(t.get("id", t.get("title", "")))
            if key not in seen:
                link: str = item.get("link", "")
                if link.startswith("//"):
                    link = "https:" + link
                link = link.replace(".info", ".cc")
                seen[key] = {
                    "translation_id": key,
                    "translation_title": t.get("title", ""),
                    "translation_type": t.get("type", "voice"),
                    "link": link,
                }

        return {
            "results": list(seen.values()),
            "kinopoisk_id": kinopoisk_id,
            "shikimori_id": shikimori_id,
        }

    except Exception as e:
        print(f"[Kodik/search] Error for '{title}': {e}")
        return {"results": [], "error": str(e)}


# ── Title Data Caching ────────────────────────────────────────
_TITLE_DATA_CACHE = {} # { shikimori_id: {"data": ..., "expiry": ...} }
_TITLE_DATA_TTL = 43200 # 12 Hours

@app.get("/kodik/by-shikimori/{shikimori_id}")
async def kodik_by_shikimori(shikimori_id: str):
    """
    Get full anime info from Shikimori GraphQL + translations from Kodik using Shikimori ID.
    Caches combined results for 12 hours.
    """
    global _TITLE_DATA_CACHE
    now = datetime.datetime.now().timestamp()
    
    # 1. Check Cache
    if shikimori_id in _TITLE_DATA_CACHE:
        entry = _TITLE_DATA_CACHE[shikimori_id]
        if now < entry["expiry"]:
            # Optionally: we could check if translations are present and if not, try to re-fetch Kodik
            # but for simplicity, we serve the cache.
            return entry["data"]

    try:
        # SEQUENTIAL FETCH
        shiki_data = {}
        active_shiki_domain = None
        
        # 1. Fetch Shikimori Metadata
        gql_query = f"""
        query {{
          animes(ids: "{shikimori_id}", limit: 1) {{
            id name russian score poster {{ originalUrl }}
            episodes episodesAired status kind description
            genres {{ name }} airedOn {{ year }}
          }}
        }}
        """
        try:
            res_shiki, shiki_dom = await fetch_shikimori_graphql(gql_query)
            if res_shiki and res_shiki.status_code == 200:
                s_list = res_shiki.json().get("data", {}).get("animes", [])
                if s_list:
                    shiki_data = s_list[0]
                    active_shiki_domain = shiki_dom
        except: pass

        # 2. Fetch Kodik Translations
        kodik_raw = []
        try:
            kodik_raw, _ = await fetch_kodik_api("/search", {
                "shikimori_id": shikimori_id,
                "with_material_data": "true",
                "with_episodes": "true",
                "limit": 50,
            })
        except: pass

        if not shiki_data and not kodik_raw:
            # Short cache for failures
            _TITLE_DATA_CACHE[shikimori_id] = {
                "data": {"found": False, "metadata": None, "translations": []},
                "expiry": now + 30 
            }
            return {"found": False, "metadata": None, "translations": []}

        # 3. Process Data
        active_domain = active_shiki_domain
        kodik_poster = None
        kinopoisk_id = ""
        if kodik_raw:
            first = kodik_raw[0]
            if isinstance(first, dict):
                md = first.get("material_data") or {}
                kodik_poster = md.get("poster_url")
                kinopoisk_id = str(first.get("kinopoisk_id") or "")

        # Extract posters and fix URLs
        shiki_poster = (shiki_data.get("poster", {}) or {}).get("originalUrl")
        if isinstance(shiki_poster, str) and shiki_poster.startswith("/"):
            if active_domain:
                shiki_poster = f"https://{active_domain}{shiki_poster}"
            else:
                shiki_poster = f"https://shikimori.one{shiki_poster}"
        
        # Build combined metadata
        metadata = {
            "shikimori_id": shikimori_id,
            "kinopoisk_id": kinopoisk_id,
            "title": shiki_data.get("russian") or shiki_data.get("name") or "",
            "title_orig": shiki_data.get("name") or "",
            "year": shiki_data.get("airedOn", {}).get("year") if shiki_data.get("airedOn") else None,
            "anime_kind": shiki_data.get("kind", ""),
            "anime_status": shiki_data.get("status", ""),
            "episodes_total": shiki_data.get("episodes"),
            "episodes_aired": shiki_data.get("episodesAired"),
            "poster": shiki_poster or kodik_poster,
            "description": sanitize_description(shiki_data.get("description", "")),
            "genres": [g["name"] for g in shiki_data.get("genres", [])] if shiki_data.get("genres") else [],
            "shikimori_rating": shiki_data.get("score"),
            "screenshots": [],
        }

        seen: dict[str, dict] = {}
        if isinstance(kodik_raw, list):
            for item in kodik_raw:
                if not isinstance(item, dict):
                    continue
                t = item.get("translation", {})
                key = str(t.get("id", t.get("title", "")))
                if key not in seen:
                    link: str = item.get("link", "")
                    if link.startswith("//"):
                        link = "https:" + link
                    
                    # Rewrite player link to use working user-provided mirror
                    # We take the first one (kodik.cc) as primary player mirror
                    for old in ["kodikapi.com", "kodik.info", "kodik.biz", "kodik.cc", "kodikdb.com"]:
                        if old in link:
                            link = link.replace(old, KODIK_PLAYER_DOMAINS[0])
                            break
                    
                    # Compute episode count
                    ep_count = item.get("episodes_count")
                    if not ep_count:
                        ep_count = item.get("last_episode")
                    if not ep_count:
                        ep_count = 1
                        
                    seen[key] = {
                        "translation_id": key,
                        "translation_title": t.get("title", ""),
                        "translation_type": t.get("type", "voice"),
                        "link": link,
                        "episodes_count": int(ep_count),
                    }

        result = {
            "found": True,
            "metadata": metadata,
            "translations": list(seen.values()),
        }
        
        # 5. Update Cache (Only if we found something useful)
        if result["found"] and (shiki_data or kodik_raw):
            _TITLE_DATA_CACHE[shikimori_id] = {
                "data": result,
                "expiry": now + _TITLE_DATA_TTL
            }
            
        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Kodik/by-shikimori] Global Error for '{shikimori_id}': e={type(e).__name__} {e}")
        return {"found": False, "metadata": None, "translations": [], "error": str(e)}


# ═════════════════════════════════════════════════════════════
# SHIKIMORI CATALOG (WITH KODIK POSTERS)
from fastapi import Request

@app.post("/shikimori/catalog")
async def shikimori_catalog(request: Request):
    """
    Proxy to Shikimori GraphQL API.
    Fetches the catalog from Shikimori, then extracts the IDs, queries Kodik for those IDs, 
    and injects Kodik's reliable poster URLs into the Shikimori response objects.
    """
    try:
        raw_body = await request.json()
        body = raw_body if isinstance(raw_body, dict) else {}
    except Exception:
        body = {}
    
    # Extract filters
    limit = int(body.get("limit", 20))
    page = int(body.get("page", 1))
    search = body.get("search", "")
    status = body.get("status", "")
    kind = body.get("kind", "")
    order = body.get("order", "ranked")
    genres = body.get("genre", "")

    season = body.get("season", "")
    is_strict = body.get("strict", False)
    
    fetch_limit = limit * 2 if is_strict else limit

    # Build filters string for GraphQL
    filters = [f"limit: {fetch_limit}", f"page: {page}"]
    if search:
        filters.append(f'search: "{search}"')
    if status:
        filters.append(f'status: "{status}"')
    if kind:
        filters.append(f'kind: "{kind}"')
    if order:
        if order == "ranked":
            filters.append('order: ranked')
        elif order == "popularity":
            filters.append('order: popularity')
        elif order == "aired_on":
            filters.append('order: aired_on')
    if genres:
        filters.append(f'genre: "{genres}"')
    if season:
        filters.append(f'season: "{season}"')
        
    filters_str = ", ".join(filters)

    gql_query = f"""
    query {{
      animes({filters_str}) {{
        id
        name
        russian
        score
        poster {{ originalUrl }}
        episodes
        episodesAired
        status
        kind
        airedOn {{ year }}
      }}
    }}
    """
    
    try:
        shiki_res, active_domain = await fetch_shikimori_graphql(gql_query)
            
        if not shiki_res:
            return {"error": "Shikimori domains failed to respond"}
            
        shiki_data = shiki_res.json()
        if not isinstance(shiki_data, dict) or "data" not in shiki_data or not isinstance(shiki_data["data"], dict) or "animes" not in shiki_data["data"]:
            return []

        animes = shiki_data["data"]["animes"]
        if not isinstance(animes, list):
            return []
        
        # Apply strict filtering (no Kodik checks, just Shikimori episode data)
        filtered_animes = []
        for item in animes:
            if not isinstance(item, dict):
                continue

            if is_strict:
                # If ongoing, must have > 0 aired episodes
                if status == "ongoing" and int(item.get("episodesAired") or 0) == 0:
                    continue
            
            # Fix relative poster URLs from Shikimori GraphQL
            poster = item.get("poster")
            if isinstance(poster, dict) and poster.get("originalUrl"):
                p_url = poster["originalUrl"]
                if isinstance(p_url, str) and p_url.startswith("/"):
                    poster["originalUrl"] = f"https://{active_domain}{p_url}"

            filtered_animes.append(item)
            
        return filtered_animes[:limit] if is_strict else filtered_animes  # type: ignore

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Shikimori/catalog] Error: {repr(e)}")
        return {"error": repr(e)}


@app.get("/kodik/video-links/{shikimori_id}")
async def kodik_video_links(shikimori_id: int):
    """
    Returns direct video links (HLS or MP4) for the given Shikimori ID.
    Uses 'with_link=true' to get raw file URLs.
    """
    try:
        token = await get_kodik_token()
        r = await kodik_client.get("https://kodikapi.com/search", params={
            "token": token,
            "shikimori_id": shikimori_id,
            "with_link": "true",
            "with_episodes": "true"
        })
        
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}"}
            
        data = r.json()
        results = data.get("results", [])
        if not results:
            return {"found": False, "error": "No results for this ID"}
            
        all_sources = []
        for res in results:
            trans = res.get("translation", {})
            trans_title = trans.get("title", "Unknown")
            trans_id = trans.get("id")
            
            # Simple movie links
            movie_links = res.get("links", {})
            movie_hls = res.get("hls")
            
            # Serial seasons/episodes
            seasons_data = []
            for s in res.get("seasons", []):
                s_num = s.get("season_number")
                eps_data = []
                for e in s.get("episodes", []):
                    e_num = e.get("episode_number")
                    eps_data.append({
                        "episode": e_num,
                        "links": e.get("links", {}),
                        "hls": e.get("hls")
                    })
                seasons_data.append({
                    "season": s_num,
                    "episodes": eps_data
                })
                
            all_sources.append({
                "translation_title": trans_title,
                "translation_id": trans_id,
                "links": movie_links,
                "hls": movie_hls,
                "seasons": seasons_data
            })
            
        return {"found": True, "sources": all_sources}
    except Exception as e:
        print(f"[Kodik/video-links] Error for '{shikimori_id}': {e}")
        return {"found": False, "error": str(e)}

@app.get("/kodik/video-links/{shikimori_id}")
async def kodik_video_links_route(shikimori_id: int):
    return await kodik_video_links(shikimori_id)


@app.get("/anilibria/video-links/{shikimori_id}")
async def anilibria_video_links_route(shikimori_id: int):
    # This now returns everything (AniLibria + Kodik) for the custom player
    return await all_video_links(shikimori_id)

@app.get("/video/all-links/{shikimori_id}")
async def all_video_links(shikimori_id: int):
    """
    Unified endpoint for direct video links from AniLibria and Kodik.
    """
    all_sources = []
    
    # 1. Fetch AniLibria links
    libria_data = await anilibria_video_links(shikimori_id)
    if isinstance(libria_data, dict) and libria_data.get("found"):
        all_sources.extend(libria_data.get("sources", []))
        
    # 2. Fetch Kodik links
    kodik_data = await kodik_video_links(shikimori_id)
    if isinstance(kodik_data, dict) and kodik_data.get("found"):
        all_sources.extend(kodik_data.get("sources", []))
        
    return {
        "found": len(all_sources) > 0,
        "sources": all_sources
    }


async def anilibria_video_links(shikimori_id: int):
    """
    Fetches direct video links from AniLibria API v1.
    1. Gets title from Shikimori.
    2. Searches AniLibria by title.
    3. Fetches full release info with episodes/HLS links.
    """
    try:
        # 1. Fetch metadata from Shikimori to get titles, year and kind
        gql_query = f"""
        query {{
          animes(ids: "{shikimori_id}", limit: 1) {{
            name
            russian
            airedOn {{ year }}
            kind
          }}
        }}
        """
        shiki_res, active_domain = await fetch_shikimori_graphql(gql_query)
        
        anime_title = None
        anime_russian = None
        shiki_year = None
        shiki_kind = None
        
        if shiki_res:
            res_json = shiki_res.json()
            animes = res_json.get("data", {}).get("animes", [])
            if animes:
                anime_title = animes[0].get("name")
                anime_russian = animes[0].get("russian")
                shiki_year = animes[0].get("airedOn", {}).get("year")
                shiki_kind = animes[0].get("kind")
        
        if not anime_title:
            return {"found": False, "error": "Shikimori title not found"}

        # 2. Search AniLibria
        # Try English title first, then Russian
        best_release = None
        for q in [anime_title, anime_russian]:
            if not q: continue
            libria_search = await http_client.get(
                "https://aniliberty.top/api/v1/anime/catalog/releases",
                params={"f[search]": q},
                headers={"User-Agent": "NekoStream/2.0"}
            )
            if libria_search.status_code == 200:
                results = libria_search.json().get("data", [])
                for rel in results:
                    # Match Year (if available)
                    rel_year = rel.get("year")
                    if shiki_year is not None and rel_year is not None:
                        if abs(int(shiki_year) - int(rel_year)) > 1:
                            continue
                    
                    # Match Type (TV vs Movie)
                    # libria type: MOVIE, TV, OVA, ONA, SPECIAL
                    # shiki kind: tv, movie, ova, ona, special, music
                    rel_type = rel.get("type", {}).get("value", "").upper()
                    shiki_k = (shiki_kind or "").upper()
                    
                    # Basic mapping check
                    type_match = False
                    if shiki_k == "MOVIE" and rel_type == "MOVIE": type_match = True
                    elif shiki_k == "TV" and rel_type == "TV": type_match = True
                    elif shiki_k in ["OVA", "ONA", "SPECIAL"] and rel_type in ["OVA", "ONA", "SPECIAL"]: type_match = True
                    elif not shiki_k or not rel_type: type_match = True # Fallback if missing
                    
                    if type_match:
                        best_release = rel
                        break
                
                if best_release: break

        if not best_release:
            return {"found": False, "error": "No matching results on AniLibria"}

        release_id = best_release["id"]
        
        # 3. Fetch full release details
        libria_detail = await http_client.get(
            f"https://aniliberty.top/api/v1/anime/releases/{release_id}",
            headers={"User-Agent": "NekoStream/2.0"}
        )
        
        if libria_detail.status_code != 200:
            return {"found": False, "error": f"AniLibria Detail HTTP {libria_detail.status_code}"}
            
        rel = libria_detail.json()
        
        # 4. Format for NekoPlayer (NekoSource structure)
        formatted_episodes = []
        for e in rel.get("episodes", []):
            # Map quality scales to links for selection
            links = {}
            if e.get("hls_480"): links["480"] = e["hls_480"]
            if e.get("hls_720"): links["720"] = e["hls_720"]
            if e.get("hls_1080"): links["1080"] = e["hls_1080"]
            
            formatted_episodes.append({
                "episode": e.get("ordinal"),
                "links": links,
                # Duration and name are extra info
                "duration": e.get("duration"),
                "name": e.get("name")
            })
            
        # Wrap in a single season (Season 1)
        seasons = [{
            "season": 1,
            "episodes": formatted_episodes
        }]
        
        # Create a single NekoSource for AniLibria
        anilibria_source = {
            "translation_title": "AniLibria",
            "translation_id": 99999, # Dummy ID for AniLibria
            "links": {}, # Mandatory links field
            "seasons": seasons
        }
            
        torrents = []
        for t in rel.get("torrents", []):
            torrents.append({
                "label": t.get("label"),
                "quality": t.get("quality", {}).get("description"),
                "size": t.get("size"),
                "magnet": t.get("magnet"),
                "seeders": t.get("seeders")
            })

        return {
            "found": True,
            "release_id": release_id,
            "title": rel.get("name", {}).get("main"),
            "sources": [anilibria_source],
            "torrents": torrents
        }

    except Exception as e:
        print(f"[AniLibria/video-links] Error for '{shikimori_id}': {e}")
        return {"found": False, "error": str(e)}


import random
import asyncio

@app.get("/custom/popular")
async def custom_popular(limit: int = 10):
    """
    Fetches the top ~50 currently popular ongoing anime,
    and returns a random selection of `limit` items to ensure variety.
    """
    query = f"""
    query {{
      animes(limit: 50, order: popularity, status: "ongoing") {{
        id
        name
        russian
        score
        poster {{ originalUrl }}
        episodes
        episodesAired
        status
        kind
        airedOn {{ year }}
      }}
    }}
    """
    res, active_domain = await fetch_shikimori_graphql(query)
    if not res:
        return []
    
    try:
        data = res.json()
        items = data.get("data", {}).get("animes", [])
        if not items:
            return []
        
        # Pick random `limit` items from the top 50
        selected = random.sample(items, min(limit, len(items)))
        
        # Fix poster URLs
        for item in selected:
            if item and item.get("poster") and item["poster"].get("originalUrl"):
                url = item["poster"]["originalUrl"]
                if url.startswith("/"):
                    item["poster"]["originalUrl"] = f"https://{active_domain}{url}"
                    
        return selected
    except Exception as e:
        print(f"[Custom Popular] Error: {e}")
        return []

# ── Performance Optimization (Random) ─────────────────────────
_RANDOM_CACHE = {"items": [], "expiry": 0}
_RANDOM_CACHE_TTL = 1800 # 30 mins

@app.get("/custom/random")
async def custom_random(limit: int = 10):
    """
    Fetches a random selection of anime. 
    Caches 50 items and serves from them until cache expires or runs low.
    """
    global _RANDOM_CACHE
    now = datetime.datetime.now().timestamp()
    
    # If we have enough items in cache, use them
    if _RANDOM_CACHE["items"] and now < _RANDOM_CACHE["expiry"] and len(_RANDOM_CACHE["items"]) >= limit:
        selected = random.sample(_RANDOM_CACHE["items"], limit)
        # Remove selected to ensure variety on subsequent clicks
        # Note: We keep them if we want to allow repeats, but here we prefer variety.
        # Actually, let's keep them and just sample to be faster/simpler.
        return selected

    # Otherwise fetch new page
    random_page = random.randint(1, 50) 
    query = f"""
    query {{
      animes(limit: 50, page: {random_page}, order: ranked) {{
        id name russian score poster {{ originalUrl }}
        episodes episodesAired status kind airedOn {{ year }}
      }}
    }}
    """
    res, active_domain = await fetch_shikimori_graphql(query)
    if not res:
        # Fallback to old cache if exists, else return empty
        return random.sample(_RANDOM_CACHE["items"], min(limit, len(_RANDOM_CACHE["items"]))) if _RANDOM_CACHE["items"] else []
        
    try:
        data = res.json()
        items = data.get("data", {}).get("animes", [])
        if not items: return []
            
        # Fix poster URLs
        for item in items:
            if item.get("poster") and item["poster"].get("originalUrl"):
                url = item["poster"]["originalUrl"]
                if url.startswith("/"):
                    item["poster"]["originalUrl"] = f"https://{active_domain or _STICKY_DOMAIN}{url}"
        
        # Update Cache
        _RANDOM_CACHE["items"] = items
        _RANDOM_CACHE["expiry"] = now + _RANDOM_CACHE_TTL
        
        return random.sample(items, min(limit, len(items)))
    except Exception as e:
        print(f"[Custom Random] Error: {e}")
        return []

# ── Performance Optimization ──────────────────────────────────
_CALENDAR_CACHE = {"data": None, "expiry": 0}
_CALENDAR_CACHE_TTL = 3600 # 1 Hour

@app.get("/shikimori/calendar")
async def shikimori_calendar():
    """Proxy for Shikimori's calendar API with parallel fetching and caching."""
    # 1. Check Cache
    now = datetime.datetime.now().timestamp()
    if _CALENDAR_CACHE["data"] and now < _CALENDAR_CACHE["expiry"]:
        return _CALENDAR_CACHE["data"]

    for domain in SHIKIMORI_DOMAINS:
        url = f"https://{domain}/api/calendar"
        try:
            res = await http_client.get(
                url,
                headers={"User-Agent": "NekoStream/2.0"},
                timeout=httpx.Timeout(10.0)
            )
            if res.status_code != 200:
                continue
            
            print(f"[Shikimori Calendar] Success on {domain}")
            data = res.json()
            
            # 2. Extract IDs
            anime_ids = [str(item["anime"]["id"]) for item in data if item.get("anime") and item["anime"].get("id")]
            poster_map = {}
            
            # 3. Create Parallel Tasks for Poster Fetching
            tasks = []
            for i in range(0, len(anime_ids), 50):
                chunk = anime_ids[i:i+50]
                ids_str = ",".join(chunk)
                gql_query = f"""
                query {{
                  animes(ids: "{ids_str}", limit: 50) {{
                    id
                    poster {{ originalUrl }}
                  }}
                }}
                """
                tasks.append(fetch_shikimori_graphql(gql_query))

            # 4. Run Parallel Requests
            responses = await asyncio.gather(*tasks)

            # 5. Process Results
            for gql_res, active_dom in responses:
                if not gql_res: continue
                try:
                    gql_json = gql_res.json()
                    gql_items = gql_json.get("data", {}).get("animes", [])
                    for a in gql_items:
                        p = a.get("poster")
                        if p and p.get("originalUrl"):
                            url = p["originalUrl"]
                            if url.startswith("/"):
                                url = f"https://{active_dom or domain}{url}"
                            poster_map[str(a["id"])] = url
                except:
                    pass
                            
            # 6. Inject Better Posters
            for item in data:
                if item.get("anime") and item["anime"].get("id"):
                    aid = str(item["anime"]["id"])
                    if aid in poster_map:
                        item["anime"]["image"]["original"] = poster_map[aid]
                    else:
                        # Standard fix for relative URLs if mapping failed
                        orig = item["anime"].get("image", {}).get("original")
                        if orig and isinstance(orig, str) and orig.startswith("/"):
                            item["anime"]["image"]["original"] = f"https://{domain}{orig}"

            # 7. Update Cache
            _CALENDAR_CACHE["data"] = data
            _CALENDAR_CACHE["expiry"] = now + _CALENDAR_CACHE_TTL
            return data

        except Exception as e:
            print(f"[Shikimori Calendar] Failed on {domain}: {e}")
            continue

    print("[Shikimori Calendar] All fallback domains failed.")
    return []
