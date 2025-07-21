#!/usr/bin/env python3
"""
Cursor AI Agent for DownloadHub.legal Movie Search and Download Link Extraction

This agent automatically:
1. Searches for movies on downloadhub.legal
2. Extracts search results with metadata
3. Navigates to specific movie pages
4. Bypasses ads and redirections
5. Extracts direct download links
6. Returns clean JSON data
"""

import requests
import json
import time
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from fake_useragent import UserAgent
import logging
from typing import Dict, List, Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedDownloadHubAgent:
    def __init__(self):
        self.base_url = "https://downloadhub.legal"
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
        Search for movies using the correct downloadhub.legal format with pagination
        """
        try:
            logger.info(f"Searching for movie: {movie_name} (page {page})")
            
            # Use the exact format you specified
            search_url = f"https://downloadhub.legal/?s={movie_name.replace(' ', '+')}"
            
            response = self.session.get(search_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            all_movies = []
            
            # Extract movie links directly from the search results
            all_links = soup.find_all('a', href=True)
            
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # Look for actual movie download links
                if (text and len(text) > 20 and 
                    'downloadhub.legal' in href and
                    any(keyword in text.lower() for keyword in ['download', 'hdrip', 'bluray', 'webrip', 'dvdrip']) and
                    self._is_relevant_to_search(text, movie_name)):
                    
                    # Ensure URL is properly formatted
                    formatted_url = self._format_movie_url(text, href)
                    
                    movie_data = {
                        'title': text,
                        'detail_url': formatted_url,
                        'year': self.extract_year(text),
                        'language': self.extract_language(text),
                        'quality': self.extract_quality(text),
                        'image': None
                    }
                    all_movies.append(movie_data)
            
            # Calculate pagination
            total_movies = len(all_movies)
            start_index = (page - 1) * per_page
            end_index = start_index + per_page
            movies_page = all_movies[start_index:end_index]
            
            total_pages = (total_movies + per_page - 1) // per_page  # Ceiling division
            
            logger.info(f"Found {total_movies} total movies, showing page {page}/{total_pages}")
            
            return {
                'movies': movies_page,
                'pagination': {
                    'current_page': page,
                    'per_page': per_page,
                    'total_movies': total_movies,
                    'total_pages': total_pages,
                    'has_next': page < total_pages,
                    'has_prev': page > 1
                }
            }
            
        except Exception as e:
            logger.error(f"Error searching movies: {str(e)}")
            return {
                'movies': [],
                'pagination': {
                    'current_page': 1,
                    'per_page': per_page,
                    'total_movies': 0,
                    'total_pages': 0,
                    'has_next': False,
                    'has_prev': False
                }
            }
    
    def _is_relevant_to_search(self, text: str, search_term: str) -> bool:
        """Check if the link text is relevant to the search term"""
        text_lower = text.lower()
        search_lower = search_term.lower()
        
        # Check if search words appear in the text
        search_words = search_lower.split()
        text_words = text_lower.split()
        
        matching_words = sum(1 for word in search_words if any(word in text_word for text_word in text_words))
        return matching_words >= len(search_words) * 0.5
    
    def _format_movie_url(self, title: str, original_url: str) -> str:
        """Format movie URL using the correct downloadhub.legal pattern"""
        try:
            # If the original URL is already properly formatted, use it
            if original_url.endswith('/') and 'downloadhub.legal' in original_url:
                return original_url
            
            # Generate URL from title using the pattern you specified
            # Example: "Lies My Babysitter Told 2024 English 1080p | 720p | 480p HDRip ESub Download"
            # Should become: "lies-my-babysitter-told-2024-english-1080p-720p-480p-hdrip-esub-download"
            
            # Clean the title
            clean_title = title.lower()
            
            # Remove common words and characters
            clean_title = re.sub(r'\s*\|\s*', '-', clean_title)  # Replace " | " with "-"
            clean_title = re.sub(r'[^\w\s-]', '', clean_title)   # Remove special chars except spaces and hyphens
            clean_title = re.sub(r'\s+', '-', clean_title)       # Replace spaces with hyphens
            clean_title = re.sub(r'-+', '-', clean_title)        # Replace multiple hyphens with single
            clean_title = clean_title.strip('-')                 # Remove leading/trailing hyphens
            
            # Construct the proper URL
            formatted_url = f"https://downloadhub.legal/{clean_title}/"
            
            logger.info(f"Formatted URL: {original_url} -> {formatted_url}")
            return formatted_url
            
        except Exception as e:
            logger.error(f"Error formatting URL: {e}")
            return original_url
    
    def extract_movie_metadata(self, container) -> Optional[Dict[str, Any]]:
        """Extract movie metadata from search result container"""
        try:
            # Extract title
            title_elem = container.find('h2') or container.find('h3') or container.find('a')
            title = title_elem.get_text(strip=True) if title_elem else "Unknown"
            
            # Extract link
            link_elem = container.find('a', href=True)
            link = urljoin(self.base_url, link_elem['href']) if link_elem else None
            
            # Extract year (from title or separate element)
            year = self.extract_year(title)
            
            # Extract language and quality from title or description
            language = self.extract_language(title)
            quality = self.extract_quality(title)
            
            # Extract image
            img_elem = container.find('img')
            image = img_elem.get('src') or img_elem.get('data-src') if img_elem else None
            
            return {
                'title': title,
                'year': year,
                'language': language,
                'quality': quality,
                'detail_url': link,
                'image': image
            }
            
        except Exception as e:
            logger.error(f"Error extracting movie metadata: {str(e)}")
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
        elif 'punjabi' in text_lower:
            return 'Punjabi'
        else:
            return 'Unknown'
    
    def extract_quality(self, text: str) -> List[str]:
        """Extract quality information from text"""
        qualities = []
        quality_patterns = [r'480p', r'720p', r'1080p', r'4K', r'HD', r'CAM', r'DVDRip', r'BluRay']
        
        for pattern in quality_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                qualities.append(pattern.upper())
                
        return qualities if qualities else ['Unknown']
    
    def get_download_links(self, movie_url: str) -> Dict[str, Any]:
        """
        Extract download links from movie detail page
        
        Args:
            movie_url: URL of the movie detail page
            
        Returns:
            Dictionary with movie info and download links
        """
        try:
            logger.info(f"Extracting download links from: {movie_url}")
            
            response = self.session.get(movie_url)
            response.raise_for_status()
            
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
                'total_links': len(download_links)
            }
            
            logger.info(f"Extracted {len(download_links)} download links")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting download links: {str(e)}")
            return {'error': str(e)}
    
    def extract_download_links(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract download and streaming links for the selected movie"""
        links = []
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Pattern 1: Links with quality + file size pattern (like "1080P [ 2.8GB ] Link 1")
            if re.search(r'(480p|720p|1080p).*?\[.*?(\d+(?:\.\d+)?\s*(?:GB|MB))', text, re.IGNORECASE):
                link_data = self.process_download_link(link)
                if link_data:
                    links.append(link_data)
            
            # Pattern 2: External download/streaming hosts
            elif any(host in href.lower() for host in [
                'uptobhai.blog', 'shortlinkto.onl', 'drive.google.com', 'mega.nz', 'mediafire.com',
                'dropbox.com', 'streamtape.com', 'doodstream.com', 'mixdrop.co', 'upstream.to'
            ]):
                if not self._is_other_movie_link(text, href):
                    link_data = self.process_download_link(link)
                    if link_data:
                        links.append(link_data)
            
            # Pattern 3: Download/Stream links with common keywords
            elif (text and len(text) > 3 and len(text) < 50 and
                  any(keyword in text.lower() for keyword in [
                      'download', 'link 1', 'link 2', 'server', 'mirror', 'watch', 'stream',
                      '480p', '720p', '1080p', 'hd', 'full movie'
                  ]) and
                  not self._is_other_movie_link(text, href) and
                  'downloadhub.legal' not in href):  # Exclude internal navigation
                
                link_data = self.process_download_link(link)
                if link_data:
                    links.append(link_data)
            
            # Pattern 4: Links that look like quality indicators
            elif re.search(r'\b(480p|720p|1080p|hd|full)\b', text, re.IGNORECASE) and len(text) < 30:
                if not self._is_other_movie_link(text, href) and 'downloadhub.legal' not in href:
                    link_data = self.process_download_link(link)
                    if link_data:
                        links.append(link_data)
        
        return links
    
    def _is_other_movie_link(self, text: str, href: str) -> bool:
        """Check if this is a link to another movie or promotional site (not a download link)"""
        text_lower = text.lower()
        href_lower = href.lower()
        
        # Skip promotional/advertisement sites
        promotional_sites = [
            '7starhd', 'hdhub4u', 'filmywap', 'moviesflix', 'worldfree4u',
            'khatrimaza', 'filmyzilla', 'pagalmovies', 'bolly4u', 'moviescounter'
        ]
        
        if any(site in text_lower or site in href_lower for site in promotional_sites):
            return True
        
        # Skip links that look like other movie titles
        other_movie_indicators = [
            'smurfs', 'octopus', 'star trek', 'untamed', 'sakamoto', 'mirchi', 
            'varisu', 'pechi', 'tanvi', 'nikita', 'saiyaara', 'masti', 'bhama',
            'kaliyugam', 'solo boy', 'journey'
        ]
        
        # If text contains other movie names and doesn't have download pattern, skip it
        if (any(indicator in text_lower for indicator in other_movie_indicators) and
            not re.search(r'(480p|720p|1080p).*?\[.*?(\d+(?:\.\d+)?\s*(?:GB|MB))', text, re.IGNORECASE)):
            return True
        
        # Skip if it's a link to another downloadhub.legal movie page
        if ('downloadhub.legal' in href and 
            len(text) > 50 and 
            'download' in text_lower and
            not re.search(r'(480p|720p|1080p).*?\[.*?(\d+(?:\.\d+)?\s*(?:GB|MB))', text, re.IGNORECASE)):
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
            
            # Follow redirects to get actual download URL
            actual_url = self.resolve_redirects(href)
            
            return {
                'text': link_text,
                'url': actual_url,
                'original_url': href,
                'host': host,
                'quality': quality,
                'file_size': file_size
            }
            
        except Exception as e:
            logger.error(f"Error processing download link: {str(e)}")
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
    
    def resolve_redirects(self, url: str, max_redirects: int = 5) -> str:
        """Follow redirects to get actual download URL"""
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
    
    def extract_page_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract additional metadata from movie page"""
        metadata = {}
        
        # Extract description
        desc_elem = soup.find('div', class_=re.compile(r'content|description|summary', re.I))
        if desc_elem:
            metadata['description'] = desc_elem.get_text(strip=True)[:500]
        
        # Extract genre, year, etc. from meta tags or structured data
        meta_tags = soup.find_all('meta')
        for tag in meta_tags:
            name = tag.get('name', '').lower()
            content = tag.get('content', '')
            
            if name in ['description', 'keywords']:
                metadata[name] = content
        
        return metadata
    
    def bypass_ads_and_redirects(self, url: str) -> str:
        """Attempt to bypass common ad redirects and get direct link"""
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

def main():
    """Main function for testing the agent"""
    agent = DownloadHubAgent()
    
    # Example usage
    movie_name = input("Enter movie name to search: ").strip()
    
    if not movie_name:
        print("Please enter a valid movie name")
        return
    
    # Search for movies
    print(f"\nSearching for '{movie_name}'...")
    search_results = agent.search_movies(movie_name)
    
    if not search_results:
        print("No movies found!")
        return
    
    # Display search results
    print(f"\nFound {len(search_results)} movies:")
    for i, movie in enumerate(search_results, 1):
        print(f"{i}. {movie['title']} ({movie['year']}) - {movie['language']} - {movie['quality']}")
    
    # Get user selection
    try:
        choice = int(input(f"\nSelect movie (1-{len(search_results)}): ")) - 1
        if 0 <= choice < len(search_results):
            selected_movie = search_results[choice]
            
            # Extract download links
            print(f"\nExtracting download links for: {selected_movie['title']}")
            download_data = agent.get_download_links(selected_movie['detail_url'])
            
            # Save results to JSON
            output_file = f"downloadhub_results_{movie_name.replace(' ', '_')}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(download_data, f, indent=2, ensure_ascii=False)
            
            print(f"\nResults saved to: {output_file}")
            print(f"Total download links found: {download_data.get('total_links', 0)}")
            
            # Display some links
            links = download_data.get('download_links', [])
            if links:
                print("\nSample download links:")
                for i, link in enumerate(links[:5], 1):
                    print(f"{i}. {link['text']} - {link['host']} ({link['quality']})")
        else:
            print("Invalid selection!")
            
    except ValueError:
        print("Please enter a valid number!")

if __name__ == "__main__":
    main()