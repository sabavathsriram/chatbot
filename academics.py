import requests
from bs4 import BeautifulSoup
import os

# Dictionary of academic pages
academic_pages = {
    "Regulations": "https://kmit.in/academics/regulations.php",
    "Value_Added_Services": "https://kmit.in/academics/value-%20addedservices.php",
    "Endowment_Awards": "https://kmit.in/academics/endowment-awards.php",
    "Teaching_Learning_Evaluation": "https://kmit.in/academics/tlevaluation.php"
}

# Directory to store data
os.makedirs("KMIT_Data/Academics", exist_ok=True)

# Function to scrape and save academic details
def scrape_academic(name, url):
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)

        if response.status_code != 200:
            print(f"❌ Failed to access {name}: {url}")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        text_content = soup.get_text(separator="\n", strip=True)

        # Save extracted text to a file
        filename = f"KMIT_Data/Academics/{name}.txt"
        with open(filename, "w", encoding="utf-8") as file:
            file.write(text_content)

        print(f"✅ Saved {name} details successfully!")

    except Exception as e:
        print(f"🚨 Error scraping {name}: {e}")

# Run the scraping function for each academic page
for name, url in academic_pages.items():
    scrape_academic(name, url)

print("🎉 All academic data has been scraped and stored successfully!")
