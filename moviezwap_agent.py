#!/usr/bin/env python3
"""
MoviezWap Agent - Source 2 for Movie Agent
Handles movie search and download link extraction from moviezwap.pink
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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MoviezWapAgent:
    def __init__(self):
        self.base_url = "https://www.moviezwap.pink"
        self.session = requests.Session()
        self.ua = UserAgent()
        self.setup_session()
        
    def setup_session(self):
        """Setup session with proper headers and configurations"""
        headers = {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session.headers.update(headers)
        self.session.timeout = 30
        
    def search_movies(self, movie_name: str, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
        """
        Search for movies on moviezwap.pink
        """
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Searching MoviezWap for: {movie_name} (page {page}) - Attempt {attempt + 1}")
                
                # Try multiple search approaches for MoviezWap
                search_urls = [
                    f"{self.base_url}/search.php?q={quote(movie_name)}",
                    f"{self.base_url}/?s={quote(movie_name)}",
                    f"{self.base_url}/category/Telugu-(2025)-Movies.html",  # Fallback to category
                ]
                
                response = None
                for search_url in search_urls:
                    try:
                        logger.info(f"Trying search URL: {search_url}")
                        response = self.session.get(search_url, timeout=30)
                        if response.status_code == 200:
                            # Check if we got actual search results
                            if movie_name.lower() in response.text.lower() or "movie" in response.text.lower():
                                break
                    except:
                        continue
                
                if not response or response.status_code != 200:
                    # If search fails, try browsing recent movies
                    search_url = f"{self.base_url}/category/Telugu-(2025)-Movies.html"
                
                # Add retry-specific headers
                self.session.headers.update({
                    'User-Agent': self.ua.random,
                    'Connection': 'close'
                })
                
                response = self.session.get(search_url, timeout=30)
                response.raise_for_status()
                break  # Success, exit retry loop
                
            except (requests.exceptions.ConnectionError, 
                    requests.exceptions.Timeout,
                    ConnectionResetError) as e:
                logger.warning(f"Connection error on attempt {attempt + 1}: {str(e)}")
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    
                    # Reset session for fresh connection
                    self.session.close()
                    self.session = requests.Session()
                    self.setup_session()
                else:
                    logger.error(f"All {max_retries} attempts failed")
                    raise e
                    
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            all_movies = []
            
            # Extract movie links from search results - improved for MoviezWap
            all_links = soup.find_all('a', href=True)
            
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # Look for actual movie page links (not download links)
                if (text and len(text) > 15 and 
                    self._is_movie_page_link(href, text) and
                    self._is_relevant_to_search(text, movie_name)):
                    
                    # Ensure URL is properly formatted
                    full_url = urljoin(self.base_url, href)
                    
                    # Extract additional info from the link's container
                    container = link.find_parent(['div', 'li', 'article'])
                    
                    movie_data = {
                        'title': text,
                        'detail_url': full_url,
                        'year': self.extract_year(text),
                        'language': self.extract_language(text),
                        'quality': self.extract_quality(text),
                        'image': self._extract_image_from_container(container) if container else None,
                        'source': 'MoviezWap'
                    }
                    all_movies.append(movie_data)
            
            # Remove duplicates based on URL
            seen_urls = set()
            unique_movies = []
            for movie in all_movies:
                if movie['detail_url'] not in seen_urls:
                    seen_urls.add(movie['detail_url'])
                    unique_movies.append(movie)
            
            # Calculate pagination
            total_movies = len(unique_movies)
            start_index = (page - 1) * per_page
            end_index = start_index + per_page
            movies_page = unique_movies[start_index:end_index]
            
            total_pages = (total_movies + per_page - 1) // per_page
            
            logger.info(f"Found {total_movies} total movies from MoviezWap, showing page {page}/{total_pages}")
            
            return {
                'movies': movies_page,
                'pagination': {
                    'current_page': page,
                    'per_page': per_page,
                    'total_movies': total_movies,
                    'total_pages': total_pages,
                    'has_next': page < total_pages,
                    'has_prev': page > 1
                },
                'source': 'MoviezWap'
            }
            
        except Exception as e:
            logger.error(f"Error searching MoviezWap: {str(e)}")
            return {
                'movies': [],
                'pagination': {
                    'current_page': 1,
                    'per_page': per_page,
                    'total_movies': 0,
                    'total_pages': 0,
                    'has_next': False,
                    'has_prev': False
                },
                'source': 'MoviezWap'
            }
    
    def _is_movie_page_link(self, href: str, text: str) -> bool:
        """Check if a link points to a movie page (not a download link)"""
        href_lower = href.lower()
        text_lower = text.lower()
        
        # Must be a movie page URL pattern
        movie_page_patterns = [
            '/movie/', '.html'
        ]
        
        has_movie_url = any(pattern in href_lower for pattern in movie_page_patterns)
        
        # Must have movie-like text (title with year, quality, etc.)
        movie_text_indicators = [
            '(20', '(19',  # Year patterns
            'hdrip', 'webrip', 'bluray', 'dvdrip', 'camrip',
            'telugu', 'tamil', 'hindi', 'english', 'malayalam',
            'original', 'dubbed'
        ]
        
        has_movie_text = any(indicator in text_lower for indicator in movie_text_indicators)
        
        # Exclude navigation, category, and other non-movie links
        exclude_patterns = [
            'category/', 'search.php', 'contact', 'about', 'privacy', 'terms',
            'telegram', 'facebook', 'twitter', 'instagram', 'bookmark',
            'join', 'download', 'movies download', 'new movies'
        ]
        
        is_excluded = any(pattern in href_lower or pattern in text_lower for pattern in exclude_patterns)
        
        # Must be a proper movie title (reasonable length)
        is_proper_length = 20 <= len(text) <= 200
        
        return has_movie_url and has_movie_text and not is_excluded and is_proper_length
    
    def _is_relevant_to_search(self, text: str, search_term: str) -> bool:
        """Check if the link text is relevant to the search term"""
        text_lower = text.lower()
        search_lower = search_term.lower()
        
        # Check if search words appear in the text
        search_words = search_lower.split()
        text_words = text_lower.split()
        
        matching_words = sum(1 for word in search_words if any(word in text_word for text_word in text_words))
        return matching_words >= len(search_words) * 0.4  # 40% match threshold
    
    def _extract_image_from_container(self, container) -> Optional[str]:
        """Extract image URL from container"""
        img = container.find('img')
        if img:
            return img.get('src') or img.get('data-src')
        return None
    
    def extract_year(self, text: str) -> Optional[str]:
        """Extract year from text"""
        year_match = re.search(r'\b(19|20)\d{2}\b', text)
        return year_match.group() if year_match else None
    
    def extract_language(self, text: str) -> str:
        """Extract language from text"""
        text_lower = text.lower()
        if 'hindi' in text_lower:
            return 'Hindi'
        elif 'english' in text_lower:
            return 'English'
        elif 'tamil' in text_lower:
            return 'Tamil'
        elif 'telugu' in text_lower:
            return 'Telugu'
        elif 'malayalam' in text_lower:
            return 'Malayalam'
        elif 'kannada' in text_lower:
            return 'Kannada'
        elif 'punjabi' in text_lower:
            return 'Punjabi'
        else:
            return 'Unknown'
    
    def extract_quality(self, text: str) -> List[str]:
        """Extract quality information from text"""
        qualities = []
        quality_patterns = [r'480p', r'720p', r'1080p', r'4K', r'HD', r'CAM', r'DVDRip', r'BluRay', r'WebRip']
        
        for pattern in quality_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                qualities.append(pattern.upper())
                
        return qualities if qualities else ['Unknown']
    
    def get_download_links(self, movie_url: str) -> Dict[str, Any]:
        """
        Extract download links from movie detail page
        """
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Extracting MoviezWap download links from: {movie_url} - Attempt {attempt + 1}")
                
                # Add retry-specific headers
                self.session.headers.update({
                    'User-Agent': self.ua.random,
                    'Connection': 'close'
                })
                
                response = self.session.get(movie_url, timeout=30)
                response.raise_for_status()
                break  # Success, exit retry loop
                
            except (requests.exceptions.ConnectionError, 
                    requests.exceptions.Timeout,
                    ConnectionResetError) as e:
                logger.warning(f"Connection error on attempt {attempt + 1}: {str(e)}")
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    
                    # Reset session for fresh connection
                    self.session.close()
                    self.session = requests.Session()
                    self.setup_session()
                else:
                    logger.error(f"All {max_retries} attempts failed")
                    return {'error': f'Connection failed after {max_retries} attempts: {str(e)}'}
                    
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract movie title
            title_elem = soup.find('h1') or soup.find('title')
            title = title_elem.get_text(strip=True) if title_elem else "Unknown"
            
            # Find download links
            download_links = self.extract_download_links(soup)
            
            # Extract additional metadata
            metadata = self.extract_page_metadata(soup)
            
            result = {
                'title': title,
                'url': movie_url,
                'metadata': metadata,
                'download_links': download_links,
                'total_links': len(download_links),
                'source': 'MoviezWap'
            }
            
            logger.info(f"Extracted {len(download_links)} download links from MoviezWap")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting MoviezWap download links: {str(e)}")
            return {'error': str(e), 'source': 'MoviezWap'}
    
    def extract_download_links(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract download links from MoviezWap movie page"""
        links = []
        all_links = soup.find_all('a', href=True)
        
        logger.info(f"MoviezWap: Found {len(all_links)} total links on page")
        
        download_candidates = 0
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Look for download-related links
            if self._is_download_link(href, text):
                download_candidates += 1
                logger.info(f"MoviezWap: Found download candidate: {text[:50]} -> {href}")
                link_data = self.process_download_link(link)
                if link_data:
                    links.append(link_data)
                    logger.info(f"MoviezWap: Added download link: {link_data['text'][:50]}")
        
        logger.info(f"MoviezWap: Found {download_candidates} download candidates, processed {len(links)} valid links")
        return links
    
    def _is_download_link(self, href: str, text: str) -> bool:
        """Check if a link is a download link - improved for MoviezWap"""
        href_lower = href.lower()
        text_lower = text.lower()
        
        # Skip internal navigation links
        skip_patterns = [
            'category/', 'search.php', 'contact', 'about', 'privacy', 'terms',
            'telegram.me', 'facebook.com', 'twitter.com', 'instagram.com',
            '/category/', 'moviezwap.pink', 'bookmark', 'join'
        ]
        
        if any(pattern in href_lower for pattern in skip_patterns):
            return False
        
        # Priority 1: Direct file hosting services
        direct_hosts = [
            'drive.google.com', 'mega.nz', 'mediafire.com', 'dropbox.com',
            'uploadrar.com', 'rapidgator.net', 'nitroflare.com', 'uptobox.com',
            'gofile.io', 'pixeldrain.com', 'anonfiles.com', 'zippyshare.com'
        ]
        
        if any(host in href_lower for host in direct_hosts):
            return True
        
        # Priority 2: Shortlink services
        shortlink_services = [
            'shortlinkto.onl', 'shortlinkto.biz', 'uptobhai.blog', 'shortlink.to',
            'linkvertise.com', 'adf.ly', 'bit.ly', 'tinyurl.com'
        ]
        
        if any(service in href_lower for service in shortlink_services):
            return True
        
        # Priority 3: Download-related text patterns (be more flexible)
        download_text_patterns = [
            'download link', 'server 1', 'server 2', 'mirror 1', 'mirror 2',
            'watch online', 'stream', 'direct link', 'file link',
            'download', 'link', 'server', 'mirror', 'watch'
        ]
        
        # Check if text contains download-related words and is not too long (avoid paragraphs)
        if (any(pattern in text_lower for pattern in download_text_patterns) and 
            len(text) < 100 and len(text) > 3):
            return True
        
        # Priority 4: URLs that look like download endpoints
        download_url_patterns = [
            '/download/', '/link/', '/server/', '/mirror/', '/watch/', '/stream/'
        ]
        
        if any(pattern in href_lower for pattern in download_url_patterns):
            return True
        
        return False
    
    def process_download_link(self, link_elem) -> Optional[Dict[str, Any]]:
        """Process individual download link element"""
        try:
            href = link_elem.get('href')
            if not href:
                return None
            
            # Skip non-download links
            skip_patterns = ['javascript:', 'mailto:', '#', 'tel:']
            if any(pattern in href.lower() for pattern in skip_patterns):
                return None
            
            # Get link text
            link_text = link_elem.get_text(strip=True)
            
            # Determine host
            host = self.get_host_name(href)
            
            # Extract quality and file size from link text
            quality = self.extract_quality(link_text)
            file_size = self.extract_file_size(link_text)
            
            # Handle relative URLs
            if href.startswith('/'):
                href = urljoin(self.base_url, href)
            
            return {
                'text': link_text,
                'url': href,
                'original_url': href,
                'host': host,
                'quality': quality,
                'file_size': file_size,
                'source': 'MoviezWap'
            }
            
        except Exception as e:
            logger.error(f"Error processing MoviezWap download link: {str(e)}")
            return None
    
    def get_host_name(self, url: str) -> str:
        """Extract host name from URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Map common hosts
            host_mapping = {
                'drive.google.com': 'Google Drive',
                'mega.nz': 'Mega',
                'mediafire.com': 'MediaFire',
                'dropbox.com': 'Dropbox',
                '1fichier.com': '1Fichier',
                'rapidgator.net': 'RapidGator',
                'uploadrar.com': 'UploadRar',
                'nitroflare.com': 'NitroFlare'
            }
            
            for domain_key, host_name in host_mapping.items():
                if domain_key in domain:
                    return host_name
            
            return domain
            
        except:
            return 'Unknown'
    
    def extract_file_size(self, text: str) -> Optional[str]:
        """Extract file size from text"""
        size_pattern = r'(\d+(?:\.\d+)?)\s*(MB|GB|KB)'
        match = re.search(size_pattern, text, re.IGNORECASE)
        return match.group() if match else None
    
    def extract_page_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract additional metadata from movie page"""
        metadata = {}
        
        # Extract description
        desc_elem = soup.find('div', class_=re.compile(r'content|description|summary', re.I))
        if desc_elem:
            metadata['description'] = desc_elem.get_text(strip=True)[:500]
        
        # Extract genre, year, etc. from meta tags
        meta_tags = soup.find_all('meta')
        for tag in meta_tags:
            name = tag.get('name', '').lower()
            content = tag.get('content', '')
            
            if name in ['description', 'keywords']:
                metadata[name] = content
        
        return metadata

