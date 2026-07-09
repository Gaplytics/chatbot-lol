import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

logger = logging.getLogger("gaply-scraper")

def scrape_website(base_url: str, max_depth: int = 3) -> list[dict]:
    """
    Performs a Breadth-First Search crawl of the website starting from base_url, 
    up to max_depth. Extracts the main text content from each page.
    """
    visited = set()
    queue = [(base_url, 0)]
    results = []
    
    base_domain = urlparse(base_url).netloc

    while queue:
        url, depth = queue.pop(0)
        
        if url in visited or depth > max_depth:
            continue
            
        visited.add(url)
        
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                continue
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Remove scripts, styles, and layout elements to focus on content
            for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                element.extract()
                
            text = soup.get_text(separator="\n")
            
            # Clean up excessive whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            title = soup.title.string if soup.title else url
            
            if text:
                results.append({
                    "url": url,
                    "title": title.strip(),
                    "content": text
                })
                
            # Find all internal links to queue up for next depth
            if depth < max_depth:
                for link in soup.find_all('a', href=True):
                    next_url = urljoin(base_url, link['href'])
                    if urlparse(next_url).netloc == base_domain:
                        queue.append((next_url, depth + 1))
                        
        except Exception as e:
            logger.warning(f"Failed to scrape {url}: {e}")

    logger.info(f"Scraped {len(results)} pages from {base_url}")
    return results
