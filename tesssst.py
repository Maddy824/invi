import http.client
import urllib
import json

conn = http.client.HTTPSConnection("api.webscraping.ai")

# 1. Getting the guest token

# Updated token
auth_header = 'Bearer AAAAAAAAAAAAAAAAAAAAAO6zqAEAAAAAOZ8HEcBBWtBoscX8NJHbmleb5LA%3DSqFf6mSrWbUludsz10O6PGKwqQuHTdBNdqcSEXcmqVUMRSusyG'

api_params = {
  'api_key': 'test-api-key',
  'js': 'false',
  'timeout': 25000,
  'url': 'https://api.twitter.com/1.1/guest/activate.json',
  'headers[Authorization]': auth_header
}
conn.request("POST", f"/html?{urllib.parse.urlencode(api_params)}")

res = conn.getresponse()
json_raw = res.read().decode("utf-8")
json_object = json.loads(json_raw)

if 'guest_token' in json_object:
    quest_token = json_object['guest_token']
    print("Using guest token: " + quest_token)
else:
    print("Guest token not found in the response:")
    print(json.dumps(json_object, indent=1))
    exit()

twitter_params = {
  'q': 'test',
  'count': 100,
  # 'cursor': '',
  'include_want_retweets': 1,
  'include_quote_count': 'true',
  'include_reply_count': 1,
  'tweet_mode': 'extended',
  'include_entities': 'true',
  'include_user_entities': 'true',
  'simple_quoted_tweet': 'true',
  'tweet_search_mode': 'live',
  'query_source': 'typed_query'
}

api_params = {
  'api_key': 'test-api-key',
  'js': 'false',
  'timeout': 25000,
  'url': 'https://api.twitter.com/2/search/adaptive.json?' + urllib.parse.urlencode(twitter_params),
  'headers[Authorization]': auth_header,
  'headers[X-Guest-Token]': quest_token
}
conn.request("GET", f"/html?{urllib.parse.urlencode(api_params)}")

res = conn.getresponse()
json_raw = res.read().decode("utf-8")
json_object = json.loads(json_raw)

print(json.dumps(json_object, indent=1))