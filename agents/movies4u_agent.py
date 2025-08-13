#!/usr/bin/env python3
"""
Movies4U Agent - Movie search and download link extraction from movies4u.fm
Handles human verification and dynamic content loading
"""

import requests
import json
import time
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote, unquote
from fake_useragent import UserAgent
import logging
from typing import Dict, List, Optional, Any
try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    uc = None
    By = None
    WebDriverWait = None
    expected_conditions = None
    SELENIUM_AVAILABLE = False
try:
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
except ImportError:
    TimeoutException = Exception
    NoSuchElementException = Exception

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Movies4UAgent:
    def __init__(self):
        self.base_url = "https://movies4u.fm"
        self.search_url = "https://movies4u.fm/?s={}&ct_post_type=post%3Apage"
        
        self.session = requests.Session()
        self.ua = UserAgent()
        self.setup_session()
        
        # Selenium driver for handling verification
        self.driver = None
        
    def setup_session(self):
        """Setup session with headers and cookies"""
        headers = {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
        self.session.headers.update(headers)
        
        # Set timeout
        self.session.timeout = 30
        
    def init_selenium_driver(self):
        """Initialize Selenium driver for handling verification"""
        if self.driver:
            return self.driver
            
        try:
            # Check if Selenium is disabled (for deployment environments)
            import os
            if os.environ.get('DISABLE_SELENIUM', '').lower() == 'true':
                logger.info("Selenium disabled via environment variable")
                return None
                
            options = uc.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--disable-web-security")
            options.add_argument("--disable-features=VizDisplayCompositor")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument(f"--user-agent={self.ua.random}")
            
            self.driver = uc.Chrome(options=options)
            self.driver.set_page_load_timeout(30)
            logger.info("Selenium driver initialized for Movies4U")
            return self.driver
            
        except Exception as e:
            logger.error(f"Failed to initialize Selenium driver: {str(e)}")
            return None
    
    def handle_verification(self, url: str, max_retries: int = 3) -> Optional[str]:
        """Handle human verification using Selenium"""
        for attempt in range(max_retries):
            try:
                driver = self.init_selenium_driver()
                if not driver:
                    return None
                
                logger.info(f"Attempting to load {url} (attempt {attempt + 1})")
                driver.get(url)
                
                # Wait for page to load
                time.sleep(5)
                
                # Check for verification elements
                verification_indicators = [
                    "human verification",
                    "verify you are human",
                    "cloudflare",
                    "checking your browser",
                    "please wait",
                    "security check"
                ]
                
                page_text = driver.page_source.lower()
                has_verification = any(indicator in page_text for indicator in verification_indicators)
                
                if has_verification:
                    logger.info(f"Human verification detected, waiting...")
                    # Wait for verification to complete (very short timeout)
                    WebDriverWait(driver, 8).until(
                        lambda d: not any(indicator in d.page_source.lower() 
                                        for indicator in verification_indicators)
                    )
                    time.sleep(5)  # Additional wait
                
                # Check if we have valid content
                if "movies4u" in driver.page_source.lower() or "search" in driver.page_source.lower():
                    logger.info("Successfully bypassed verification")
                    return driver.page_source
                    
            except TimeoutException:
                logger.warning(f"Timeout on attempt {attempt + 1}")
                continue
            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}: {str(e)}")
                continue
        
        logger.error("Failed to bypass verification after all attempts")
        return None
    
    def search_movies(self, movie_name: str, max_results: int = 50) -> Dict[str, Any]:
        """Search for movies on Movies4U with optimized verification handling"""
        try:
            logger.info(f"Searching Movies4U for: {movie_name}")
            
            # Prepare search URL
            search_query = quote(movie_name)
            search_url = self.search_url.format(search_query)
            
            logger.info(f"Search URL: {search_url}")
            
            # Try with Selenium first (for verification handling)
            page_content = self.handle_verification(search_url)
            
            if not page_content:
                # Fallback to requests
                try:
                    response = self.session.get(search_url)
                    response.raise_for_status()
                    page_content = response.text
                except Exception as e:
                    logger.error(f"Requests fallback failed: {str(e)}")
                    return {'movies': [], 'total_found': 0}
            
            # Parse search results
            movies = self.parse_search_results(page_content, movie_name)
            
            # Limit results
            if len(movies) > max_results:
                movies = movies[:max_results]
            
            logger.info(f"Movies4U returned {len(movies)} movies")
            
            return {
                'movies': movies,
                'total_found': len(movies),
                'source': 'Movies4U'
            }
            
        except Exception as e:
            logger.error(f"Movies4U search failed: {str(e)}")
            return {'movies': [], 'total_found': 0}
    
    def parse_search_results(self, html_content: str, search_term: str) -> List[Dict[str, Any]]:
        """Parse search results from HTML content"""
        movies = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for common movie result patterns
            movie_selectors = [
                'article.post',
                '.post-item',
                '.movie-item',
                '.search-result',
                'article',
                '.entry',
                '.post'
            ]
            
            movie_elements = []
            for selector in movie_selectors:
                elements = soup.select(selector)
                if elements:
                    movie_elements = elements
                    logger.info(f"Found {len(elements)} results using selector: {selector}")
                    break
            
            if not movie_elements:
                logger.warning("No movie elements found with standard selectors")
                return movies
            
            for element in movie_elements:
                try:
                    movie_data = self.extract_movie_data(element, search_term)
                    if movie_data:
                        movies.append(movie_data)
                except Exception as e:
                    logger.debug(f"Error extracting movie data: {str(e)}")
                    continue
            
            # Remove duplicates based on title and URL
            seen = set()
            unique_movies = []
            for movie in movies:
                key = (movie.get('title', '').lower(), movie.get('url', ''))
                if key not in seen:
                    seen.add(key)
                    unique_movies.append(movie)
            
            return unique_movies
            
        except Exception as e:
            logger.error(f"Error parsing search results: {str(e)}")
            return movies
    
    def extract_movie_data(self, element, search_term: str) -> Optional[Dict[str, Any]]:
        """Extract movie data from a single result element"""
        try:
            # Extract title
            title_selectors = [
                'h2 a', 'h3 a', 'h1 a',
                '.entry-title a', '.post-title a',
                '.title a', 'a.title',
                'h2', 'h3', 'h1'
            ]
            
            title = None
            url = None
            
            for selector in title_selectors:
                title_elem = element.select_one(selector)
                if title_elem:
                    if title_elem.name == 'a':
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href')
                    else:
                        title = title_elem.get_text(strip=True)
                        # Look for URL in parent or nearby elements
                        link_elem = title_elem.find_parent('a') or title_elem.find('a')
                        if link_elem:
                            url = link_elem.get('href')
                    break
            
            if not title:
                return None
            
            # Make URL absolute
            if url and not url.startswith('http'):
                url = urljoin(self.base_url, url)
            
            # Extract additional metadata
            year = self.extract_year(element)
            quality = self.extract_quality(element)
            language = self.extract_language(element)
            description = self.extract_description(element)
            
            # Check relevance
            if not self.is_relevant_result(title, search_term):
                return None
            
            movie_data = {
                'title': title,
                'url': url or '',
                'year': year,
                'quality': quality,
                'language': language,
                'description': description,
                'source': 'Movies4U',
                'source_url': self.base_url
            }
            
            return movie_data
            
        except Exception as e:
            logger.debug(f"Error extracting movie data: {str(e)}")
            return None
    
    def extract_year(self, element) -> Optional[str]:
        """Extract year from element"""
        text = element.get_text()
        year_match = re.search(r'\b(19|20)\d{2}\b', text)
        return year_match.group() if year_match else None
    
    def extract_quality(self, element) -> Optional[str]:
        """Extract quality from element"""
        text = element.get_text().lower()
        qualities = ['4k', '2160p', '1080p', '720p', '480p', 'hd', 'cam', 'dvdrip', 'bluray', 'webrip']
        for quality in qualities:
            if quality in text:
                return quality.upper()
        return None
    
    def extract_language(self, element) -> Optional[str]:
        """Extract language from element"""
        text = element.get_text().lower()
        languages = {
            'hindi': 'Hindi', 'english': 'English', 'tamil': 'Tamil',
            'telugu': 'Telugu', 'punjabi': 'Punjabi', 'bengali': 'Bengali',
            'marathi': 'Marathi', 'gujarati': 'Gujarati'
        }
        for lang_key, lang_value in languages.items():
            if lang_key in text:
                return lang_value
        return None
    
    def extract_description(self, element) -> Optional[str]:
        """Extract description from element"""
        desc_selectors = ['.excerpt', '.summary', '.description', '.content', 'p']
        for selector in desc_selectors:
            desc_elem = element.select_one(selector)
            if desc_elem:
                desc = desc_elem.get_text(strip=True)
                if len(desc) > 50:  # Only return substantial descriptions
                    return desc[:200] + '...' if len(desc) > 200 else desc
        return None
    
    def is_relevant_result(self, title: str, search_term: str) -> bool:
        """Check if the result is relevant to the search term"""
        title_lower = title.lower()
        search_lower = search_term.lower()
        
        # Direct match
        if search_lower in title_lower:
            return True
        
        # Word-based matching
        search_words = search_lower.split()
        title_words = title_lower.split()
        
        # Check if most search words are in title
        matches = sum(1 for word in search_words if any(word in title_word for title_word in title_words))
        return matches >= len(search_words) * 0.6  # 60% match threshold
    
    def extract_download_links(self, movie_url: str) -> Dict[str, Any]:
        """Extract download links from movie page"""
        try:
            logger.info(f"Extracting download links from: {movie_url}")
            
            # Use Selenium for dynamic content
            page_content = self.handle_verification(movie_url)
            
            if not page_content:
                return {'links': [], 'error': 'Failed to load movie page'}
            
            soup = BeautifulSoup(page_content, 'html.parser')
            
            # Look for download links
            download_links = []
            
            # Common download link patterns
            link_selectors = [
                'a[href*="download"]',
                'a[href*="drive.google.com"]',
                'a[href*="mega.nz"]',
                'a[href*="mediafire"]',
                'a[href*="dropbox"]',
                '.download-link a',
                '.download-button a',
                '.btn-download'
            ]
            
            for selector in link_selectors:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href')
                    if href and self.is_valid_download_link(href):
                        download_links.append({
                            'url': href,
                            'text': link.get_text(strip=True),
                            'quality': self.extract_quality_from_link(link),
                            'size': self.extract_size_from_link(link)
                        })
            
            return {
                'links': download_links,
                'total_links': len(download_links),
                'source': 'Movies4U'
            }
            
        except Exception as e:
            logger.error(f"Error extracting download links: {str(e)}")
            return {'links': [], 'error': str(e)}
    
    def is_valid_download_link(self, url: str) -> bool:
        """Check if URL is a valid download link"""
        if not url:
            return False
        
        valid_domains = [
            'drive.google.com', 'mega.nz', 'mediafire.com',
            'dropbox.com', '1fichier.com', 'rapidgator.net',
            'uploadrar.com', 'nitroflare.com', 'uptobox.com'
        ]
        
        return any(domain in url.lower() for domain in valid_domains)
    
    def extract_quality_from_link(self, link_element) -> Optional[str]:
        """Extract quality information from download link"""
        text = link_element.get_text().lower()
        qualities = ['4k', '2160p', '1080p', '720p', '480p']
        for quality in qualities:
            if quality in text:
                return quality.upper()
        return None
    
    def extract_size_from_link(self, link_element) -> Optional[str]:
        """Extract file size from download link"""
        text = link_element.get_text()
        size_match = re.search(r'(\d+(?:\.\d+)?)\s*(GB|MB|KB)', text, re.IGNORECASE)
        return size_match.group() if size_match else None
    
    def cleanup(self):
        """Cleanup resources"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                logger.info("Selenium driver cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up driver: {str(e)}")
    
    def __del__(self):
        """Destructor to cleanup resources"""
        self.cleanup()

def main():
    """Test the Movies4U agent"""
    agent = Movies4UAgent()
    
    try:
        # Test search
        print("Testing Movies4U Agent...")
        results = agent.search_movies("RRR", max_results=5)
        
        print(f"\nFound {results['total_found']} movies:")
        for i, movie in enumerate(results['movies'], 1):
            print(f"{i}. {movie['title']}")
            print(f"   URL: {movie['url']}")
            print(f"   Year: {movie.get('year', 'N/A')}")
            print(f"   Quality: {movie.get('quality', 'N/A')}")
            print(f"   Language: {movie.get('language', 'N/A')}")
            print()
        
        # Test download link extraction if we have results
        if results['movies']:
            print("Testing download link extraction...")
            first_movie = results['movies'][0]
            links = agent.extract_download_links(first_movie['url'])
            print(f"Found {links['total_links']} download links")
            
    except Exception as e:
        print(f"Error testing agent: {str(e)}")
    finally:
        agent.cleanup()

if __name__ == "__main__":
    main()