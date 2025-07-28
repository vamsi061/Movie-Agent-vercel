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
from urllib.parse import urljoin, urlparse

class SkySetXAgent:
    def __init__(self, config=None):
        self.base_url = "https://skysetx.rip"
        self.search_url = f"{self.base_url}/?s="
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
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
            
            # Look for download buttons with quality patterns
            # Pattern: "1080P [ 2.4GB ] Link 1", "720P [1.3GB ] Link 1", etc.
            download_links = soup.find_all('a', href=True, string=re.compile(r'(1080p|720p|480p).*?link.*?\d+', re.I))
            
            for link in download_links:
                href = link['href']
                text = link.get_text(strip=True)
                
                # Extract quality and size from text
                quality_info = self._extract_quality_and_size(text)
                
                # Extract host from URL for display
                from urllib.parse import urlparse
                parsed_url = urlparse(href)
                host = parsed_url.netloc or 'Unknown'
                
                # Skip links from shortlinkto hosts
                if 'shortlinkto' in host.lower():
                    continue
                
                links.append({
                    'url': href,
                    'quality': quality_info['quality'],
                    'size': quality_info['size'],
                    'file_size': quality_info['size'],  # Frontend expects 'file_size'
                    'type': 'download',
                    'title': text,
                    'text': text,  # Frontend expects 'text' for display
                    'host': host,  # Frontend expects 'host'
                    'source': 'SkySetX'
                })
            
            # If no links found with the primary method, try fallback
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
            
            # Check for external download hosts
            if any(host in href for host in ['drive.google', 'mega.nz', 'mediafire', 'dropbox', 'uploadrar', 'rapidgator']):
                quality = self._extract_quality_from_text(text)
                
                # Extract host from URL for display
                from urllib.parse import urlparse
                parsed_url = urlparse(href)
                host_name = parsed_url.netloc or 'Unknown'
                
                # Skip links from shortlinkto hosts
                if 'shortlinkto' in host_name.lower():
                    continue
                
                links.append({
                    'url': href,
                    'quality': quality,
                    'size': 'Unknown',
                    'file_size': 'Unknown',  # Frontend expects 'file_size'
                    'type': 'download',
                    'title': text,
                    'text': text,  # Frontend expects 'text' for display
                    'host': host_name,  # Frontend expects 'host'
                    'source': 'SkySetX'
                })
        
        return links
    
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

if __name__ == "__main__":
    agent = SkySetXAgent()
    print("SkySetX Agent initialized successfully!")