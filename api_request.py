import requests

# your host credentials
IP = 'HOST IP ADDRESS'
port = 8080

url = f'http://{IP}:{port}/'

# request data
data = requests.post(url, json={}).json()
print(data)