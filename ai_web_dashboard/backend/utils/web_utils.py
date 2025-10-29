import httpx
from bs4 import BeautifulSoup, Comment
import logging
import os
import json
import asyncio

from .. import config
from .llm_utils import call_llm

logger = logging.getLogger(__name__)

async def search_google(query: str) -> list:
    """
    Performs a Google search using the Serper.dev API.
    Requires SERPER_API_KEY in config.py.
    """
    if not config.SERPER_API_KEY:
        logger.error("[Web Util] Serper.dev API Key not set. Cannot perform search.")
        return []

    url = "https://serper.dev/search"
    headers = {
        'X-API-KEY': config.SERPER_API_KEY,
        'Content-Type': 'application/json'
    }
    payload = json.dumps({"q": query})

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, headers=headers, content=payload)
            response.raise_for_status()
            data = response.json()
            
            results = []
            if 'organic' in data:
                for item in data['organic']:
                    results.append({
                        "title": item.get('title'),
                        "link": item.get('link'),
                        "snippet": item.get('snippet')
                    })
            logger.info(f"[Web Util] Serper.dev search for '{query}' returned {len(results)} results.")
            return results
    except httpx.RequestError as e:
        logger.error(f"[Web Util] HTTP request failed for Serper.dev API: {e}")
        return []
    except Exception as e:
        logger.error(f"[Web Util] An unexpected error occurred during Serper.dev search: {e}")
        return []

def _heuristic_content_extraction(soup: BeautifulSoup) -> str:
    """
    Fallback function to extract content using heuristics.
    """
    # Try common main content tags
    for tag in ["article", "main", "[role='main']"]:
        main_content = soup.select_one(tag)
        if main_content:
            return main_content.get_text(separator=' ', strip=True)

    # Fallback to finding the element with the most text
    max_text_len = 0
    best_element = None
    for element in soup.find_all(['div', 'p', 'section']):
        text = element.get_text(separator=' ', strip=True)
        if len(text) > max_text_len:
            max_text_len = len(text)
            best_element = element
    
    if best_element:
        return best_element.get_text(separator=' ', strip=True)
        
    return soup.get_text(separator=' ', strip=True)


async def extract_content_from_url(url: str) -> str:
    """
    Extracts the main readable content from a given URL using a hybrid AI and heuristic approach.
    """
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')

            # 1. Heuristic Pre-cleaning
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form']):
                element.decompose()
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()
            
            # Remove common non-content divs
            for div in soup.find_all("div", {'id': ['sidebar', 'related-posts', 'comments', 'ad-container']}):
                div.decompose()
            for div in soup.find_all("div", {'class': ['sidebar', 'related', 'ads', 'social-media-buttons']}):
                div.decompose()

            cleaned_html = soup.body.prettify() if soup.body else soup.prettify()
            
            # Limit the size of the HTML to avoid excessive token usage
            if len(cleaned_html) > 20000:
                 logger.warning(f"[Web Util] Cleaned HTML for {url} is very large ({len(cleaned_html)} chars). Truncating for AI.")
                 cleaned_html = cleaned_html[:20000]

            # 2. AI-powered Extraction
            prompt_message = {
                "role": "user",
                "content": f"From the following HTML snippet, please extract only the main article content. Return only the clean text, without any HTML tags or explanations.\n\nHTML:\n```html\n{cleaned_html}\n```"
            }
            
            success, extracted_text = await asyncio.to_thread(
                call_llm,
                messages=[prompt_message],
                model=config.WEB_EXTRACTION_MODEL,
                max_tokens=2000,
                temperature=0.1
            )

            if success and extracted_text:
                logger.info(f"[Web Util] Successfully extracted content from {url} using AI.")
                return extracted_text.strip()
            else:
                logger.warning(f"[Web Util] AI extraction failed for {url}. Falling back to heuristic method. Reason: {extracted_text}")
                # 3. Fallback to Heuristics
                return _heuristic_content_extraction(soup)

    except httpx.RequestError as e:
        logger.error(f"[Web Util] HTTP request failed for {url}: {e}")
        return f"Error: Could not fetch content from the URL. {e}"
    except Exception as e:
        logger.error(f"[Web Util] An unexpected error occurred during content extraction from {url}: {e}")
        return f"Error: An unexpected error occurred. {e}"