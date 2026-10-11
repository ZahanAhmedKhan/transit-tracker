import requests

url = "https://api.github.com/repos/python/cpython"
response = requests.get(url)
data = response.json()

print(response.status_code)
print(data["name"])
print(data["stargazers_count"])
