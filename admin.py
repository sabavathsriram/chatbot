import requests
from bs4 import BeautifulSoup
import os

# URLs to scrape
admin_research_pages = {
    "Perspective_Plan": "https://kmit.in/administration/perspectiveplan.php",
    "Management": "https://kmit.in/administration/management.php",
    "Principal": "https://kmit.in/administration/principal.php",
    "HODs": "https://kmit.in/administration/hod.php",
    "AAC": "https://kmit.in/administration/aac.php",
    "IIC": "https://kmit.in/research/iic.php",
    "Other_Committees": "https://kmit.in/administration/othercommittees.php",
    "IDMC": "https://kmit.in/administration/idmc.php",
    "HR_Policy": "https://kmit.in/administration/hrpolicy.php"
}

# Directory to store data
os.makedirs("KMIT_Data/Administration", exist_ok=True)

# Function to scrape and save text content
def scrape_administration():
    for filename, url in admin_research_pages.items():
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)

            if response.status_code != 200:
                print(f"❌ Failed to access: {url}")
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            text_content = soup.get_text(separator="\n", strip=True)

            # Save extracted text to a file
            file_path = f"KMIT_Data/Administration/{filename}.txt"
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(text_content)

            print(f"✅ {filename} details saved successfully!")

        except Exception as e:
            print(f"🚨 Error scraping {filename}: {e}")

# Run the scraping function
scrape_administration()

print("🎉 All Administration & Research data has been scraped and stored successfully!")
