#!/usr/bin/env python3
"""
SkySetX Agent - Movie search and link extraction from skysetx.rip
Similar to MoviezWap and MovieRulz agents
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time
import logging
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Any, Optional

class SkySetXAgent:
    def __init__(self, config=None):
        self.base_url = "https://skysetx.rip"
        self.search_url = f"{self.base_url}/?s="
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.logger = logging.getLogger(__name__)
        
    def search_movies(self, query, limit=10):
        """Search for movies on SkySetX"""
        try:
            search_url = f"{self.search_url}{query}"
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            movies = []
            
            # Parse movie results
            movie_containers = soup.find_all('div', class_='thumb')
            
            for container in movie_containers[:limit]:
                try:
                    # Extract movie link and title
                    link_elem = container.find('a', href=True)
                    if not link_elem:
                        continue
                        
                    movie_url = link_elem['href']
                    title_elem = container.find('p')
                    title = title_elem.get_text(strip=True) if title_elem else "Unknown"
                    
                    # Extract image
                    img_elem = container.find('img')
                    image = img_elem['src'] if img_elem and img_elem.get('src') else ""
                    
                    movies.append({
                        'title': title,
                        'url': movie_url,
                        'image': image,
                        'source': 'SkySetX'
                    })
                except Exception as e:
                    continue
                    
            return movies[:limit]
            
        except Exception as e:
            print(f"Error searching SkySetX: {e}")
            return []
        
    def extract_links(self, movie_url):
        """Extract download links from movie page"""
        try:
            response = self.session.get(movie_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
            
            # Method 1: Look for download buttons with quality patterns
            # Pattern: "1080P [ 2.4GB ] Link 1", "720P [1.3GB ] Link 1", etc.
            download_links = soup.find_all('a', href=True, string=re.compile(r'(1080p|720p|480p).*?link.*?\d+', re.I))
            
            for link in download_links:
                # Use the enhanced process_download_link method like downloadhub agent
                link_data = self.process_download_link(link)
                if link_data:
                    links.append(link_data)
            
            # Method 2: Look for alternative format - "1080p Download Link 3780MB"
            if not links:
                links.extend(self._extract_alternative_format_links(soup))
            
            # Method 3: If no links found with the primary methods, try fallback
            if not links:
                links = self._fallback_link_extraction(soup)
            
            return links
            
        except Exception as e:
            print(f"Error extracting links from SkySetX: {e}")
            return []
    
    def _fallback_link_extraction(self, soup):
        """Fallback method for link extraction"""
        links = []
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link['href']
            text = link.get_text(strip=True)
            
            # Check for external download hosts or skysetx-specific hosts
            if any(host in href for host in ['drive.google', 'mega.nz', 'mediafire', 'dropbox', 'uploadrar', 'rapidgator', 'uptobhai.blog', 'shortlinkto.onl']):
                # Use the enhanced process_download_link method like downloadhub agent
                link_data = self.process_download_link(link)
                if link_data:
                    links.append(link_data)
        
        return links
    
    def _extract_alternative_format_links(self, soup):
        """Extract links in alternative format for pages with different structure"""
        links = []
        
        # Get page text to find quality sections
        page_text = soup.get_text()
        
        # Find quality indicators and their associated file sizes
        quality_sections = []
        
        # Look for patterns like "1080p Download Link 3780MB"
        quality_patterns = re.findall(r'(1080p|720p|480p)\s+download\s+link\s+(\d+(?:\.\d+)?)\s*(mb|gb)', page_text, re.I)
        
        for quality, size_value, size_unit in quality_patterns:
            quality_sections.append({
                'quality': quality.lower(),
                'size': f"{size_value}{size_unit.upper()}"
            })
        
        # Now find all external download links
        all_links = soup.find_all('a', href=True)
        external_links = []
        
        for link in all_links:
            href = link['href']
            text = link.get_text(strip=True)
            
            # Skip internal links
            if href.startswith('#') or href.startswith('/') or 'skysetx.rip' in href:
                continue
                
            # Look for external download hosts
            if any(host in href for host in ['uptobhai.org', 'shortlinkto.biz', 'drive.google', 'mega.nz', 'mediafire', 'dropbox']):
                external_links.append({
                    'text': text,
                    'href': href,
                    'host': self._extract_host(href)
                })
        
        # Group external links by their position and associate with qualities
        # The structure typically has 3 links per quality (1080p, 720p, 480p)
        # Each quality has: Watch online, Server 1, Server 2
        
        links_per_quality = 3  # Watch online, Server 1, Server 2
        
        for i, quality_info in enumerate(quality_sections):
            start_idx = i * links_per_quality
            end_idx = start_idx + links_per_quality
            
            quality_links = external_links[start_idx:end_idx]
            
            for j, link_info in enumerate(quality_links):
                # Create a temporary link element for processing
                from bs4 import BeautifulSoup
                temp_soup = BeautifulSoup(f'<a href="{link_info["href"]}">{link_info["text"]}</a>', 'html.parser')
                temp_link = temp_soup.find('a')
                
                # Use the enhanced process_download_link method
                link_data = self.process_download_link(temp_link)
                if link_data:
                    # Determine link type for better title
                    link_type = "Unknown"
                    if "watch online" in link_info['text'].lower():
                        link_type = "Watch Online"
                    elif "server 1" in link_info['text'].lower():
                        link_type = "Server 1"
                    elif "server 2" in link_info['text'].lower():
                        link_type = "Server 2"
                    
                    # Update title with quality and size info
                    enhanced_title = f"{quality_info['quality'].upper()} [{quality_info['size']}] {link_type}"
                    link_data['title'] = enhanced_title
                    link_data['text'] = enhanced_title
                    
                    # Update quality and size from our extraction
                    link_data['quality'] = quality_info['quality']
                    link_data['size'] = quality_info['size']
                    link_data['file_size'] = quality_info['size']
                    
                    links.append(link_data)
        
        return links
    
    def _extract_host(self, url):
        """Extract host from URL"""
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        return parsed_url.netloc or 'Unknown'
    
    def _extract_quality_and_size_alternative(self, text):
        """Extract quality and size from alternative format text"""
        quality = 'Unknown'
        size = 'Unknown'
        
        # Extract quality
        if '1080p' in text.lower():
            quality = '1080p'
        elif '720p' in text.lower():
            quality = '720p'
        elif '480p' in text.lower():
            quality = '480p'
        elif '4k' in text.lower():
            quality = '4K'
        
        # Extract size - pattern like "3780MB" or "1610MB"
        size_match = re.search(r'(\d+(?:\.\d+)?)\s*(mb|gb)', text, re.I)
        if size_match:
            size_value = size_match.group(1)
            size_unit = size_match.group(2).upper()
            size = f"{size_value}{size_unit}"
        
        return {
            'quality': quality,
            'size': size
        }
    
    def _extract_quality_and_size(self, text):
        """Extract quality and size from link text"""
        quality = 'Unknown'
        size = 'Unknown'
        
        # Extract quality
        if '1080p' in text.lower():
            quality = '1080p'
        elif '720p' in text.lower():
            quality = '720p'
        elif '480p' in text.lower():
            quality = '480p'
        elif '4k' in text.lower():
            quality = '4K'
        
        # Extract size using regex
        # Pattern: [ 2.4GB ], [1.3GB ], [ 700MB ], etc.
        size_match = re.search(r'\[\s*([0-9.]+\s*[GMK]B)\s*\]', text, re.I)
        if size_match:
            size = size_match.group(1).strip()
        
        return {
            'quality': quality,
            'size': size
        }
    
    def _extract_quality_from_text(self, text):
        """Extract quality from link text (legacy method)"""
        if '1080p' in text.lower():
            return '1080p'
        elif '720p' in text.lower():
            return '720p'
        elif '480p' in text.lower():
            return '480p'
        elif '4k' in text.lower():
            return '4K'
        return 'Unknown'
    
    def get_download_links(self, movie_url: str) -> Dict[str, Any]:
        """
        Enhanced download link extraction with retry logic and structured response
        Following the same pattern as enhanced downloadhub agent
        
        Args:
            movie_url: URL of the movie detail page
            
        Returns:
            Dictionary with movie info and download links
        """
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                self.logger.info(f"SkySetX: Extracting download links from: {movie_url} - Attempt {attempt + 1}")
                
                # Add retry-specific headers
                self.session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Connection': 'close'
                })
                
                response = self.session.get(movie_url, timeout=30)
                response.raise_for_status()
                break  # Success, exit retry loop
                
            except (requests.exceptions.ConnectionError, 
                    requests.exceptions.Timeout,
                    ConnectionResetError) as e:
                error_str = str(e)
                self.logger.warning(f"SkySetX: Connection error on attempt {attempt + 1}: {error_str}")
                
                # Don't retry for timeout errors - site is unreachable
                if 'timed out' in error_str.lower() or 'timeout' in error_str.lower():
                    self.logger.error(f"SkySetX: Timeout error detected - skipping retries for unreachable site")
                    return {'error': f'Site unreachable (timeout): {error_str}'}
                
                if attempt < max_retries - 1:
                    self.logger.info(f"SkySetX: Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    
                    # Reset session for fresh connection
                    self.session.close()
                    self.session = requests.Session()
                    self.session.headers.update({
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    })
                else:
                    self.logger.error(f"SkySetX: All {max_retries} attempts failed")
                    return {'error': f'Connection failed after {max_retries} attempts: {error_str}'}
                    
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract movie title
            title_elem = soup.find('h1') or soup.find('title')
            title = title_elem.get_text(strip=True) if title_elem else "Unknown"
            
            # Use existing extract_links method for actual link extraction
            download_links = self.extract_links(movie_url)
            
            # Extract additional metadata
            metadata = self.extract_page_metadata(soup)
            
            result = {
                'title': title,
                'url': movie_url,
                'metadata': metadata,
                'download_links': download_links,
                'total_links': len(download_links),
                'source': 'SkySetX'
            }
            
            self.logger.info(f"SkySetX: Extracted {len(download_links)} download links")
            return result
            
        except Exception as e:
            self.logger.error(f"SkySetX: Error extracting download links: {str(e)}")
            return {'error': str(e)}
    
    def extract_page_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract metadata from the movie page"""
        metadata = {}
        
        try:
            # Extract IMDB rating
            imdb_elem = soup.find(text=re.compile(r'IMDB.*?(\d+\.\d+)', re.I))
            if imdb_elem:
                imdb_match = re.search(r'(\d+\.\d+)', str(imdb_elem))
                if imdb_match:
                    metadata['imdb_rating'] = imdb_match.group(1)
            
            # Extract director
            director_elem = soup.find(text=re.compile(r'Directed.*?:', re.I))
            if director_elem:
                director_text = str(director_elem.parent.get_text() if director_elem.parent else director_elem)
                director_match = re.search(r'Directed.*?:\s*([^\n]+)', director_text, re.I)
                if director_match:
                    metadata['director'] = director_match.group(1).strip()
            
            # Extract release date
            release_elem = soup.find(text=re.compile(r'Release date.*?:', re.I))
            if release_elem:
                release_text = str(release_elem.parent.get_text() if release_elem.parent else release_elem)
                release_match = re.search(r'Release date.*?:\s*([^\n]+)', release_text, re.I)
                if release_match:
                    metadata['release_date'] = release_match.group(1).strip()
            
            # Extract genres
            genre_elem = soup.find(text=re.compile(r'Genres.*?:', re.I))
            if genre_elem:
                genre_text = str(genre_elem.parent.get_text() if genre_elem.parent else genre_elem)
                genre_match = re.search(r'Genres.*?:\s*([^\n]+)', genre_text, re.I)
                if genre_match:
                    metadata['genres'] = genre_match.group(1).strip()
            
            # Extract languages
            lang_elem = soup.find(text=re.compile(r'Languages.*?:', re.I))
            if lang_elem:
                lang_text = str(lang_elem.parent.get_text() if lang_elem.parent else lang_elem)
                lang_match = re.search(r'Languages.*?:\s*([^\n]+)', lang_text, re.I)
                if lang_match:
                    metadata['languages'] = lang_match.group(1).strip()
            
        except Exception as e:
            self.logger.warning(f"SkySetX: Error extracting metadata: {str(e)}")
        
        return metadata
    
    def process_download_link(self, link_elem) -> Optional[Dict[str, Any]]:
        """Process individual download link element - same as enhanced downloadhub agent"""
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
            
            # Follow redirects to get actual download URL
            actual_url = self.resolve_redirects(href)
            
            # Determine if this is a shortlink that needs unlocking
            is_shortlink = any(shortlink_host in host.lower() for shortlink_host in ['uptobhai', 'shortlinkto', 'shortlink'])
            is_locked = is_shortlink  # All shortlinks are locked initially
            
            return {
                'text': link_text,
                'url': actual_url,
                'original_url': href,
                'host': host,
                'quality': quality,
                'file_size': file_size,
                'title': link_text,
                'size': file_size,
                'type': 'download',
                'source': 'SkySetX',
                'is_shortlink': is_shortlink,
                'needs_unlock': is_shortlink,
                'is_locked': is_locked,
                'status': 'locked' if is_locked else 'unknown'
            }
            
        except Exception as e:
            self.logger.error(f"Error processing download link: {str(e)}")
            return None
    
    def get_host_name(self, url: str) -> str:
        """Extract host name from URL - same as enhanced downloadhub agent"""
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
                'nitroflare.com': 'NitroFlare',
                'uptobhai.blog': 'UpToBhai',
                'uptobhai.org': 'UpToBhai',
                'shortlinkto.onl': 'ShortLinkTo',
                'shortlinkto.biz': 'ShortLinkTo'
            }
            
            for domain_key, host_name in host_mapping.items():
                if domain_key in domain:
                    return host_name
            
            return domain
            
        except:
            return 'Unknown'
    
    def extract_quality(self, text: str) -> str:
        """Extract quality from text - enhanced version"""
        text_lower = text.lower()
        if '4k' in text_lower or '2160p' in text_lower:
            return '4K'
        elif '1080p' in text_lower:
            return '1080p'
        elif '720p' in text_lower:
            return '720p'
        elif '480p' in text_lower:
            return '480p'
        elif 'hd' in text_lower:
            return 'HD'
        return 'Unknown'
    
    def extract_file_size(self, text: str) -> Optional[str]:
        """Extract file size from text - same as enhanced downloadhub agent"""
        size_pattern = r'(\d+(?:\.\d+)?)\s*(MB|GB|KB)'
        match = re.search(size_pattern, text, re.IGNORECASE)
        return match.group() if match else None
    
    def resolve_redirects(self, url: str, max_redirects: int = 5) -> str:
        """Follow redirects to get actual download URL - same as enhanced downloadhub agent"""
        try:
            for _ in range(max_redirects):
                response = self.session.head(url, allow_redirects=False, timeout=10)
                
                if response.status_code in [301, 302, 303, 307, 308]:
                    location = response.headers.get('Location')
                    if location:
                        url = urljoin(url, location)
                    else:
                        break
                else:
                    break
            
            return url
            
        except:
            return url
    
    def bypass_ads_and_redirects(self, url: str) -> str:
        """Attempt to bypass common ad redirects and get direct link - same as enhanced downloadhub agent"""
        try:
            # Common ad bypass patterns
            bypass_patterns = [
                r'go\.php\?url=([^&]+)',
                r'redirect\.php\?url=([^&]+)',
                r'link\.php\?url=([^&]+)',
                r'url=([^&]+)',
            ]
            
            for pattern in bypass_patterns:
                match = re.search(pattern, url)
                if match:
                    import urllib.parse
                    decoded_url = urllib.parse.unquote(match.group(1))
                    return decoded_url
            
            return url
            
        except:
            return url

if __name__ == "__main__":
    agent = SkySetXAgent()
    print("SkySetX Agent initialized successfully!")