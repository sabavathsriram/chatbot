import requests
from bs4 import BeautifulSoup
import os

# Research pages dictionary
research_pages = {
    "Research_Overview": "https://kmit.in/research/research.php",
    "Incubation_Center": "https://kmit.in/research/incubationcenter.php",
    "Research_Labs": "https://kmit.in/research/researchlabs.php",
    "Publications_Committee": "https://kmit.in/research/publications_committee.php",
    "Publication_Policy": "https://kmit.in/research/publication-policy.php"
}

# Directory to store data
os.makedirs("KMIT_Data/Research", exist_ok=True)

# Function to scrape and save research details
def scrape_research(name, url):
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)

        if response.status_code != 200:
            print(f"❌ Failed to access {name}: {url}")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        text_content = soup.get_text(separator="\n", strip=True)

        # Save extracted text to a file
        filename = f"KMIT_Data/Research/{name}.txt"
        with open(filename, "w", encoding="utf-8") as file:
            file.write(text_content)

        print(f"✅ Saved {name} details successfully!")

    except Exception as e:
        print(f"🚨 Error scraping {name}: {e}")

# Run the scraping function for each research page
for name, url in research_pages.items():
    scrape_research(name, url)

print("🎉 All research data has been scraped and stored successfully!")
