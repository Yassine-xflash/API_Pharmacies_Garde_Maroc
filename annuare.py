import requests
import pandas as pd
from bs4 import BeautifulSoup
import json
import time
import logging
import re
import os
from urllib.parse import urljoin, urlparse

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AnnuairePharmacyScraper:
    def __init__(self):
        self.base_url = "https://www.annuaire-gratuit.ma"
        
        # Get the directory where the script is located
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        logger.info(f"Script directory: {self.script_dir}")
        logger.info(f"All output files will be saved in: {self.script_dir}")
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate',  # Removed 'br' compression
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        })
        
        self.pharmacies_data = []
        self.api_key = "AIzaSyBnN118yXQmI6PseuR6rsSRJNZCOkiNJKQ"
        
    def get_page_content(self, url, retries=3):
        """Fetch page content with retry mechanism"""
        for attempt in range(retries):
            try:
                logger.info(f"Fetching {url} (attempt {attempt + 1})")
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                
                if response.status_code == 200:
                    # Handle encoding issues
                    if response.encoding is None or response.encoding.lower() in ['iso-8859-1', 'windows-1252']:
                        response.encoding = 'utf-8'
                    
                    # Try to detect actual encoding if needed
                    if 'charset' in response.headers.get('content-type', '').lower():
                        charset_match = re.search(r'charset=([^;]+)', response.headers['content-type'])
                        if charset_match:
                            detected_encoding = charset_match.group(1).strip()
                            logger.info(f"Detected encoding: {detected_encoding}")
                            response.encoding = detected_encoding
                    
                    # Alternative approach: Try different encodings
                    content = None
                    text_content = None
                    
                    # Try UTF-8 first
                    try:
                        content = response.content.decode('utf-8')
                        text_content = content
                        logger.info("Successfully decoded with UTF-8")
                    except UnicodeDecodeError:
                        logger.warning("UTF-8 decoding failed, trying alternatives...")
                        
                        # Try other common encodings
                        for encoding in ['iso-8859-1', 'windows-1252', 'cp1252']:
                            try:
                                content = response.content.decode(encoding)
                                text_content = content
                                logger.info(f"Successfully decoded with {encoding}")
                                break
                            except UnicodeDecodeError:
                                continue
                    
                    if content is None:
                        # Last resort: ignore decode errors
                        content = response.content.decode('utf-8', errors='ignore')
                        text_content = content
                        logger.warning("Using UTF-8 with error ignore")
                    
                    # Create BeautifulSoup object
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    # Debug: Check if we got valid content
                    page_text = soup.get_text()
                    if len(page_text) < 100 or 'pharmacie' not in page_text.lower():
                        logger.warning(f"Suspicious content received. Length: {len(page_text)}")
                        logger.info(f"First 200 chars: {page_text[:200]}")
                        
                        # Try alternative request method
                        if attempt == 0:  # Only try this on first attempt
                            logger.info("Trying alternative request method...")
                            alt_response = self.get_page_alternative_method(url)
                            if alt_response:
                                return alt_response
                    
                    return soup, text_content
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < retries - 1:
                    time.sleep(3 * (attempt + 1))
                else:
                    logger.error(f"Failed to fetch {url} after {retries} attempts")
                    return None
    
    def test_connection(self, city_input="zghanghan"):
        """Test basic connection and response handling"""
        print(f"🔍 TESTING CONNECTION TO: {city_input}")
        print("="*50)
        
        # Build URL
        if not city_input.startswith('_'):
            city_input = '_' + city_input
        test_url = f"{self.base_url}/pharmacies/{city_input}"
        
        print(f"Testing URL: {test_url}")
        
        # Test basic connection
        try:
            raw_response = requests.get(test_url, timeout=10)
            print(f"Status Code: {raw_response.status_code}")
            print(f"Headers: {dict(raw_response.headers)}")
            print(f"Content-Type: {raw_response.headers.get('content-type', 'Not specified')}")
            print(f"Content-Encoding: {raw_response.headers.get('content-encoding', 'Not specified')}")
            print(f"Response Encoding: {raw_response.encoding}")
            print(f"Content Length: {len(raw_response.content)} bytes")
            
            # Try to decode content
            try:
                decoded_content = raw_response.content.decode('utf-8')
                print(f"✓ UTF-8 decode successful")
                print(f"Decoded length: {len(decoded_content)} chars")
                print(f"First 200 chars: {decoded_content[:200]}")
                
                if 'pharmacie' in decoded_content.lower():
                    print("✓ Content contains 'pharmacie' - looks good!")
                else:
                    print("⚠️ Content doesn't contain 'pharmacie'")
                    
            except UnicodeDecodeError as e:
                print(f"❌ UTF-8 decode failed: {e}")
                
                # Try alternative encodings
                for encoding in ['iso-8859-1', 'windows-1252', 'cp1252']:
                    try:
                        decoded_content = raw_response.content.decode(encoding)
                        print(f"✓ {encoding} decode successful")
                        print(f"First 200 chars: {decoded_content[:200]}")
                        break
                    except:
                        continue
                        
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            
        print("="*50)

    def test_single_city(self, city_input=None):
        """Test scraping for a single city - useful for debugging"""
        if not city_input:
            city_input = "zghanghan"  # Default test city that we know works
            
        # First test the connection
        self.test_connection(city_input)
        
        logger.info(f"🧪 TESTING SINGLE CITY: {city_input}")
        logger.info("="*50)
        
        pharmacies = self.extract_pharmacy_links_from_listing(city_input)
        
        if pharmacies:
            logger.info(f"✅ SUCCESS: Found {len(pharmacies)} pharmacies")
            print(f"\n🎉 Found {len(pharmacies)} pharmacies in {city_input}:")
            
            for i, pharmacy in enumerate(pharmacies[:5], 1):  # Show first 5
                print(f"  {i}. {pharmacy['name']}")
                print(f"     📞 Phone: {pharmacy.get('phone', 'No phone')}")
                print(f"     🏠 Address: {pharmacy.get('address', 'No address')}")
                print()
                
            # Test detailed scraping for first pharmacy if it has href
            if len(pharmacies) > 0 and pharmacies[0].get('href'):
                logger.info("Testing detailed info extraction...")
                detailed = self.get_detailed_pharmacy_info(pharmacies[0])
                print(f"📋 Detailed data sample:")
                for key, value in detailed.items():
                    print(f"   {key}: {value}")
            
            print(f"\n✅ Test completed successfully!")
            return True
        else:
            logger.error(f"❌ FAILED: No pharmacies found for {city_input}")
            print(f"\n❌ No pharmacies found for {city_input}")
            print("🔍 Check the debug files that were created for more information.")
            return False, None
    
    def get_page_alternative_method(self, url):
        """Alternative method to fetch page content"""
        try:
            logger.info("Trying alternative request method with different headers...")
            
            # Create a new session with minimal headers
            alt_session = requests.Session()
            alt_session.headers.update({
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'identity',  # No compression
                'Connection': 'keep-alive',
            })
            
            response = alt_session.get(url, timeout=20)
            
            if response.status_code == 200:
                # Try to decode properly
                content = response.content.decode('utf-8', errors='ignore')
                soup = BeautifulSoup(content, 'html.parser')
                
                # Check if this looks better
                page_text = soup.get_text()
                if 'pharmacie' in page_text.lower():
                    logger.info("Alternative method successful!")
                    return soup, content
                    
        except Exception as e:
            logger.warning(f"Alternative method failed: {e}")
            
        return None
    
    def extract_pharmacy_links_from_listing(self, city_url):
        """Extract pharmacy links from city listing page"""
        # Handle different input formats
        city_name = city_url.strip()
        
        if city_name.startswith('http'):
            # Full URL provided
            full_url = city_name
        elif city_name.startswith('/pharmacies/'):
            # Relative URL provided
            full_url = urljoin(self.base_url, city_name)
        else:
            # Just city name provided - build the URL
            if not city_name.startswith('_'):
                city_name = '_' + city_name
            full_url = f"{self.base_url}/pharmacies/{city_name}"
        
        logger.info(f"Scraping city listing: {full_url} (from input: {city_url.strip()})")
        
        soup, raw_html = self.get_page_content(full_url)
        if not soup or not raw_html:
            logger.error(f"Could not fetch content for {full_url}")
            return []
        
        # Check if we got a valid pharmacy listing page
        page_text = soup.get_text().lower()
        if 'pharmacie' not in page_text:
            logger.warning(f"Page doesn't seem to contain pharmacy listings: {full_url}")
            logger.info(f"Page text preview: {page_text[:200]}...")
            return []
        
        pharmacies = []
        
        # Strategy 1: Look for pharmacy names and extract details from the listing page itself
        pharmacy_entries = self.extract_from_listing_text(soup, raw_html, full_url)
        pharmacies.extend(pharmacy_entries)
        
        # Strategy 2: Look for individual pharmacy page links
        pharmacy_links = self.extract_individual_pharmacy_links(soup)
        pharmacies.extend(pharmacy_links)
        
        # Remove duplicates
        unique_pharmacies = []
        seen_names = set()
        
        for pharmacy in pharmacies:
            # Create a unique key based on name and phone
            unique_key = f"{pharmacy['name']}_{pharmacy.get('phone', '')}"
            if unique_key not in seen_names:
                unique_pharmacies.append(pharmacy)
                seen_names.add(unique_key)
        
        logger.info(f"Extracted {len(unique_pharmacies)} unique pharmacies from {full_url}")
        
        # If no pharmacies found, this is likely an issue
        if not unique_pharmacies:
            logger.error(f"❌ NO PHARMACIES EXTRACTED from {full_url}")
            logger.error("This could mean:")
            logger.error("1. The URL is incorrect or doesn't exist")
            logger.error("2. The page structure has changed")
            logger.error("3. The city name is misspelled")
            logger.error("4. Network/blocking issues")
        
        return unique_pharmacies
    
    def extract_from_listing_text(self, soup, raw_html, full_url):
        """Extract pharmacy data directly from the listing page text - IMPROVED VERSION"""
        pharmacies = []
        
        # Debug: Print the page structure
        logger.info("=== DEBUGGING PAGE CONTENT ===")
        logger.info(f"Page title: {soup.title.string if soup.title else 'No title'}")
        
        # Get the main content text
        text_content = soup.get_text()
        logger.info(f"Page text length: {len(text_content)}")
        
        # IMPROVED: Split text into blocks separated by dashes and process each block
        # This handles the specific format of the annuaire-gratuit.ma site
        text_blocks = re.split(r'\n-\s*', text_content)
        
        logger.info(f"Found {len(text_blocks)} text blocks separated by dashes")
        
        pharmacy_count = 0
        for i, block in enumerate(text_blocks):
            block = block.strip()
            
            # Skip blocks that don't contain pharmacy information
            if not block or len(block) < 10:
                continue
                
            # Check if this block contains pharmacy information
            if 'pharmacie' not in block.lower():
                continue
            
            logger.info(f"Processing block {i}: {block[:100]}...")
            
            # Extract pharmacy name - usually the first line or starts with "Pharmacie"
            lines = [line.strip() for line in block.split('\n') if line.strip()]
            if not lines:
                continue
                
            pharmacy_name = ""
            phone = "0000000000"
            address = ""
            
            # Find the pharmacy name
            for line in lines:
                if 'pharmacie' in line.lower() and len(line) < 100:  # Reasonable name length
                    # Clean up the name
                    if line.lower().startswith('pharmacie'):
                        pharmacy_name = line
                        break
                    elif 'pharmacie' in line.lower():
                        # Extract just the pharmacy part
                        match = re.search(r'(pharmacie[^à]*)', line, re.IGNORECASE)
                        if match:
                            pharmacy_name = match.group(1).strip()
                            break
            
            # If no name found, skip this block
            if not pharmacy_name:
                continue
                
            # Extract phone number - look for patterns like 0536352904 or 05 36 35 01 90
            phone_patterns = [
                r'0\d{9}',  # 0536352904
                r'0\d\s\d{2}\s\d{2}\s\d{2}\s\d{2}',  # 05 36 35 01 90
                r'\b\d{10}\b'  # Any 10 digit number
            ]
            
            for pattern in phone_patterns:
                phone_match = re.search(pattern, block)
                if phone_match:
                    phone = re.sub(r'\s+', '', phone_match.group())  # Remove spaces
                    # Validate it's actually a phone number (starts with 05, 06, 07, etc.)
                    if phone.startswith('0') and len(phone) == 10:
                        break
            
            # Extract address - look for "Adresse:" pattern
            address_match = re.search(r'Adresse:\s*([^.]+)', block, re.IGNORECASE)
            if address_match:
                address = address_match.group(1).strip()
            
            # Clean up pharmacy name
            pharmacy_name = re.sub(r'\s+', ' ', pharmacy_name)  # Normalize whitespace
            
            # Add the pharmacy if we have a valid name
            if pharmacy_name and len(pharmacy_name) > 5:
                pharmacy_data = {
                    'name': pharmacy_name,
                    'phone': phone,
                    'address': address,
                    'href': '',
                    'city': self.extract_city_name_from_url(full_url)
                }
                pharmacies.append(pharmacy_data)
                pharmacy_count += 1
                
                logger.info(f"✓ Extracted pharmacy: {pharmacy_name} | Phone: {phone}")
        
        logger.info(f"Successfully extracted {pharmacy_count} pharmacies using improved text parsing")
        
        # Fallback: If no pharmacies found with the main method, try regex patterns
        if not pharmacies:
            logger.info("No pharmacies found with block method, trying regex fallback...")
            pharmacies = self.extract_with_regex_fallback(text_content, full_url)
        
        # If still no results, save debug info
        if not pharmacies:
            debug_file = self.get_output_path(f"debug_page_{int(time.time())}.html")
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(raw_html)
            logger.warning(f"No pharmacies found. Page saved for debugging: {debug_file}")
            
            # Also save text content for analysis
            debug_text_file = self.get_output_path(f"debug_text_{int(time.time())}.txt")
            with open(debug_text_file, 'w', encoding='utf-8') as f:
                f.write(text_content)
            logger.warning(f"Page text saved for debugging: {debug_text_file}")
        
        return pharmacies
    
    def extract_with_regex_fallback(self, text_content, full_url):
        """Fallback method using regex patterns"""
        pharmacies = []
        
        # More specific patterns for the annuaire-gratuit.ma format
        patterns_to_try = [
            # Pattern for: Pharmacie Name\nCity PhoneNumber
            r'(Pharmacie[^\n]+)\n[^\n]*?(\d{10})',
            # Pattern for: - Pharmacie Name
            r'-\s*(Pharmacie[^\n]+)',
            # Pattern for any line with Pharmacie and potential phone
            r'(Pharmacie[^\n]*?)(?:(\d{10}))?',
        ]
        
        for i, pattern in enumerate(patterns_to_try, 1):
            logger.info(f"Trying fallback pattern {i}: {pattern}")
            matches = re.findall(pattern, text_content, re.MULTILINE | re.IGNORECASE)
            logger.info(f"Fallback pattern {i} found {len(matches)} matches")
            
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        name = match[0].strip()
                        phone = match[1] if len(match) > 1 and match[1] else "0000000000"
                    else:
                        name = match.strip()
                        phone = "0000000000"
                    
                    if len(name) > 5 and 'pharmacie' in name.lower():
                        pharmacies.append({
                            'name': name,
                            'phone': phone,
                            'address': "",
                            'href': '',
                            'city': self.extract_city_name_from_url(full_url)
                        })
                
                if pharmacies:
                    logger.info(f"Fallback method found {len(pharmacies)} pharmacies")
                    break
        
        return pharmacies
    
    def extract_individual_pharmacy_links(self, soup):
        """Look for links to individual pharmacy pages"""
        pharmacies = []
        
        # Find all links that might lead to individual pharmacy pages
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link.get('href')
            text = link.get_text(strip=True)
            
            # Check if this is a pharmacy link
            if (href and 
                ('/pharmacies/' in href or 'pharmacie' in href.lower()) and 
                text and 
                'pharmacie' in text.lower() and
                not href.startswith('/pharmacies/_')):  # Not a city listing
                
                pharmacies.append({
                    'name': text,
                    'href': href,
                    'phone': '',
                    'address': '',
                    'city': ''
                })
        
        return pharmacies
    
    def format_pharmacy_data(self, pharmacy_dict):
        """Format pharmacy data into standard structure"""
        return {
            'name': pharmacy_dict.get('name', ''),
            'phone': pharmacy_dict.get('phone', '0000000000'),
            'address': pharmacy_dict.get('address', ''),
            'href': pharmacy_dict.get('href', ''),
            'city': pharmacy_dict.get('city', '')
        }
    
    def extract_city_name_from_url(self, url):
        """Extract city name from the URL"""
        # Extract from URL like /pharmacies/_casablanca
        match = re.search(r'/pharmacies/_([^/?]+)', url)
        if match:
            city_name = match.group(1)
            # Convert from URL format to display format
            city_name = city_name.replace('-', ' ').title()
            return city_name
        return ""
    
    def extract_city_from_url(self, raw_html):
        """Extract city name from URL or page content"""
        # Try to extract from breadcrumb or title
        city_match = re.search(r'Pharmacies à ([^|<]+)', raw_html)
        if city_match:
            return city_match.group(1).strip()
        return ""
    
    def get_detailed_pharmacy_info(self, pharmacy):
        """Get detailed information from individual pharmacy page"""
        if not pharmacy.get('href'):
            # No individual page, return what we have
            return {
                'pharmacie': pharmacy['name'],
                'lien': '',
                'quartier': '',
                'adresse': pharmacy.get('address', ''),
                'coordonnee': "00.00000000, 0.00000000",
                'telephone': pharmacy.get('phone', '0000000000'),
                'etat': '',
                'cle': self.api_key
            }
        
        # Fetch individual pharmacy page
        pharmacy_url = urljoin(self.base_url, pharmacy['href'])
        logger.info(f"Fetching details for: {pharmacy['name']}")
        
        soup, raw_html = self.get_page_content(pharmacy_url)
        if not soup:
            return self.get_default_pharmacy_data(pharmacy)
        
        # Extract detailed information
        phone = pharmacy.get('phone', '0000000000')
        address = pharmacy.get('address', '')
        coordinates = "00.00000000, 0.00000000"
        etat = ""
        quartier = ""
        
        # Try to extract phone if not already available
        if not phone or phone == '0000000000':
            phone_elem = soup.find(attrs={"itemprop": "telephone"})
            if phone_elem:
                phone_href = phone_elem.get('href', '')
                phone = phone_href.replace("tel:", '').strip() if phone_href else phone
            else:
                # Look for phone patterns in text
                phone_match = re.search(r'(\d{10})', soup.get_text())
                if phone_match:
                    phone = phone_match.group(1)
        
        # Extract address if not available
        if not address:
            address_elem = soup.find('address')
            if address_elem:
                address = address_elem.get_text(strip=True)
                
                # Look for Google Maps coordinates
                maps_link = address_elem.find('a', href=re.compile(r'maps\.google', re.I))
                if maps_link:
                    maps_href = maps_link.get('href', '')
                    coord_match = re.search(r'q=([^&]+)', maps_href)
                    if coord_match:
                        coordinates = coord_match.group(1).replace(",", ', ')
        
        # Extract status/état
        try:
            history_table = soup.find("table", attrs={"class": "pharma_history"})
            if history_table:
                rows = history_table.find_all("tr")
                if rows:
                    last_row = rows[-1]
                    cells = last_row.find_all("td")
                    if cells:
                        etat = cells[-1].get_text(strip=True).replace("Garde ", "")
        except:
            pass
        
        # Extract quartier
        quartier_elem = soup.find("span", attrs={"itemprop": "addressLocality"})
        if quartier_elem:
            quartier = quartier_elem.get_text(strip=True)
        
        return {
            'pharmacie': pharmacy['name'],
            'lien': pharmacy['href'],
            'quartier': quartier,
            'adresse': address,
            'coordonnee': coordinates,
            'telephone': phone,
            'etat': etat,
            'cle': self.api_key
        }
    
    def get_default_pharmacy_data(self, pharmacy):
        """Return default data structure when detailed scraping fails"""
        return {
            'pharmacie': pharmacy['name'],
            'lien': pharmacy.get('href', ''),
            'quartier': '',
            'adresse': pharmacy.get('address', ''),
            'coordonnee': "00.00000000, 0.00000000",
            'telephone': pharmacy.get('phone', '0000000000'),
            'etat': '',
            'cle': self.api_key
        }
    
    def scrape_cities(self, cities_file):
        """Main scraping function"""
        # Ensure cities_file path is relative to script directory
        cities_file_path = self.get_output_path(cities_file)
        
        try:
            with open(cities_file_path, 'r', encoding='utf-8') as f:
                cities = f.readlines()
        except FileNotFoundError:
            logger.error(f"File {cities_file_path} not found")
            return
        
        total_cities = len(cities)
        logger.info(f"Starting to scrape {total_cities} cities")
        
        for i, city_url in enumerate(cities, 1):
            logger.info(f"Processing city {i}/{total_cities}: {city_url.strip()}")
            
            try:
                # Extract pharmacy data from city listing page
                pharmacies = self.extract_pharmacy_links_from_listing(city_url)
                
                if not pharmacies:
                    logger.warning(f"No pharmacies found for city: {city_url.strip()}")
                    continue
                
                # Get detailed information for each pharmacy
                for j, pharmacy in enumerate(pharmacies, 1):
                    logger.info(f"Processing pharmacy {j}/{len(pharmacies)}: {pharmacy['name']}")
                    
                    try:
                        detailed_data = self.get_detailed_pharmacy_info(pharmacy)
                        self.pharmacies_data.append(detailed_data)
                        
                        # Respectful delay
                        time.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"Error processing pharmacy {pharmacy['name']}: {e}")
                        # Add basic data even if detailed scraping fails
                        self.pharmacies_data.append(self.get_default_pharmacy_data(pharmacy))
                
                # Delay between cities
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing city {city_url.strip()}: {e}")
                continue
    
    def get_output_path(self, filename):
        """Get the full path for output file in the script directory"""
        return os.path.join(self.script_dir, filename)
    
    def save_data(self, base_filename='pharmacies_data', save_json=True, save_csv=True, save_excel=False):
        """Save scraped data in multiple formats"""
        if not self.pharmacies_data:
            logger.warning("No data to save")
            return
        
        saved_files = []
        
        try:
            # Create DataFrame for all formats
            df = pd.DataFrame(self.pharmacies_data)
            
            # Save as JSON
            if save_json:
                json_file = self.get_output_path(f"{base_filename}.json")
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(self.pharmacies_data, f, ensure_ascii=False, indent=2)
                saved_files.append(json_file)
                logger.info(f"✓ JSON saved: {json_file}")
            
            # Save as CSV
            if save_csv:
                csv_file = self.get_output_path(f"{base_filename}.csv")
                df.to_csv(csv_file, index=False, encoding='utf-8')
                saved_files.append(csv_file)
                logger.info(f"✓ CSV saved: {csv_file}")
            
            # Save as Excel (optional)
            if save_excel:
                try:
                    excel_file = self.get_output_path(f"{base_filename}.xlsx")
                    df.to_excel(excel_file, index=False, engine='openpyxl')
                    saved_files.append(excel_file)
                    logger.info(f"✓ Excel saved: {excel_file}")
                except ImportError:
                    logger.warning("Excel export requires 'openpyxl'. Install with: pip install openpyxl")
                except Exception as e:
                    logger.warning(f"Could not save Excel file: {e}")
            
            # Also save formatted JSON for your original script compatibility
            original_json = self.get_output_path(f"{base_filename}_original_format.json")
            formatted_output = "[" + df.to_json(orient='records')[1:-1].replace('},{', '},\n{') + "]"
            with open(original_json, 'w', encoding='utf-8') as f:
                f.write(formatted_output)
            saved_files.append(original_json)
            logger.info(f"✓ Original format JSON saved: {original_json}")
            
            # Print detailed summary
            self.print_summary(saved_files, df)
            
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    def print_summary(self, saved_files, df):
        """Print detailed summary of scraped data"""
        print(f"\n{'='*50}")
        print(f"🎉 SCRAPING COMPLETED SUCCESSFULLY!")
        print(f"{'='*50}")
        print(f"📊 Total pharmacies scraped: {len(self.pharmacies_data)}")
        print(f"📁 All files saved in: {self.script_dir}")
        print(f"📄 Files created:")
        for file in saved_files:
            # Show just the filename for cleaner display
            filename = os.path.basename(file)
            file_size = os.path.getsize(file) / 1024  # Size in KB
            print(f"   ✓ {filename} ({file_size:.1f} KB)")
        
        # Statistics
        cities_count = df['quartier'].nunique() if 'quartier' in df.columns else 0
        phones_count = len(df[df['telephone'] != '0000000000']) if 'telephone' in df.columns else 0
        addresses_count = len(df[df['adresse'] != '']) if 'adresse' in df.columns else 0
        
        print(f"\n📈 Data Quality Statistics:")
        print(f"   🏙️  Cities covered: {cities_count}")
        print(f"   📞 Pharmacies with phone: {phones_count}")
        print(f"   🏠 Pharmacies with address: {addresses_count}")
        print(f"   📍 Data completeness: {((phones_count + addresses_count) / (len(df) * 2) * 100):.1f}%")
        
        # Show sample data
        if self.pharmacies_data:
            print(f"\n📋 Sample pharmacy data:")
            sample = self.pharmacies_data[0]
            for key, value in sample.items():
                print(f"   {key}: {value}")
        
        print(f"\n✨ Ready to use! All files are in your project directory.")
        print(f"📂 Location: {self.script_dir}")
        print(f"{'='*50}")
    
    def save_filtered_data(self, filter_criteria=None, output_suffix="filtered"):
        """Save filtered data based on criteria"""
        if not self.pharmacies_data:
            logger.warning("No data to filter")
            return
        
        df = pd.DataFrame(self.pharmacies_data)
        
        # Apply filters
        if filter_criteria:
            if 'has_phone' in filter_criteria and filter_criteria['has_phone']:
                df = df[df['telephone'] != '0000000000']
            
            if 'has_address' in filter_criteria and filter_criteria['has_address']:
                df = df[df['adresse'] != '']
            
            if 'cities' in filter_criteria:
                cities = filter_criteria['cities']
                df = df[df['quartier'].isin(cities)]
        
        # Save filtered data
        filtered_data = df.to_dict('records')
        base_filename = self.get_output_path(f"pharmacies_{output_suffix}")
        
        # Temporarily store filtered data
        original_data = self.pharmacies_data
        self.pharmacies_data = filtered_data
        
        # Get base filename without path for the save_data method
        base_name_only = f"pharmacies_{output_suffix}"
        self.save_data(base_name_only)
        
        # Restore original data
        self.pharmacies_data = original_data
        
        logger.info(f"Filtered data saved: {len(filtered_data)} pharmacies")
    
    def test_single_city(self, city_input=None):
        """Test scraping for a single city - useful for debugging"""
        if not city_input:
            city_input = "zghanghan"  # Default test city that we know works
            
        logger.info(f"🧪 TESTING SINGLE CITY: {city_input}")
        logger.info("="*50)
        
        pharmacies = self.extract_pharmacy_links_from_listing(city_input)
        
        if pharmacies:
            logger.info(f"✅ SUCCESS: Found {len(pharmacies)} pharmacies")
            print(f"\n🎉 Found {len(pharmacies)} pharmacies in {city_input}:")
            
            for i, pharmacy in enumerate(pharmacies[:5], 1):  # Show first 5
                print(f"  {i}. {pharmacy['name']}")
                print(f"     📞 Phone: {pharmacy.get('phone', 'No phone')}")
                print(f"     🏠 Address: {pharmacy.get('address', 'No address')}")
                print()
                
            # Test detailed scraping for first pharmacy if it has href
            if len(pharmacies) > 0 and pharmacies[0].get('href'):
                logger.info("Testing detailed info extraction...")
                detailed = self.get_detailed_pharmacy_info(pharmacies[0])
                print(f"📋 Detailed data sample:")
                for key, value in detailed.items():
                    print(f"   {key}: {value}")
            
            print(f"\n✅ Test completed successfully!")
            return True
        else:
            logger.error(f"❌ FAILED: No pharmacies found for {city_input}")
            print(f"\n❌ No pharmacies found for {city_input}")
            print("🔍 Check the debug files that were created for more information.")
            return False