def main():
    """Main function for testing the MoviezWap agent"""
    agent = MoviezWapAgent()
    
    # Example usage
    movie_name = input("Enter movie name to search on MoviezWap: ").strip()
    
    if not movie_name:
        print("Please enter a valid movie name")
        return
    
    # Search for movies
    print(f"\nSearching MoviezWap for '{movie_name}'...")
    search_results = agent.search_movies(movie_name)
    
    movies = search_results.get('movies', [])
    if not movies:
        print("No movies found on MoviezWap!")
        return
    
    # Display search results
    print(f"\nFound {len(movies)} movies on MoviezWap:")
    for i, movie in enumerate(movies, 1):
        print(f"{i}. {movie['title']} ({movie['year']}) - {movie['language']} - {movie['quality']}")
    
    # Get user selection
    try:
        choice = int(input(f"\nSelect movie (1-{len(movies)}): ")) - 1
        if 0 <= choice < len(movies):
            selected_movie = movies[choice]
            
            # Extract download links
            print(f"\nExtracting download links for: {selected_movie['title']}")
            download_data = agent.get_download_links(selected_movie['detail_url'])
            
            # Save results to JSON
            output_file = f"moviezwap_results_{movie_name.replace(' ', '_')}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(download_data, f, indent=2, ensure_ascii=False)
            
            print(f"\nMoviezWap results saved to: {output_file}")
            print(f"Total download links found: {download_data.get('total_links', 0)}")
            
            # Display some links
            links = download_data.get('download_links', [])
            if links:
                print("\nSample download links from MoviezWap:")
                for i, link in enumerate(links[:5], 1):
                    print(f"{i}. {link['text']} - {link['host']} ({link['quality']})")
        else:
            print("Invalid selection!")
            
    except ValueError:
        print("Please enter a valid number!")

if __name__ == "__main__":
    main()