import requests
from bs4 import BeautifulSoup
import os

# List of initiatives and their respective URLs
initiatives = {
    "Trishul": "https://kmit.in/intiatives/trishul.php",
    "Arjuna": "https://kmit.in/intiatives/arjuna.php",
    "Sonet": "https://kmit.in/intiatives/sonet.php",
    "BEC": "https://kmit.in/intiatives/bec.php",
    "NFS": "https://kmit.in/intiatives/nfs.php",
    "Project-School": "https://kmit.in/intiatives/project-school.php",
    "International_Finishing_School": "https://kmit.in/intiatives/International%20finishing-school.php",
    "Imagineering_School": "https://kmit.in/intiatives/imagineering-school.php"
}

# Directory to store data
os.makedirs("KMIT_Data/Initiatives", exist_ok=True)

# Function to scrape and save initiative data
def scrape_initiative(name, url):
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Failed to access {name}: {url}")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        text_content = soup.get_text(separator="\n", strip=True)

        # Save the extracted text
        filename = f"KMIT_Data/Initiatives/{name}.txt"
        with open(filename, "w", encoding="utf-8") as file:
            file.write(text_content)
        
        print(f"✅ Saved {name} details successfully!")
    
    except Exception as e:
        print(f"🚨 Error scraping {name}: {e}")

# Run the scraping function for each initiative
for name, url in initiatives.items():
    scrape_initiative(name, url)

print("🎉 All initiative data has been scraped and stored successfully!")
