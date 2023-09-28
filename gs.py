import requests_html
from selenium import webdriver
from selenium.webdriver.common.by import By
from pprint import pprint
import json
from selenium_stealth import stealth

usernames = ["jlo"]
proxy = "127.0.0.10:80"
output = {}

def main():
    for username in usernames:
        scrape(username)

def prepare_browser():
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument(f'--proxy-server={proxy}')
    chrome_options.add_argument("start-maximized")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    driver = webdriver.Chrome(options= chrome_options)
    stealth(driver,
            user_agent= 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.53 Safari/537.36',
            languages= ["en-US", "en"],
            vendor=  "Google Inc.",
            platform=  "Win32",
            webgl_vendor=  "Intel Inc.",
            renderer=  "Intel Iris OpenGL Engine",
            fix_hairline= False,
            run_on_insecure_origins= False,
            )
    return driver


def scrape(username):
  url = f'https://instagram.com/{username}/?__a=1&__d=dis'
  response = requests_html.HTMLSession().get(url)

  # Check the response code
  if response.status_code != 200:
    print(f"Error: {response.status_code} response for {username}")
    return

  # Parse the JSON response
  try:
    data_json = response.json()
    user_data = data_json['graphql']['user']
    parse_data(username, user_data)
  except json.decoder.JSONDecodeError:
    print(f"Error: Could not decode JSON for {username}")
def parse_data(username, user_data):
  captions = []
  if len(user_data['edge_owner_to_timeline_media']['edges']) > 0:
    for node in user_data['edge_owner_to_timeline_media']['edges']:
      if len(node['node']['edge_media_to_caption']['edges']) > 0:
        if node['node']['edge_media_to_caption']['edges'][0]['node']['text']:
          captions.append(node['node']['edge_media_to_caption']['edges'][0]['node']['text'])

  try:
    output[username] = {
      'name': user_data['full_name'],
      'category': user_data['category_name'],
      'followers': user_data['edge_followed_by']['count'],
      'posts': captions,
    }
  except json.decoder.JSONDecodeError:
    print(f"Error: Could not decode JSON for {username}")

if __name__ == '__main__':
    main()
    pprint(output)