import requests
def fetchAndSaveToFile(url,path):
    r=requests.get(url)
    with open(path,"w") as f:
        f.write(r.text)
url="https://www.kmit.in/"
fetchAndSaveToFile(url,"data/Dataset.html")