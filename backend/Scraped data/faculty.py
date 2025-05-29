import requests
from bs4 import BeautifulSoup
import csv

# URL of the CSE Faculty page
url = "https://kmit.in/department/faculty_CSE.php"

# Headers to simulate a real browser request
headers = {"User-Agent": "Mozilla/5.0"}

# Function to scrape faculty data
def scrape_cse_faculty():
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("❌ Failed to access the webpage")
        return

    soup = BeautifulSoup(response.text, "html.parser")

    # Find the faculty table
    faculty_table = soup.find("table")  # Assuming data is inside a <table>
    if not faculty_table:
        print("❌ No table found on the webpage!")
        return

    # Extract table rows
    rows = faculty_table.find_all("tr")

    # Open CSV file to store data
    with open("CSE_FACULTY.csv", "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        # Extract header from the first row
        header = [th.get_text(strip=True) for th in rows[0].find_all("th")]
        writer.writerow(header)  # Write header row

        # Extract faculty data
        for row in rows[1:]:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            writer.writerow(cols)

    print("✅ CSE Faculty data saved successfully as 'CSE_FACULTY.csv'!")

# Run the scraping function
scrape_cse_faculty()
