import requests
from bs4 import BeautifulSoup
import os
import PyPDF2
from io import BytesIO

# URL of the examination page
exam_url = "https://kmit.in/examination/exam.php"
headers = {"User-Agent": "Mozilla/5.0"}

# Directory for storing text data
exam_data_dir = "KMIT_Data/Examinations"
text_dir = f"{exam_data_dir}/TextFiles"
os.makedirs(text_dir, exist_ok=True)

# Function to extract text from PDF
def extract_text_from_pdf(pdf_url, save_path):
    try:
        response = requests.get(pdf_url, headers=headers, timeout=10, stream=True)
        content_type = response.headers.get("Content-Type", "").lower()

        if "pdf" not in content_type:
            print(f"❌ Skipping (Not a PDF): {pdf_url} (Content-Type: {content_type})")
            return

        # Read the PDF content
        pdf_reader = PyPDF2.PdfReader(BytesIO(response.content))
        extracted_text = ""

        for page in pdf_reader.pages:
            extracted_text += page.extract_text() + "\n"

        # Save extracted text
        with open(save_path, "w", encoding="utf-8") as text_file:
            text_file.write(extracted_text)
        print(f"✅ Extracted text from: {pdf_url}")

    except Exception as e:
        print(f"🚨 Error extracting text from {pdf_url}: {e}")

# Scrape the Examination page
def scrape_examinations():
    print("🔍 Scraping Examination page...")

    response = requests.get(exam_url, headers=headers)
    if response.status_code != 200:
        print("❌ Failed to access the Examination page.")
        return

    soup = BeautifulSoup(response.text, "html.parser")

    # Extract PDF links
    pdf_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full_url = href if href.startswith("http") else f"https://kmit.in/{href}"

        if ".pdf" in href.lower():
            pdf_links.append(full_url)

    # Extract and save text (excluding EAPCET/ECET)
    for pdf_link in pdf_links:
        pdf_name = pdf_link.split("/")[-1].replace(".pdf", ".txt")

        if "eapcet" in pdf_name.lower() or "ecet" in pdf_name.lower():
            print(f"⚠️ Skipping unwanted file: {pdf_name}")
            continue

        extract_text_from_pdf(pdf_link, f"{text_dir}/{pdf_name}")

scrape_examinations()
print("🎉 Examination text data scraping completed successfully!")
