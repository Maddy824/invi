from googleapiclient.discovery import build

# Set up your YouTube API key
api_key = 'AIzaSyDDHkREBaQ78ggOUFz6sUJVK9zJxUwCYDQ'

# Build the YouTube API service
youtube = build('youtube', 'v3', developerKey=api_key)

# Example: Search for videos by a specific keyword
search_query = 'your search query'
search_response = youtube.search().list(
    q=search_query,
    type='video',
    part='id,snippet'
).execute()

# Print the titles, likes, and views of the videos in the search results
for search_result in search_response.get('items', []):
    video_id = search_result['id']['videoId']
    video_response = youtube.videos().list(
        part='statistics',
        id=video_id
    ).execute()
    
    # Get the statistics for the video
    statistics = video_response['items'][0]['statistics']
    
    title = search_result['snippet']['title']
    likes = statistics['likeCount']
    views = statistics['viewCount']
    
    print(f"Title: {title}")
    print(f"Video ID: {video_id}")
    print(f"Likes: {likes}")
    print(f"Views: {views}")
    print("\n")
