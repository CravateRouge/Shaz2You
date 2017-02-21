from requests_oauthlib import OAuth2Session
from bs4 import BeautifulSoup
import json, re

# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret. You can acquire an OAuth 2.0 client ID and client secret from
# the Google API Console at
# https://console.developers.google.com/.
# Please ensure that you have enabled the YouTube Data API for your project.
# For more information about using OAuth2 to access the YouTube Data API, see:
#   https://developers.google.com/youtube/v3/guides/authentication
# For more information about the client_secrets.json file format, see:
#   https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
CLIENT_SECRETS_FILE = "client_secret.json"

# This variable defines a message to display if the CLIENT_SECRETS_FILE is
# missing.
MISSING_CLIENT_SECRETS_MESSAGE = """
WARNING: Please configure OAuth 2.0

To make this sample run you will need to populate the client_secrets.json file
found in the same directory as this script 

with information from the API Console
https://console.developers.google.com/

For more information about the client_secrets.json file format, please visit:
https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
"""

#Lists all the tags like they must be for searching
def listify(webPage):
	soup = BeautifulSoup(open('My Shazam - Shazam.htm'), 'html.parser')
	tags = set()
	for div in soup.find_all('div', class_='details'):
		artiste = div.find(class_='artist')
		titre  = div.find(class_='title')
		if(artiste and titre):
			formatedStr = searchFormatting(artiste) + '+' +searchFormatting(titre)	
			tags.add(formatedStr)
	
	return tags

#Formats strings for a youtube search
def  searchFormatting(terme):
	newTerme = re.sub(r'\W', '+', terme.get_text())
	newTerme = re.sub(r'\+{2,}','+',newTerme)
	newTerme = re.sub(r'\+$','', newTerme)
	return re.sub(r'^\+','', newTerme)


def authYoutube(config_auth):
	
	config_auth = config_auth['installed']
	client_id = config_auth['client_id']
	client_secret = config_auth['client_secret']
	redirect_uri = config_auth['redirect_uris'][0]
	authorization_base_url = config_auth['auth_uri']
	token_url = config_auth['token_uri']
	scope = [r'https://www.googleapis.com/auth/youtube']

	oauth = OAuth2Session(client_id, redirect_uri=redirect_uri,
		                  scope=scope)
	authorization_url, state = oauth.authorization_url(
		authorization_base_url,
		# access_type and approval_prompt are Google specific extra
		# parameters.
		access_type="offline", approval_prompt="force")

	print('Please go to '+authorization_url+' and authorize access.')
	user_code = input('Enter the code\n')
	token = oauth.fetch_token(token_url, client_secret=client_secret, code=user_code)
	
	return oauth;

def add2Playlist(shazTags, oauth):
	PLAYLIST_ID = input('Enter the playlist ID. You can get it from the field id=... in the url of the main page of the playlist. \n')
	failedInserts = []
	alreadyAdded = retrievePlaylistVideos(PLAYLIST_ID, oauth)

	for videoName in shazTags:
		#Searchs the video id with the YoutubeAPI
		search=oauth.get('https://www.googleapis.com/youtube/v3/search', params={'part':'id', 'q':videoName, 'type':'video', 'maxResults':'1'})
		items = search.json()['items']

		#If the search request returns an error
		if(search.status_code >= 400):
			failedInserts.append(printLog(videoName,search_status=search.status_code))
			continue
		
		#If the search doesn't return a result
		if(len(items)<1):
			search = oauth.get('https://www.youtube.com/results',params={'search_query':videoName})
			soup = BeautifulSoup(search.text, 'html.parser')
			videoDiv= soup.select_one('div.yt-lockup.yt-lockup-tile.yt-lockup-video.clearfix')
			
			#Checks if the second search returns a result
			if(videoDiv):
				videoId = videoDiv['data-context-item-id']
			else:
				failedInserts.append(printLog(videoName))
				continue

		else:
			videoId = items[0]['id']['videoId']

		#Checks if the video is already added
		if not videoId in alreadyAdded:
			#Inserts the video into the playlist
			insertion=oauth.post('https://www.googleapis.com/youtube/v3/playlistItems', params={'part':'snippet'}, json={'snippet':
				{'playlistId':PLAYLIST_ID, 'resourceId':
					{'kind':'youtube#video', 'videoId':videoId}}})
			#If the insertion request returns an error		
			if(insertion.status_code >= 400):
						failedInserts.append(printLog(videoName,insertion_status=insertion.status_code))

	return failedInserts

#Retrieves videos already added in the playlist
def retrievePlaylistVideos(PLAYLIST_ID, oauth, nextPage=None):
	params = {'part':'snippet','maxResults':'50','playlistId':PLAYLIST_ID}
	if(nextPage):
		params['pageToken'] = nextPage

	rp = oauth.get('https://www.googleapis.com/youtube/v3/playlistItems', params=params)
	playlist = rp.json()
	ids = [item['snippet']['resourceId']['videoId'] for item in playlist['items']]
	if 'nextPageToken' in playlist:
		ids = ids + retrievePlaylistVideos(PLAYLIST_ID, oauth, nextPage=playlist['nextPageToken'])

	return ids

#Returns logs correctly
def printLog(videoName,search_status=None,insertion_status=None):
	return {'search_status':search_status, 'insertion_status':insertion_status,'video_name':videoName}

#Gets the config for authentification
with open(CLIENT_SECRETS_FILE) as fp:
	config_auth = json.load(fp)
#Gets tags and adds them to a playlist
with open('My Shazam - Shazam.htm') as wp:
	failedInserts = add2Playlist(listify(wp), authYoutube(config_auth))

#Adds non paylisted videos to log
if(len(failedInserts)>0):
	with open('shazFailed.txt', 'a') as failures:
		json.dump(failedInserts, failures, indent=0)
