from operator import itemgetter

import re
from fastapi import FastAPI, Query, Request
from starlette.middleware.base import BaseHTTPMiddleware
from typing import List, Optional
from pydantic import BaseModel
from rapidfuzz import fuzz

from scraper import Search

app = FastAPI()


class NormalizePathMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Collapse multiple slashes into one (e.g. //search -> /search)
        path = request.scope.get('path', '')
        normalized = re.sub(r'/{2,}', '/', path)
        if normalized != path:
            request.scope['path'] = normalized
        return await call_next(request)


app.add_middleware(NormalizePathMiddleware)


class AudioBookResponse(BaseModel):
    url: Optional[str]
    title: Optional[str]
    subtitle: Optional[str] = None
    author: Optional[str]
    authors: Optional[list[str]]
    narrators: Optional[list[str]]
    narrator: Optional[str]
    tags: Optional[list[str]]  # Ensure this matches OpenAPI spec
    publisher: str = "Big Finish"
    cover: Optional[str]
    series: Optional[list[object]]
    language: str = "Eng"
    duration: Optional[int]
    isbn: Optional[str]
    description: Optional[str]
    publishedYear: Optional[str]
    publishedDate: Optional[str]
    abridged: bool = False
    explicit: bool = False

@app.get("/search/")
async def search_audiobooks(query: str = Query(..., description="Title to search for"), mediaType: Optional[str] = Query(None, description="Optional media type filter, e.g. 'book'")):
    # Get search results
    # If mediaType provided, pass a token appended to the query so Search can filter without changing APIs
    search_query = query
    if mediaType:
        search_query = f"{query}||{mediaType}"
    top_matches = Search().search(search_query)

    # Calculate similarity scores and sort results
    scored_matches = []
    for match in top_matches:
        # Defensive: some parsed results may be missing a title
        title_text = (match.get('title') if isinstance(match, dict) else None) or ''
        # Use token set ratio for more forgiving matching on multi-word titles
        try:
            score = fuzz.token_set_ratio(query, title_text)
            if not score and match.get('about'):
                score = fuzz.token_set_ratio(query, match.get('about')[:200])
        except Exception:
            score = 0
        scored_matches.append((score, match))

    # Sort by score in descending order
    scored_matches.sort(reverse=True, key=itemgetter(0))

    # Extract just the matches without scores
    sorted_matches = [match for score, match in scored_matches]

    response_data = []
    for row in sorted_matches:
        duration_minutes = None
        if row['duration']:
            try:
                duration_minutes = int(row['duration'])
            except ValueError:
                pass
        # Build description by concatenating about and background if present
        description = None
        if row.get('about'):
            description = row.get('about')
        if row.get('background'):
            if description:
                description = f"{description}\n\n{row.get('background')}"
            else:
                description = row.get('background')

        series_obj = None
        if row.get('series'):
            series_obj = [{'series': row['series'], 'sequence': row.get('series_tag')}]

        book_data = AudioBookResponse(
            url=row.get('url'),
            title=row.get('title'),
            subtitle=None,
            authors=row.get('written_by').split(', ') if row.get('written_by') else None,
            author=row.get('written_by'),
            narrators=row.get('narrated_by').split(', ') if row.get('narrated_by') else None,
            narrator=row.get('narrated_by'),
            tags=row.get('characters').split(', ') if row.get('characters') else None,
            cover=row.get('cover_url'),
            series=series_obj,
            duration=duration_minutes if duration_minutes else None,
            isbn=row.get('isbn'),
            description=description,
            publishedYear=(row.get('release_date').split('-')[0] if row.get('release_date') else None),
            publishedDate=row.get('release_date') if row.get('release_date') else None,
        )
        response_data.append(book_data)

    return {'matches': response_data}



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7777)
