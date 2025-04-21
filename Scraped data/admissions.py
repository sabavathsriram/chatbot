import requests
from bs4 import BeautifulSoup
import os

# URLs to scrape
admission_pages = {
    "Courses_Offered": "https://kmit.in/admissions/coursesoffered.php",
    "Admission_Procedure": "https://kmit.in/admissions/admission-procedure.php"
}

# Directory to store data
os.makedirs("KMIT_Data/Admissions", exist_ok=True)

# Function to scrape and save text content
def scrape_admissions():
    for filename, url in admission_pages.items():
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)

            if response.status_code != 200:
                print(f"❌ Failed to access: {url}")
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            text_content = soup.get_text(separator="\n", strip=True)

            # Save extracted text to a file
            file_path = f"KMIT_Data/Admissions/{filename}.txt"
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(text_content)

            print(f"✅ {filename} details saved successfully!")

        except Exception as e:
            print(f"🚨 Error scraping {filename}: {e}")

# Run the scraping function
scrape_admissions()

print("🎉 All admission-related data has been scraped and stored successfully!")
