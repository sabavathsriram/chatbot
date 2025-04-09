import requests
from bs4 import BeautifulSoup
import os

# Base URL
base_url = "https://kmit.in/department"

# Department URLs
departments = {
    "CSE": "faculty_CSE.php",
    "IT": "faculty_it.php",
    "CSM": "faculty_csm.php",
    "CSD": "faculty_csd.php"
}

# Create folder
os.makedirs("KMIT_Faculty_Data", exist_ok=True)

# Headers
headers = {"User-Agent": "Mozilla/5.0"}

# Scraping function
def scrape_faculty(department, url_suffix):
    url = f"{base_url}/{url_suffix}"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.find_all("tr")
        faculty_info = []

        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 2:
                name = cols[0].get_text(strip=True)
                designation = cols[1].get_text(strip=True)
                faculty_info.append(f"{name} - {designation}")

        with open(f"KMIT_Faculty_Data/{department}_Faculty.txt", "w", encoding="utf-8") as file:
            for faculty in faculty_info:
                file.write(faculty + "\n")
        print(f"{department} faculty data saved successfully.")
    else:
        print(f"Failed to scrape {department} faculty.")

# Run scraping
for dept, url in departments.items():
    scrape_faculty(dept, url)

print("✅ All faculty data scraped and saved!")
