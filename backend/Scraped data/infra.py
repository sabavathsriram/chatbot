import requests
from bs4 import BeautifulSoup
import os

# Infrastructure pages
infrastructure_pages = {
    "Library": "https://kmit.in/infrastructure/aboutLib.php",
    "Sports_Facilities": "https://kmit.in/infrastructure/sportsfacilities.php"
}

# Directory to store data
os.makedirs("KMIT_Data/Infrastructure", exist_ok=True)

# Function to scrape and save infrastructure details
def scrape_infrastructure(name, url):
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Failed to access {name}: {url}")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        text_content = soup.get_text(separator="\n", strip=True)

        # Save the extracted text
        filename = f"KMIT_Data/Infrastructure/{name}.txt"
        with open(filename, "w", encoding="utf-8") as file:
            file.write(text_content)
        
        print(f"✅ Saved {name} details successfully!")
    
    except Exception as e:
        print(f"🚨 Error scraping {name}: {e}")

# Run the scraping function for each infrastructure page
for name, url in infrastructure_pages.items():
    scrape_infrastructure(name, url)

print("🎉 All infrastructure data has been scraped and stored successfully!")
