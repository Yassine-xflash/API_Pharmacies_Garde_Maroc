import requests
import pandas as pd
from bs4 import BeautifulSoup
import json
import time
import logging
import re
from urllib.parse import urljoin, urlparse

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AnnuairePharmacyScraper:
    def __init__(self):
        self.base_url = "https://www.annuaire-gratuit.ma"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7,ar;q=0.6',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
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
                    return BeautifulSoup(response.content, 'html.parser'), response.text
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < retries - 1:
                    time.sleep(3 * (attempt + 1))
                else:
                    logger.error(f"Failed to fetch {url} after {retries} attempts")
                    return None, None
    
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
        
        pharmacies = []
        
        # Strategy 1: Look for pharmacy names and extract details from the listing page itself
        pharmacy_entries = self.extract_from_listing_text(soup, raw_html)
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
        return unique_pharmacies
    
    def extract_from_listing_text(self, soup, raw_html):
        """Extract pharmacy data directly from the listing page text"""
        pharmacies = []
        
        # Get the main content text
        text_content = soup.get_text()
        
        # Pattern to match pharmacy entries - make it more flexible for different cities
        # Format: "Pharmacie Name City PhoneNumber Pharmacie Name à City numéro de téléphone PhoneNumber Adresse: Address..."
        city_from_url = self.extract_city_name_from_url(full_url)
        
        # Create flexible pattern that works with any city name
        pharmacy_pattern = rf'Pharmacie\s+([^{city_from_url}]+?)\s+{city_from_url}\s+(\d{{10}})?.*?(?:Adresse:\s*([^.]+))?'
        
        matches = re.finditer(pharmacy_pattern, text_content, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            name = match.group(1).strip()
            phone = match.group(2) if match.group(2) else "0000000000"
            address = match.group(3).strip() if match.group(3) else ""
            
            if name and len(name) > 2:  # Basic validation
                pharmacies.append({
                    'name': f"Pharmacie {name}",
                    'phone': phone,
                    'address': address,
                    'href': '',  # No individual page link
                    'city': city_from_url
                })
        
        # Alternative pattern for simpler format
        if not pharmacies:
            # Look for lines that start with "-" (list items)
            lines = text_content.split('\n')
            current_pharmacy = {}
            
            for line in lines:
                line = line.strip()
                
                if line.startswith('-') or line.startswith('Pharmacie'):
                    # Process previous pharmacy if exists
                    if current_pharmacy.get('name'):
                        pharmacies.append(self.format_pharmacy_data(current_pharmacy))
                    
                    # Start new pharmacy
                    current_pharmacy = {}
                    
                    # Extract name and phone from line
                    # Format: "Pharmacie Name City PhoneNumber"
                    phone_match = re.search(r'(\d{10})', line)
                    if phone_match:
                        phone = phone_match.group(1)
                        name_part = line[:phone_match.start()].strip()
                        name_part = re.sub(r'^-\s*', '', name_part)  # Remove leading dash
                        
                        current_pharmacy['name'] = name_part
                        current_pharmacy['phone'] = phone
                    else:
                        # No phone number found
                        name_part = re.sub(r'^-\s*', '', line).strip()
                        if 'Pharmacie' in name_part:
                            current_pharmacy['name'] = name_part
                            current_pharmacy['phone'] = "0000000000"
                
                elif current_pharmacy.get('name') and 'Adresse:' in line:
                    # Extract address
                    address_match = re.search(r'Adresse:\s*(.+)', line)
                    if address_match:
                        current_pharmacy['address'] = address_match.group(1).strip()
            
            # Don't forget the last pharmacy
            if current_pharmacy.get('name'):
                pharmacies.append(self.format_pharmacy_data(current_pharmacy))
        
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
        try:
            with open(cities_file, 'r', encoding='utf-8') as f:
                cities = f.readlines()
        except FileNotFoundError:
            logger.error(f"File {cities_file} not found")
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
                json_file = f"{base_filename}.json"
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(self.pharmacies_data, f, ensure_ascii=False, indent=2)
                saved_files.append(json_file)
                logger.info(f"✓ JSON saved: {json_file}")
            
            # Save as CSV
            if save_csv:
                csv_file = f"{base_filename}.csv"
                df.to_csv(csv_file, index=False, encoding='utf-8')
                saved_files.append(csv_file)
                logger.info(f"✓ CSV saved: {csv_file}")
            
            # Save as Excel (optional)
            if save_excel:
                try:
                    excel_file = f"{base_filename}.xlsx"
                    df.to_excel(excel_file, index=False, engine='openpyxl')
                    saved_files.append(excel_file)
                    logger.info(f"✓ Excel saved: {excel_file}")
                except ImportError:
                    logger.warning("Excel export requires 'openpyxl'. Install with: pip install openpyxl")
                except Exception as e:
                    logger.warning(f"Could not save Excel file: {e}")
            
            # Also save formatted JSON for your original script compatibility
            original_json = f"{base_filename}_original_format.json"
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
        print(f"📁 Files saved:")
        for file in saved_files:
            print(f"   ✓ {file}")
        
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
        
        print(f"\n✨ Ready to use! Check the generated files.")
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
        base_filename = f"pharmacies_{output_suffix}"
        
        # Temporarily store filtered data
        original_data = self.pharmacies_data
        self.pharmacies_data = filtered_data
        
        self.save_data(base_filename)
        
        # Restore original data
        self.pharmacies_data = original_data
        
        logger.info(f"Filtered data saved: {len(filtered_data)} pharmacies")
    
    def test_single_city(self, city_input=None):
        """Test scraping for a single city - useful for debugging"""
        if not city_input:
            city_input = "essaouira"  # Default test city
            
        logger.info(f"Testing single city: {city_input}")
        
        pharmacies = self.extract_pharmacy_links_from_listing(city_input)
        
        if pharmacies:
            logger.info(f"Found {len(pharmacies)} pharmacies")
            for i, pharmacy in enumerate(pharmacies[:3], 1):  # Show first 3
                logger.info(f"  {i}. {pharmacy['name']} - {pharmacy.get('phone', 'No phone')}")
                
            # Test detailed scraping for first pharmacy
            if pharmacies and pharmacies[0].get('href'):
                detailed = self.get_detailed_pharmacy_info(pharmacies[0])
                logger.info(f"Detailed data sample: {detailed}")
        else:
            logger.warning("No pharmacies found")
        
        return pharmacies

def main():
    scraper = AnnuairePharmacyScraper()
    
    # Check command line arguments or ask user
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        # Test mode with a single city
        test_city = "essaouira"  # Default
        if len(sys.argv) > 2:
            test_city = sys.argv[2]
        
        print(f"Testing with city: {test_city}")
        scraper.test_single_city(test_city)
        return
    
    # Normal scraping mode
    cities_file = 'href.txt'
    
    try:
        with open(cities_file, 'r', encoding='utf-8') as f:
            cities_count = len(f.readlines())
        logger.info(f"Found {cities_count} cities in {cities_file}")
    except FileNotFoundError:
        logger.error(f"Please create {cities_file} with city names like:")
        logger.error("  essaouira")
        logger.error("  casablanca")  
        logger.error("  rabat")
        logger.error("  marrakech")
        logger.error("  (one city name per line)")
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