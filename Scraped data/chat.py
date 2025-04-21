# import requests
# from bs4 import BeautifulSoup

# # URL of KMIT website
# url = "https://www.kmit.in/"

# # Sending a request to fetch the page
# headers = {"User-Agent": "Mozilla/5.0"}
# response = requests.get(url, headers=headers)

# # Check if request was successful
# if response.status_code == 200:
#     # Parse the HTML content
#     soup = BeautifulSoup(response.text, "html.parser")

#     # Extract all links
#     links = soup.find_all("a")
#     print("Links Found on KMIT Website:")
#     for link in links:
#         href = link.get("href")
#         if href:
#             print(href)
# else:
#     print(f"Failed to retrieve the website. Status Code: {response.status_code}")


# import requests
# from bs4 import BeautifulSoup
# import csv

# # Base URL of KMIT
# base_url = "https://www.kmit.in"

# # Sending request to fetch the page
# headers = {"User-Agent": "Mozilla/5.0"}
# response = requests.get(base_url, headers=headers)

# if response.status_code == 200:
#     soup = BeautifulSoup(response.text, "html.parser")
#     links = soup.find_all("a")

#     # Store unique links
#     internal_links = set()
#     external_links = set()

#     for link in links:
#         href = link.get("href")
#         if href:
#             if href.startswith("http"):  # External Links
#                 external_links.add(href)
#             elif href.startswith("/") and not href.startswith("//"):  # Internal Links
#                 internal_links.add(base_url + href)

#     # Save to CSV file
#     with open("kmit_links.csv", "w", newline="", encoding="utf-8") as file:
#         writer = csv.writer(file)
#         writer.writerow(["Type", "URL"])
#         for link in sorted(internal_links):
#             writer.writerow(["Internal", link])
#         for link in sorted(external_links):
#             writer.writerow(["External", link])

#     print(f"Saved {len(internal_links) + len(external_links)} links to 'kmit_links.csv'.")

# else:
#     print(f"Failed to retrieve website. Status Code: {response.status_code}")


# import requests
# from bs4 import BeautifulSoup
# import csv
# import os

# # Base KMIT URL
# base_url = "https://www.kmit.in"

# # Headers to avoid blocking
# headers = {"User-Agent": "Mozilla/5.0"}

# # Directory for saving data
# os.makedirs("KMIT_Data", exist_ok=True)

# # Function to save data into CSV
# def save_to_csv(filename, data, headers):
#     with open(f"KMIT_Data/{filename}", "w", newline="", encoding="utf-8") as file:
#         writer = csv.writer(file)
#         writer.writerow(headers)
#         writer.writerows(data)

# # Function to scrape faculty details
# def scrape_faculty(department):
#     url = f"{base_url}/department/faculty_{department}.php"
#     response = requests.get(url, headers=headers)
    
#     if response.status_code == 200:
#         soup = BeautifulSoup(response.text, "html.parser")
#         faculty_data = []
#         faculty_rows = soup.find_all("tr")

#         for row in faculty_rows:
#             cols = row.find_all("td")
#             if len(cols) >= 2:
#                 name = cols[0].get_text(strip=True)
#                 designation = cols[1].get_text(strip=True)
#                 faculty_data.append([name, designation])

#         save_to_csv(f"{department}_faculty.csv", faculty_data, ["Name", "Designation"])
#         print(f"Saved {len(faculty_data)} faculty members for {department}.")
#     else:
#         print(f"Failed to scrape {department} faculty.")

# # Function to scrape admission details
# def scrape_admissions():
#     url = f"{base_url}/admissions/admission-procedure.php"
#     response = requests.get(url, headers=headers)
    
#     if response.status_code == 200:
#         soup = BeautifulSoup(response.text, "html.parser")
#         admission_text = soup.get_text(separator="\n", strip=True)
        
#         with open("KMIT_Data/admissions.txt", "w", encoding="utf-8") as file:
#             file.write(admission_text)
#         print("Saved admission details.")
#     else:
#         print("Failed to scrape admissions.")

