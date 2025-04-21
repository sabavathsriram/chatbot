import requests
from bs4 import BeautifulSoup
import os

# Base URL
base_url = "https://kmit.in"

# Headers to avoid blocking
headers = {"User-Agent": "Mozilla/5.0"}

# Pages to scrape
pages = {
    "LMS": "/uniqueness/lms.php",
    "Tessellator": "/uniqueness/tessellator.php",
    "TeleUniv": "/uniqueness/teleuniv.php",
    "KMIT_TV": "/uniqueness/kmit_tv.php",
    "ICT": "/uniqueness/ict.php",
}

# Directory to save data
os.makedirs("KMIT_Data/Uniqueness", exist_ok=True)

# Function to scrape and save page content
def scrape_page(name, page_url):
    print(f"Scraping {name} page...")

    response = requests.get(base_url + page_url, headers=headers)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Extract clean text
        page_text = soup.get_text(separator="\n", strip=True)
        
        # Save text into a file
        file_path = f"KMIT_Data/Uniqueness/{name}.txt"
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(page_text)
        
        print(f"✅ Saved: {name}.txt")
    
    else:
        print(f"❌ Failed to scrape {name} page.")

# Run the scraper for all uniqueness pages
for page_name, url in pages.items():
    scrape_page(page_name, url)

print("🎉 All uniqueness pages scraped and saved successfully!")