def main():
    scraper = AnnuairePharmacyScraper()
    
    # Check command line arguments or ask user
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        # Test mode with a single city
        test_city = "zghanghan"  # Default test city
        if len(sys.argv) > 2:
            test_city = sys.argv[2]
        
        print(f"Testing with city: {test_city}")
        scraper.test_single_city(test_city)
        return
    
    if len(sys.argv) > 1 and sys.argv[1] == 'debug':
        # Debug connection mode
        test_city = "zghanghan"  # Default test city
        if len(sys.argv) > 2:
            test_city = sys.argv[2]
        
        print(f"Debug connection test with city: {test_city}")
        scraper.test_connection(test_city)
        return
    
    # Normal scraping mode
    cities_file = 'href.txt'
    cities_file_path = scraper.get_output_path(cities_file)
    
    try:
        with open(cities_file_path, 'r', encoding='utf-8') as f:
            cities_count = len(f.readlines())
        logger.info(f"Found {cities_count} cities in {cities_file_path}")
    except FileNotFoundError:
        logger.error(f"Please create {cities_file_path} with city names like:")
        logger.error("  zghanghan")
        logger.error("  casablanca")  
        logger.error("  rabat")
        logger.error("  marrakech")
        logger.error("  (one city name per line)")
        logger.error(f"File should be located at: {cities_file_path}")
        return
    
    # Ask user about output formats
    print(f"\n📊 OUTPUT FORMAT OPTIONS:")
    print(f"1. JSON + CSV (default)")
    print(f"2. JSON only") 
    print(f"3. CSV only")
    print(f"4. All formats (JSON + CSV + Excel)")
    
    choice = input("Choose format (1-4) or press Enter for default: ").strip()
    
    save_json = True
    save_csv = True 
    save_excel = False
    
    if choice == '2':
        save_csv = False
    elif choice == '3':
        save_json = False
    elif choice == '4':
        save_excel = True
    
    # Ask for custom filename
    custom_name = input("Enter custom filename (or press Enter for 'pharmacies_data'): ").strip()
    base_filename = custom_name if custom_name else 'pharmacies_data'
    
    print(f"\n🚀 Starting scraping process...")
    print(f"📄 Output filename: {base_filename}")
    print(f"💾 Formats: JSON={save_json}, CSV={save_csv}, Excel={save_excel}")
    
    # Start scraping
    scraper.scrape_cities(cities_file)
    
    # Save results
    scraper.save_data(base_filename, save_json, save_csv, save_excel)
    
    # Ask if user wants filtered versions
    if scraper.pharmacies_data:
        print(f"\n🔍 FILTERING OPTIONS:")
        create_filtered = input("Create filtered versions? (y/n): ").lower().startswith('y')
        
        if create_filtered:
            # Save pharmacies with phone numbers only
            scraper.save_filtered_data(
                {'has_phone': True}, 
                f"{base_filename}_with_phones"
            )
            
            # Save pharmacies with complete data
            scraper.save_filtered_data(
                {'has_phone': True, 'has_address': True}, 
                f"{base_filename}_complete"
            )
            
            print("✓ Filtered versions created!")

if __name__ == "__main__":
    main()