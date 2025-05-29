import requests
from bs4 import BeautifulSoup

# URL of the About Us page
url = "https://kmit.in/aboutus/aboutus.php"

# Headers to simulate a real browser request
headers = {"User-Agent": "Mozilla/5.0"}

# Function to scrape and save About Us content
def scrape_about_us():
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("❌ Failed to access the webpage")
        return

    soup = BeautifulSoup(response.text, "html.parser")

    # Extract all the text from the page
    about_text = soup.get_text(separator="\n", strip=True)

    # Save to a text file
    with open("about_us.txt", "w", encoding="utf-8") as file:
        file.write(about_text)

    print("✅ 'About Us' page saved successfully as 'about_us.txt'!")

# Run the scraping function
scrape_about_us()
