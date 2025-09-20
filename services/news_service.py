"""
SerpAPI service for fetching news articles from Google News.
"""

import httpx
from typing import List, Dict, Any, Optional
import logging
from core.config import settings
from datetime import datetime, timedelta
import re


logger = logging.getLogger(__name__)

class SerpAPIService:
    """Service for interacting with the SerpAPI Google News."""
    
    def __init__(self):
        self.base_url = settings.SERP_BASE_URL
        self.api_key = settings.SERP_API_KEY
        self.timeout = 30.0
        
    
    async def get_latest_news(
        self,
        country: Optional[str] = None,
        category: Optional[str] = None,
        language: str = "en",
        size: int = 10,
        q: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch latest news from SerpAPI Google News.
        
        Args:
            country: Country code (e.g., 'us', 'es', 'au')
            category: News category (e.g., 'sports', 'business', 'health', 'entertainment', 'tech', 'politics')
            language: Language code (default: 'en')
            size: Number of articles to return (1-50, default: 10)
            q: Search query for specific keywords
            
        Returns:
            List of news articles
        """
        if not self.api_key:
            logger.error("SerpAPI API key not configured")
            raise ValueError("SerpAPI API key not configured")
        
        # Use the provided query directly
        if q:
            search_query = q
        else:
            # Build search query based on parameters if no direct query provided
            query_parts = []
            
            if country:
                country_name = self._map_country_to_name(country)
                if country_name:
                    query_parts.append(country_name)
            
            if category:
                category_name = self._map_category_to_name(category)
                if category_name:
                    query_parts.append(category_name)
            
            # Default to general news if no specific query
            if not query_parts:
                if country:
                    country_name = self._map_country_to_name(country)
                    query_parts.append(f"{country_name} news" if country_name else "news")
                else:
                    query_parts.append("news")
            
            search_query = " ".join(query_parts)
        
        # Build query parameters
        params = {
            "engine": "google_news_light",
            "api_key": self.api_key,
            "q": f"{search_query}",
            "num": 100,  # Cap at 100 as per API limits
            "safe": "active"
        }
        
        # Set language and domain based on country
        if country == "es":
            params["hl"] = "es"
            params["lr"] = "lang_es"
            params["google_domain"] = "google.es"
        else:
            params["hl"] = "en"
            params["lr"] = "lang_en"
            params["google_domain"] = "google.com"
        
        logger.info(f"🔍 SerpAPI Request: {self.base_url}")
        logger.info(f"📋 Request params: {params}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.base_url, params=params)
                
                logger.info(f"📡 Response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"📄 Response data keys: {list(data.keys())}")
                    
                    if data.get("search_metadata", {}).get("status") == "Success":
                        articles = data.get("news_results", [])
                        logger.info(f"📰 Parsed {len(articles)} articles from API")
                        
                        # Convert articles to our expected format
                        converted_articles = [self._convert_article_format(article) for article in articles]
                        
                        # Sort articles by date (most recent first)
                        sorted_articles = self._sort_by_date(converted_articles)
                        logger.info(f"✅ Converted {len(converted_articles)} articles, sorted by date")
                        
                        limited_articles = sorted_articles[:size]
                        logger.info(f"📊 Returning {len(limited_articles)} latest articles (size={size})")
                        
                        return limited_articles
                    else:
                        logger.warning(f"API returned status: {data.get('search_metadata', {}).get('status')}")
                        return []
                else:
                    logger.error(f"SerpAPI error: {response.status_code} - {response.text}")
                    return []
                    
        except httpx.TimeoutException:
            logger.error("SerpAPI request timed out")
            return []
        except httpx.RequestError as e:
            logger.error(f"SerpAPI request error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in SerpAPI: {e}")
            return []
    
    def _sort_by_date(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort articles by date, with most recent articles first.
        
        Args:
            articles: List of articles with 'published_at' field
            
        Returns:
            List of articles sorted by date (most recent first)
        """
        def get_sort_key(article):
            published_at = article.get('published_at', '')
            if not published_at:
                # Articles without dates go to the end
                return datetime.min
            
            try:
                article_date = self._parse_date_string(published_at)
                if article_date:
                    return article_date
                else:
                    return datetime.min
            except Exception:
                # If we can't parse the date, put it at the end
                return datetime.min
        
        # Sort by date (most recent first)
        sorted_articles = sorted(articles, key=get_sort_key, reverse=True)
        logger.info(f"📅 Sorted {len(articles)} articles by date (most recent first)")
        
        return sorted_articles
    
    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """
        Parse various date string formats from SerpAPI.
        
        Args:
            date_str: Date string in various formats
            
        Returns:
            datetime object or None if parsing fails
        """
        if not date_str:
            return None
            
        # Common patterns from SerpAPI
        patterns = [
            r'(\d+)\s+(minute|hour|day|week|month|year)s?\s+ago',
            r'(\d+)\s+(minute|hour|day|week|month|year)\s+ago',
            r'(\d+)\s+(min|hr|d|w|mo|y)\s+ago',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, date_str.lower())
            if match:
                try:
                    value = int(match.group(1))
                    unit = match.group(2)
                    
                    now = datetime.now()
                    
                    if unit in ['minute', 'min']:
                        return now - timedelta(minutes=value)
                    elif unit in ['hour', 'hr']:
                        return now - timedelta(hours=value)
                    elif unit in ['day', 'd']:
                        return now - timedelta(days=value)
                    elif unit in ['week', 'w']:
                        return now - timedelta(weeks=value)
                    elif unit in ['month', 'mo']:
                        return now - timedelta(days=value * 30)  # Approximate
                    elif unit in ['year', 'y']:
                        return now - timedelta(days=value * 365)  # Approximate
                except (ValueError, TypeError):
                    continue
        
        # If no pattern matches, try to parse as a regular date
        try:
            # Try common date formats
            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%B %d, %Y']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
            
        return None
    
    def _convert_article_format(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert SerpAPI article format to our expected format.
        
        Args:
            article: Article from SerpAPI
            
        Returns:
            Article in our expected format
        """
        return {
            "title": article.get("title", ""),
            "description": article.get("snippet", ""),
            "source": article.get("source", ""),
            "published_at": article.get("date", ""),
            "link": article.get("link", ""),
            "thumbnail": article.get("thumbnail", ""),
            "position": article.get("position", 0)
        }
    
    def _map_category_to_name(self, category: str) -> str:
        """
        Map our internal categories to search-friendly names.
        
        Args:
            category: Internal category name
            
        Returns:
            Search-friendly category name
        """
        category_mapping = {
            "general": "news",
            "sports": "sports", 
            "business": "business",
            "health": "health",
            "entertainment": "entertainment",
            "tech": "technology",
            "politics": "politics",
            "science": "science",
            "food": "food",
            "travel": "travel"
        }
        
        return category_mapping.get(category.lower(), "news")
    
    def _map_country_to_name(self, country: str) -> str:
        """
        Map country codes to country names for search.
        
        Args:
            country: Country code (e.g., 'us', 'es')
            
        Returns:
            Country name for search
        """
        country_mapping = {
            "us": "United States",
            "es": "Spain", 
            "uk": "United Kingdom",
            "au": "Australia",
            "ca": "Canada",
            "fr": "France",
            "de": "Germany",
            "it": "Italy",
            "jp": "Japan",
            "in": "India"
        }
        
        return country_mapping.get(country.lower(), country)
    

serpapi = SerpAPIService()