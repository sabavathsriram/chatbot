from bs4 import BeautifulSoup
import requests
html=requests.get('https://kmit.in/')
print(html)