# # Function to scrape placements
# def scrape_placements():
#     url = f"{base_url}/placements/placement.php"
#     response = requests.get(url, headers=headers)
    
#     if response.status_code == 200:
#         soup = BeautifulSoup(response.text, "html.parser")
#         placement_text = soup.get_text(separator="\n", strip=True)
        
#         with open("KMIT_Data/placements.txt", "w", encoding="utf-8") as file:
#             file.write(placement_text)
#         print("Saved placement details.")
#     else:
#         print("Failed to scrape placements.")

# # Function to scrape research publications
# def scrape_research():
#     url = f"{base_url}/research/researchpublications.php"
#     response = requests.get(url, headers=headers)
    
#     if response.status_code == 200:
#         soup = BeautifulSoup(response.text, "html.parser")
#         research_text = soup.get_text(separator="\n", strip=True)
        
#         with open("KMIT_Data/research.txt", "w", encoding="utf-8") as file:
#             file.write(research_text)
#         print("Saved research details.")
#     else:
#         print("Failed to scrape research.")

# # Function to scrape and download PDFs
# def scrape_pdfs():
#     url = base_url
#     response = requests.get(url, headers=headers)

#     if response.status_code == 200:
#         soup = BeautifulSoup(response.text, "html.parser")
#         pdf_links = [a["href"] for a in soup.find_all("a", href=True) if a["href"].endswith(".pdf")]

#         os.makedirs("KMIT_Data/PDFs", exist_ok=True)

#         for pdf_link in pdf_links:
#             pdf_url = pdf_link if pdf_link.startswith("http") else base_url + pdf_link
#             pdf_name = pdf_url.split("/")[-1]

#             pdf_response = requests.get(pdf_url, headers=headers)
#             if pdf_response.status_code == 200:
#                 with open(f"KMIT_Data/PDFs/{pdf_name}", "wb") as pdf_file:
#                     pdf_file.write(pdf_response.content)
#                 print(f"Downloaded {pdf_name}")
#             else:
#                 print(f"Failed to download {pdf_name}")

# # Function to scrape events
# def scrape_events():
#     url = f"{base_url}/intiatives/annualevents.php"
#     response = requests.get(url, headers=headers)

#     if response.status_code == 200:
#         soup = BeautifulSoup(response.text, "html.parser")
#         events_text = soup.get_text(separator="\n", strip=True)

#         with open("KMIT_Data/events.txt", "w", encoding="utf-8") as file:
#             file.write(events_text)
#         print("Saved event details.")
#     else:
#         print("Failed to scrape events.")

# # Run the scraping functions
# departments = ["CSE", "IT", "CSM", "CSD"]  # Add more if needed

# for dept in departments:
#     scrape_faculty(dept)

# scrape_admissions()
# scrape_placements()
# scrape_research()
# scrape_events()
# scrape_pdfs()

# print("✅ All data has been scraped and saved!")


import os
import csv
import requests
from bs4 import BeautifulSoup

# Base KMIT URL
base_url = "https://www.kmit.in"

# Headers to avoid blocking
headers = {"User-Agent": "Mozilla/5.0"}

# Directory for saving data
os.makedirs("KMIT_Data", exist_ok=True)

