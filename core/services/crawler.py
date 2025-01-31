import logging
from typing import List, Dict, Optional
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential
from backend.core.exceptions import CrawlerError
from backend.core.utils.redis import get_redis
from backend.core.config import settings

logger = logging.getLogger(__name__)

class WebCrawler:
    """Web crawler for fallback scraping when APIs are unavailable"""
    
    def __init__(self):
        self.redis = get_redis()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.timeout = httpx.Timeout(10.0, connect=5.0)
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def scrape_amazon(self, product_name: str) -> List[Dict]:
        """Scrape Amazon for product deals"""
        try:
            url = f"https://www.amazon.com/s?k={product_name.replace(' ', '+')}"
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, timeout=self.timeout)
                response.raise_for_status()
                
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            for item in soup.select('div[data-component-type="s-search-result"]'):
                try:
                    title = item.select_one('h2 a span').text.strip()
                    price = item.select_one('.a-price .a-offscreen')
                    price = float(price.text.replace('$', '')) if price else None
                    url = 'https://www.amazon.com' + item.select_one('h2 a')['href']
                    
                    if price:
                        results.append({
                            'product_name': title,
                            'price': price,
                            'url': url,
                            'source': 'Amazon',
                            'scraped_at': datetime.utcnow()
                        })
                except Exception as e:
                    logger.debug(f"Error parsing Amazon item: {str(e)}")
                    continue
                    
            return results
            
        except Exception as e:
            logger.error(f"Failed to scrape Amazon: {str(e)}")
            raise CrawlerError(f"Amazon scraping failed: {str(e)}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))        
    async def scrape_walmart(self, product_name: str) -> List[Dict]:
        """Scrape Walmart for product deals"""
        try:
            url = f"https://www.walmart.com/search?q={product_name.replace(' ', '+')}"
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, timeout=self.timeout)
                response.raise_for_status()
                
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            for item in soup.select('div[data-item-id]'):
                try:
                    title = item.select_one('.f6 a')['title']
                    price = item.select_one('[data-automation-id="product-price"]')
                    price = float(price.text.replace('$', '')) if price else None
                    url = 'https://www.walmart.com' + item.select_one('a')['href']
                    
                    if price:
                        results.append({
                            'product_name': title,
                            'price': price,
                            'url': url,
                            'source': 'Walmart',
                            'scraped_at': datetime.utcnow()
                        })
                except Exception as e:
                    logger.debug(f"Error parsing Walmart item: {str(e)}")
                    continue
                    
            return results
            
        except Exception as e:
            logger.error(f"Failed to scrape Walmart: {str(e)}")
            raise CrawlerError(f"Walmart scraping failed: {str(e)}")

    async def scrape_fallback(self, product_name: str) -> List[Dict]:
        """Fallback scraping when APIs fail"""
        try:
            # Try Amazon first
            results = await self.scrape_amazon(product_name)
            if results:
                return results
                
            # Fallback to Walmart
            results = await self.scrape_walmart(product_name)
            return results
            
        except Exception as e:
            logger.error(f"Fallback scraping failed: {str(e)}")
            raise CrawlerError(f"Fallback scraping failed for {product_name}")
