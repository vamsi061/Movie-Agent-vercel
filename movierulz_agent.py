#!/usr/bin/env python3
"""
MovieRulz Agent - Source 3 for Movie Agent
Handles movie search and download link extraction from movierulz sites
Includes Google search functionality to find current working domain
"""

import requests
import json
import time
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote
from fake_useragent import UserAgent
import logging
from typing import Dict, List, Optional, Any
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MovieRulzAgent:
    def __init__(self):
        self.base_url = "https://www.5movierulz.sarl"  # Default URL
        
        # Override with known working domains (test these first)
        self.priority_domains = [
            "https://www.5movierulz.sarl",
            "https://5movierulz.sarl",
            "https://www.4movierulz.com", 
            "https://4movierulz.com",
            "https://www.3movierulz.com",
            "https://3movierulz.com"
        ]
        self.current_working_url = None
        self.session = requests.Session()
        self.ua = UserAgent()
        self.setup_session()
        
        # Known working MovieRulz domains (prioritized list)
        self.known_working_domains = [
            "https://www.5movierulz.sarl",
            "https://5movierulz.sarl", 
            "https://www.4movierulz.com",
            "https://4movierulz.com",
            "https://www.3movierulz.com",
            "https://3movierulz.com"
        ]
        
        # Known working MovieRulz domains (prioritized list)
        self.known_working_domains = [
            "https://www.5movierulz.sarl",
            "https://5movierulz.sarl", 
            "https://www.4movierulz.com",
            "https://4movierulz.com",
            "https://www.3movierulz.com",
            "https://3movierulz.com"
        ]
        
        # Known working MovieRulz domains (test these first)
        self.known_working_domains = [
            "https://www.5movierulz.sarl",
            "https://5movierulz.sarl", 
            "https://www.4movierulz.com",
            "https://4movierulz.com",
            "https://www.3movierulz.com",
            "https://3movierulz.com",
            "https://www.movierulz.com",
            "https://movierulz.com"
        ]
        
        # Common MovieRulz domain patterns (prioritize the ones that work)
        self.domain_patterns = [
            "5movierulz", 
            "4movierulz",
            "3movierulz",
            "2movierulz",
            "1movierulz",
            "movierulz"
        ]
        
        # Common TLDs used by MovieRulz (prioritize working ones)
        self.tlds = [
            ".sarl", ".tc", ".vc", ".ms", ".pe", ".ws", ".cc", 
            ".to", ".me", ".tv", ".com", ".net", ".org", ".in"
        ]
        
    def setup_session(self):
        """Setup session with proper headers and configurations"""
        headers = {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.google.com/',
        }
        self.session.headers.update(headers)
        self.session.timeout = 30

    def find_working_movierulz_url(self) -> Optional[str]:
        """
        Use known domains first, then Google search to find the current working MovieRulz domain
        """
        try:
            logger.info("Testing known working MovieRulz domains first...")
            
            # First, try known working domains
            for domain in self.known_working_domains:
                logger.info(f"Testing known domain: {domain}")
                if self._test_url_accessibility(domain):
                    logger.info(f"Found working MovieRulz domain: {domain}")
                    return domain
            
            
            logger.info("Known domains failed, searching Google for current working MovieRulz domain...")
            
            # Google search query for MovieRulz
            search_queries = [
                "5movierulz official site 2024",
                "movierulz latest working domain",
                "movierulz new link 2025",
                "4movierulz working site"
            ]
            
            for query in search_queries:
                try:
                    # Use Selenium for Google search to avoid blocking
                    options = uc.ChromeOptions()
                    options.headless = True
                    options.add_argument("--no-sandbox")
                    options.add_argument("--disable-dev-shm-usage")
                    
                    driver = uc.Chrome(options=options)
                    
                    # Search on Google
                    google_url = f"https://www.google.com/search?q={quote(query)}"
                    driver.get(google_url)
                    time.sleep(3)
                    
                    # Extract search results
                    search_results = driver.find_elements(By.CSS_SELECTOR, "a[href*='movierulz']")
                    
                    for result in search_results:
                        href = result.get_attribute('href')
                        if href and any(pattern in href.lower() for pattern in self.domain_patterns):
                            # Extract clean URL
                            if '/url?q=' in href:
                                href = href.split('/url?q=')[1].split('&')[0]
                            
                            # Test if URL is working
                            test_url = self._extract_base_url(href)
                            if self._test_url_accessibility(test_url):
                                logger.info(f"Found working MovieRulz URL: {test_url}")
                                driver.quit()
                                return test_url
                    
                    driver.quit()
                    
                except Exception as e:
                    logger.warning(f"Google search attempt failed: {e}")
                    continue
            
            # Fallback: Try common domain combinations
            logger.info("Google search failed, trying common domain patterns...")
            return self._try_common_domains()
            
        except Exception as e:
            logger.error(f"Error finding working MovieRulz URL: {e}")
            return self.base_url  # Return default URL as fallback

    def _extract_base_url(self, url: str) -> str:
        """Extract base URL from full URL"""
        try:
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.netloc}"
        except:
            return url

    def _test_url_accessibility(self, url: str) -> bool:
        """Test if a URL is accessible and has MovieRulz content with search functionality"""
        try:
            logger.info(f"Testing URL accessibility: {url}")
            # Test the main page first
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                logger.info(f"URL {url} - Status: {response.status_code}")
                return False
            
            page_content = response.text.lower()
            
            # Check if it's actually a MovieRulz site
            if not any(indicator in page_content for indicator in ["movierulz", "movie", "download"]):
                return False
            
            # Test the search functionality specifically
            test_search_url = f"{url}/search_movies?s=test"
            search_response = self.session.get(test_search_url, timeout=10)
            
            # If search page loads (even with no results), the site is working
            return search_response.status_code == 200
            
        except:
            return False

    def _try_common_domains(self) -> Optional[str]:
        """Try common MovieRulz domain combinations"""
        for pattern in self.domain_patterns:
            for tld in self.tlds:
                test_url = f"https://www.{pattern}{tld}"
                if self._test_url_accessibility(test_url):
                    logger.info(f"Found working domain: {test_url}")
                    return test_url
        
        logger.warning("No working MovieRulz domain found, using default")
        return self.base_url

    def get_current_url(self) -> str:
        """Get current working MovieRulz URL"""
        if not self.current_working_url:
            # First try the original URL you specified
            if self._test_url_accessibility("https://www.5movierulz.sarl"):
                self.current_working_url = "https://www.5movierulz.sarl"
                logger.info("Using original specified URL: https://www.5movierulz.sarl")
            else:
                self.current_working_url = self.find_working_movierulz_url()
        return self.current_working_url or "https://www.5movierulz.sarl"

    def search_movies(self, movie_name: str, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
        """
        Search for movies on MovieRulz using the current working domain
        """
        max_retries = 3
        retry_delay = 2
        
        # Get current working URL
        current_url = self.get_current_url()
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Searching MovieRulz for: {movie_name} (page {page}) - Attempt {attempt + 1}")
                logger.info(f"Using URL: {current_url}")
                
                # MovieRulz search URL format - try different search patterns
                search_patterns = [
                    f"{current_url}/search_movies?s={quote(movie_name)}",
                    f"{current_url}/search?s={quote(movie_name)}",
                    f"{current_url}/?s={quote(movie_name)}"
                ]
                
                search_url = search_patterns[0]  # Start with the primary pattern
                
                # Add retry-specific headers
                self.session.headers.update({
                    'User-Agent': self.ua.random,
                    'Connection': 'close',
                    'Referer': current_url
                })
                
                response = self.session.get(search_url, timeout=30)
                
                # If we get blocked or redirected, try to find new working URL
                if response.status_code != 200 or "blocked" in response.text.lower():
                    logger.warning("Current URL seems blocked, searching for new working domain...")
                    self.current_working_url = None  # Reset cached URL
                    current_url = self.get_current_url()
                    search_url = f"{current_url}/search_movies?s={quote(movie_name)}"
                    response = self.session.get(search_url, timeout=30)
                
                response.raise_for_status()
                break  # Success, exit retry loop
                
            except (requests.exceptions.ConnectionError, 
                    requests.exceptions.Timeout,
                    ConnectionResetError) as e:
                error_str = str(e)
                logger.warning(f"Connection error on attempt {attempt + 1}: {error_str}")
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    
                    # Reset session and try new URL
                    self.session.close()
                    self.session = requests.Session()
                    self.setup_session()
                    self.current_working_url = None
                    current_url = self.get_current_url()
                else:
                    logger.error(f"All {max_retries} attempts failed")
                    raise e
                    
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            all_movies = []
            
            # Parse MovieRulz search results with multiple selectors
            movie_containers = []
            
            # Try multiple selector patterns for MovieRulz
            selectors_to_try = [
                # Common movie container patterns
                ['div', {'class': re.compile(r'(movie|post|item|card|content)', re.I)}],
                ['article', {'class': re.compile(r'(movie|post|item|card)', re.I)}],
                ['div', {'class': re.compile(r'(entry|result)', re.I)}],
                # Link-based patterns
                ['a', {'href': re.compile(r'/(movie|watch|download|film)', re.I)}],
                # Generic content patterns
                ['div', {'id': re.compile(r'(content|main|posts)', re.I)}],
                ['div', {'class': re.compile(r'(wp-content|content)', re.I)}],
            ]
            
            for tag, attrs in selectors_to_try:
                containers = soup.find_all(tag, attrs)
                if containers:
                    movie_containers = containers
                    logger.info(f"Found {len(containers)} containers using {tag} with {attrs}")
                    break
            
            # If still no containers, try finding all links with movie-like URLs
            if not movie_containers:
                all_links = soup.find_all('a', href=True)
                movie_containers = [link for link in all_links 
                                  if link.get('href') and 
                                  any(keyword in link.get('href').lower() 
                                      for keyword in ['movie', 'film', 'watch', 'download', '/20', '/19'])]
            
            logger.info(f"Found {len(movie_containers)} movie containers")
            
            for container in movie_containers[:per_page]:
                try:
                    # Check if container has multiple movie links
                    movie_links = container.find_all('a', href=True)
                    movie_links = [link for link in movie_links 
                                 if link.get('href') and 
                                 any(keyword in link.get('href').lower() 
                                     for keyword in ['movie', 'watch', 'download'])]
                    
                    if len(movie_links) > 1:
                        # Container has multiple movie links, extract each one
                        for link in movie_links:
                            movie_data = self._extract_movie_data_from_link(link, current_url)
                            if movie_data and self._is_relevant_movie(movie_data, movie_name):
                                all_movies.append(movie_data)
                    else:
                        # Single movie container, use original method
                        movie_data = self._extract_movie_data(container, current_url)
                        if movie_data and self._is_relevant_movie(movie_data, movie_name):
                            all_movies.append(movie_data)
                except Exception as e:
                    logger.warning(f"Error extracting movie data: {e}")
                    continue
            
            # Sort by relevance
            all_movies = self._sort_by_relevance(all_movies, movie_name)
            
            return {
                'status': 'success',
                'source': 'movierulz',
                'base_url': current_url,
                'search_query': movie_name,
                'page': page,
                'per_page': per_page,
                'total_found': len(all_movies),
                'movies': all_movies[:per_page]
            }
            
        except Exception as e:
            logger.error(f"Error parsing MovieRulz search results: {e}")
            return {
                'status': 'error',
                'source': 'movierulz',
                'error': str(e),
                'search_query': movie_name,
                'movies': []
            }

    def _extract_movie_data_from_link(self, link_elem, base_url: str) -> Optional[Dict[str, Any]]:
        """Extract movie data from a single link element"""
        try:
            if not link_elem:
                return None
            
            movie_url = urljoin(base_url, link_elem.get('href'))
            
            # Extract title from link text
            title = link_elem.get_text(strip=True)
            if not title:
                title = link_elem.get('title', '')
            
            # Extract image - look for img in the same parent or nearby
            image_url = ""
            parent = link_elem.parent
            if parent:
                img_elem = parent.find('img')
                if img_elem:
                    image_url = img_elem.get('src') or img_elem.get('data-src', '')
                    if image_url:
                        image_url = urljoin(base_url, image_url)
            
            # Extract metadata from title
            metadata = self._extract_metadata(title, link_elem.parent or link_elem)
            
            return {
                'title': title,
                'url': movie_url,
                'image': image_url,
                'year': metadata.get('year', ''),
                'language': metadata.get('language', ''),
                'quality': metadata.get('quality', ''),
                'size': metadata.get('size', ''),
                'format': metadata.get('format', ''),
                'source': 'movierulz'
            }
            
        except Exception as e:
            logger.warning(f"Error extracting movie data from link: {e}")
            return None

    def _extract_movie_data(self, container, base_url: str) -> Optional[Dict[str, Any]]:
        """Extract movie data from container element"""
        try:
            # Find movie link
            link_elem = container.find('a', href=True)
            if not link_elem:
                link_elem = container if container.name == 'a' else None
            
            if not link_elem:
                return None
            
            movie_url = urljoin(base_url, link_elem.get('href'))
            
            # Extract title
            title = ""
            title_elem = container.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            if title_elem:
                title = title_elem.get_text(strip=True)
            else:
                title = link_elem.get_text(strip=True)
            
            if not title:
                title = link_elem.get('title', '')
            
            # Extract image
            image_url = ""
            img_elem = container.find('img')
            if img_elem:
                image_url = img_elem.get('src') or img_elem.get('data-src', '')
                if image_url:
                    image_url = urljoin(base_url, image_url)
            
            # Extract metadata from title or container
            metadata = self._extract_metadata(title, container)
            
            return {
                'title': title,
                'url': movie_url,
                'image': image_url,
                'year': metadata.get('year', ''),
                'language': metadata.get('language', ''),
                'quality': metadata.get('quality', ''),
                'size': metadata.get('size', ''),
                'format': metadata.get('format', ''),
                'source': 'movierulz'
            }
            
        except Exception as e:
            logger.warning(f"Error extracting movie data: {e}")
            return None

    def _extract_metadata(self, title: str, container) -> Dict[str, str]:
        """Extract metadata like year, language, quality from title and container"""
        metadata = {
            'year': '',
            'language': '',
            'quality': '',
            'size': '',
            'format': ''
        }
        
        text = title.lower()
        
        # Extract year
        year_match = re.search(r'\b(19\d{2}|20[0-3]\d)\b', text)
        if year_match:
            metadata['year'] = year_match.group(1)
        
        # Extract language
        languages = ['hindi', 'english', 'tamil', 'telugu', 'malayalam', 'kannada', 'bengali', 'punjabi', 'marathi', 'gujarati']
        for lang in languages:
            if lang in text:
                metadata['language'] = lang.title()
                break
        
        # Extract quality
        qualities = ['480p', '720p', '1080p', '4k', '2160p', 'hd', 'cam', 'dvdrip', 'webrip', 'bluray', 'hdtv', 'brrip']
        for quality in qualities:
            if quality in text:
                metadata['quality'] = quality.upper()
                break
        
        # Extract size
        size_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(gb|mb)\b', text)
        if size_match:
            metadata['size'] = f"{size_match.group(1)} {size_match.group(2).upper()}"
        
        # Extract format
        formats = ['mp4', 'mkv', 'avi', 'mov', 'wmv']
        for fmt in formats:
            if fmt in text:
                metadata['format'] = fmt.upper()
                break
        
        return metadata

    def _is_relevant_movie(self, movie_data: Dict[str, Any], search_query: str) -> bool:
        """Check if movie is relevant to search query"""
        title = movie_data.get('title', '').lower()
        search_query = search_query.lower()
        
        # Basic relevance check
        if search_query in title:
            return True
        
        # Check individual words
        search_words = search_query.split()
        title_words = title.split()
        
        matching_words = sum(1 for word in search_words if any(word in title_word for title_word in title_words))
        
        # Consider relevant if at least 50% of search words match
        return matching_words >= len(search_words) * 0.5

    def _extract_quality_from_text(self, text: str) -> str:
        """Extract quality information from text"""
        text_lower = text.lower()
        qualities = ['4k', '2160p', '1080p', '720p', '480p', '360p', '240p', 'hd', 'dvdscr', 'cam', 'ts']
        
        for quality in qualities:
            if quality in text_lower:
                return quality.upper()
        return 'Unknown'
    
    def _extract_file_size_from_text(self, text: str) -> str:
        """Extract file size from text"""
        size_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(gb|mb|kb)\b', text.lower())
        if size_match:
            return f"{size_match.group(1)} {size_match.group(2).upper()}"
        return 'Unknown'
    
    def _extract_domain_from_url(self, url: str) -> str:
        """Extract clean domain name from URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Extract main domain (remove subdomains for common patterns)
            if 'streamlare' in domain:
                return 'streamlare.com'
            elif 'vcdnlare' in domain:
                return 'vcdnlare.com'
            elif 'streamtape' in domain:
                return 'streamtape.com'
            elif 'mixdrop' in domain:
                return 'mixdrop.co'
            elif 'doodstream' in domain:
                return 'doodstream.com'
            else:
                return domain
                
        except Exception:
            return 'Unknown'

    def _sort_by_relevance(self, movies: List[Dict[str, Any]], search_query: str) -> List[Dict[str, Any]]:
        """Sort movies by relevance to search query"""
        def relevance_score(movie):
            title = movie.get('title', '').lower()
            search_query_lower = search_query.lower()
            
            # Exact match gets highest score
            if search_query_lower == title:
                return 100
            
            # Substring match
            if search_query_lower in title:
                return 80
            
            # Word-based matching
            search_words = search_query_lower.split()
            title_words = title.split()
            
            matching_words = sum(1 for word in search_words if any(word in title_word for title_word in title_words))
            
            return (matching_words / len(search_words)) * 60
        
        return sorted(movies, key=relevance_score, reverse=True)

    def extract_download_links(self, movie_url: str) -> Dict[str, Any]:
        """
        Extract download links from a MovieRulz movie page
        """
        try:
            logger.info(f"Extracting download links from: {movie_url}")
            
            # Get movie page
            response = self.session.get(movie_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            download_links = []
            
            # Look for streaming service links (priority) and download links
            streaming_services = [
                'streamlare', 'vcdnlare', 'slmaxed', 'sltube', 'streamlare.com',
                'netutv', 'uperbox', 'streamtape', 'droplare', 'streamwish', 
                'filelions', 'mixdrop', 'doodstream', 'upstream'
            ]
            
            # First, look for streaming service links
            all_links = soup.find_all('a', href=True)
            
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # Check for streaming service links
                for service in streaming_services:
                    if (service in href.lower() or service in text.lower()) and len(text) > 3:
                        # Extract quality and size info
                        quality = self._extract_quality_from_text(text)
                        file_size = self._extract_file_size_from_text(text)
                        
                        # Create better link name with domain and service
                        domain = self._extract_domain_from_url(href)
                        service_name = service.title()
                        
                        # Create descriptive text
                        if quality and quality != 'Unknown':
                            link_text = f"{service_name} - {quality}"
                        else:
                            link_text = f"{service_name} Stream"
                        
                        download_links.append({
                            'text': link_text,
                            'url': href,
                            'host': domain,
                            'service_type': service_name,
                            'quality': quality,
                            'file_size': file_size,
                            'source': 'MovieRulz'
                        })
                        break
            
            # If no streaming links found, look for other download links
            if not download_links:
                link_selectors = [
                    'a[href*="download"]',
                    'a[href*="drive.google"]',
                    'a[href*="mega.nz"]',
                    'a[href*="mediafire"]',
                    'a[href*="dropbox"]',
                    'a[href*="1fichier"]',
                    'a[href*="rapidgator"]',
                    'a[href*="uploadrar"]',
                    'a[href*="nitroflare"]',
                    'a[href*="uptobox"]',
                    'a[href*=".mp4"]',
                    'a[href*=".mkv"]',
                    'a[href*=".avi"]'
                ]
                
                for selector in link_selectors:
                    links = soup.select(selector)
                    for link in links:
                        href = link.get('href')
                        text = link.get_text(strip=True)
                        
                        if href and len(href) > 10:
                            # Determine service type
                            service_type = self._identify_service_type(href)
                            
                            # Extract quality and size info
                            quality = self._extract_quality_from_text(text)
                            file_size = self._extract_file_size_from_text(text)
                            
                            download_links.append({
                                'text': text,
                                'url': href,
                                'service_type': service_type,
                                'quality': quality,
                                'file_size': file_size,
                                'source': 'MovieRulz'
                            })
            
            # Remove duplicates
            seen_urls = set()
            unique_links = []
            for link in download_links:
                if link['url'] not in seen_urls:
                    seen_urls.add(link['url'])
                    unique_links.append(link)
            
            return {
                'status': 'success',
                'movie_url': movie_url,
                'total_links': len(unique_links),
                'download_links': unique_links
            }
            
        except Exception as e:
            logger.error(f"Error extracting download links: {e}")
            return {
                'status': 'error',
                'movie_url': movie_url,
                'error': str(e),
                'download_links': []
            }

    def _identify_service_type(self, url: str) -> str:
        """Identify the file hosting service from URL"""
        url_lower = url.lower()
        
        if 'drive.google' in url_lower:
            return "Google Drive"
        elif 'mega.nz' in url_lower:
            return "Mega"
        elif 'mediafire' in url_lower:
            return "MediaFire"
        elif 'dropbox' in url_lower:
            return "Dropbox"
        elif 'onedrive' in url_lower:
            return "OneDrive"
        elif '1fichier' in url_lower:
            return "1Fichier"
        elif 'rapidgator' in url_lower:
            return "RapidGator"
        elif 'uploadrar' in url_lower:
            return "UploadRar"
        elif 'nitroflare' in url_lower:
            return "NitroFlare"
        elif 'uptobox' in url_lower:
            return "Uptobox"
        else:
            domain = urlparse(url).netloc
            return domain.replace('www.', '').replace('.com', '').replace('.net', '').title()

    def _extract_quality_from_text(self, text: str) -> str:
        """Extract quality information from text"""
        text_lower = text.lower()
        qualities = ['480p', '720p', '1080p', '4k', '2160p', 'hd', 'full hd', 'uhd']
        
        for quality in qualities:
            if quality in text_lower:
                return quality.upper()
        
        return "Unknown"

    def _extract_size_from_text(self, text: str) -> str:
        """Extract file size from text"""
        size_match = re.search(r'(\d+(?:\.\d+)?)\s*(gb|mb|kb)', text.lower())
        if size_match:
            return f"{size_match.group(1)} {size_match.group(2).upper()}"
        
        return "Unknown"

def main():
    """Test the MovieRulz agent"""
    agent = MovieRulzAgent()
    
    # Test search
    test_movie = "RRR"
    print(f"Testing MovieRulz search for: {test_movie}")
    
    results = agent.search_movies(test_movie)
    print(json.dumps(results, indent=2))
    
    # Test download link extraction if we found movies
    if results.get('movies'):
        first_movie = results['movies'][0]
        print(f"\nTesting download link extraction for: {first_movie['title']}")
        
        download_results = agent.extract_download_links(first_movie['url'])
        print(json.dumps(download_results, indent=2))

if __name__ == "__main__":
    main()