# Function to save data into CSV
def save_to_csv(filename, data, headers):
    with open(f"KMIT_Data/{filename}", "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerows(data)

# Function to scrape faculty details
def scrape_faculty(department):
    url = f"{base_url}/department/faculty_{department}.php"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        faculty_data = []
        faculty_rows = soup.find_all("tr")

        for row in faculty_rows:
            cols = row.find_all("td")
            if len(cols) >= 2:
                name = cols[0].get_text(strip=True)
                designation = cols[1].get_text(strip=True)
                faculty_data.append([name, designation])

        save_to_csv(f"{department}_faculty.csv", faculty_data, ["Name", "Designation"])
        print(f"✅ Saved {len(faculty_data)} faculty members for {department}.")
    else:
        print(f"❌ Failed to scrape {department} faculty.")

# Function to scrape admission details
def scrape_admissions():
    url = f"{base_url}/admissions/admission-procedure.php"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        admission_text = soup.get_text(separator="\n", strip=True)
        
        with open("KMIT_Data/admissions.txt", "w", encoding="utf-8") as file:
            file.write(admission_text)
        print("✅ Saved admission details.")
    else:
        print("❌ Failed to scrape admissions.")

# Function to scrape placements
def scrape_placements():
    url = f"{base_url}/placements/placement.php"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        placement_text = soup.get_text(separator="\n", strip=True)
        
        with open("KMIT_Data/placements.txt", "w", encoding="utf-8") as file:
            file.write(placement_text)
        print("✅ Saved placement details.")
    else:
        print("❌ Failed to scrape placements.")

# Function to scrape research publications
def scrape_research():
    url = f"{base_url}/research/researchpublications.php"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        research_text = soup.get_text(separator="\n", strip=True)
        
        with open("KMIT_Data/research.txt", "w", encoding="utf-8") as file:
            file.write(research_text)
        print("✅ Saved research details.")
    else:
        print("❌ Failed to scrape research.")

# Function to scrape and download PDFs
def scrape_pdfs():
    url = base_url
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        pdf_links = [a["href"] for a in soup.find_all("a", href=True) if a["href"].endswith(".pdf")]

        os.makedirs("KMIT_Data/PDFs", exist_ok=True)

        for pdf_link in pdf_links:
            pdf_url = pdf_link if pdf_link.startswith("http") else base_url + pdf_link
            pdf_name = pdf_url.split("/")[-1]

            pdf_response = requests.get(pdf_url, headers=headers)
            if pdf_response.status_code == 200:
                with open(f"KMIT_Data/PDFs/{pdf_name}", "wb") as pdf_file:
                    pdf_file.write(pdf_response.content)
                print(f"✅ Downloaded {pdf_name}")
            else:
                print(f"❌ Failed to download {pdf_name}")

# Function to scrape syllabus PDFs
def scrape_syllabus_pdfs():
    syllabus_url = f"{base_url}/academics/syllabus.php"
    response = requests.get(syllabus_url, headers=headers)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        pdf_links = [a["href"] for a in soup.find_all("a", href=True) if a["href"].endswith(".pdf")]

        os.makedirs("KMIT_Data/Syllabus_PDFs", exist_ok=True)

        for pdf_link in pdf_links:
            pdf_url = pdf_link if pdf_link.startswith("http") else base_url + pdf_link
            pdf_name = pdf_url.split("/")[-1]

            pdf_response = requests.get(pdf_url, headers=headers)
            if pdf_response.status_code == 200:
                with open(f"KMIT_Data/Syllabus_PDFs/{pdf_name}", "wb") as pdf_file:
                    pdf_file.write(pdf_response.content)
                print(f"✅ Downloaded Syllabus PDF: {pdf_name}")
            else:
                print(f"❌ Failed to download syllabus PDF: {pdf_name}")
    else:
        print(f"❌ Failed to load syllabus page. Status Code: {response.status_code}")

# Function to scrape events
def scrape_events():
    url = f"{base_url}/intiatives/annualevents.php"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        events_text = soup.get_text(separator="\n", strip=True)

        with open("KMIT_Data/events.txt", "w", encoding="utf-8") as file:
            file.write(events_text)
        print("✅ Saved event details.")
    else:
        print("❌ Failed to scrape events.")

# Run the scraping functions
departments = ["cse", "it", "csm", "csd"]  # Add more if needed

for dept in departments:
    scrape_faculty(dept)

scrape_admissions()
scrape_placements()
scrape_research()
scrape_events()
scrape_pdfs()
scrape_syllabus_pdfs()  # ✅ Added syllabus PDF scraping

print("🎉✅ All data has been scraped and saved successfully!")
