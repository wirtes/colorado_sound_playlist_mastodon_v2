#!/usr/bin/python

import time
import sys
import json
import requests
from mastodon import Mastodon
from datetime import datetime
from pprint import pprint


# Writes the state file
def write_state(file_path, id):
	with open(file_path, 'w') as file:
		file.write(id.strip())
	return


# Reads the state from the state file
def read_state(file_path):
	try:
		with open(file_path, 'r') as file:
			state = file.readline().strip()  # Read the first line and remove leading/trailing whitespace
	# If it fails, we don't have a state file yet. So make one.
	except:
		state = "starting up"
		write_state(file_path, state)
	return state
	

# Loads the configuration file. Do all config in ./config/config.json & exclude from repo.
def get_config(working_directory):
	try:
		with open(working_directory + '/config/config.json', 'r') as file:
			data = json.load(file)
		return data
	except FileNotFoundError:
		print("Config file not found.")
	except json.JSONDecodeError as e:
		print(f"JSON decoding error: {e}")
	except Exception as e:
		print(f"An error occurred: {e}")


def convert_seconds_to_time(epoch_seconds):
		# Convert seconds since the epoch to a datetime object
		dt = datetime.fromtimestamp(epoch_seconds)
		
		# Format the datetime to H:MMp (e.g., 3:45p for 3:45 PM)
		time_str = dt.strftime("%I:%M%p").lstrip("0").lower()  # Remove leading zero and convert AM/PM to lowercase
		return time_str


def fetch_current_song(uri):
	now_playing = {}
	try:
		response = requests.get(uri)
		response.raise_for_status()  # Raise an error for HTTP errors
		metadata = response.json()
		metadata = metadata[0]	
		# pprint(metadata)
		now_playing["album"] = metadata.get("TALB", "N/A")
		now_playing["song"] = metadata.get("TIT2", "N/A")
		now_playing["artist"] = metadata.get("TPE1", "N/A")	
		now_playing["album_art"] = metadata.get("WXXX_album_art", "N/A")
		now_playing["song_id"] = now_playing["song"] + "_" + now_playing["artist"]
		time_played = metadata.get("played_on", "N/A")
		if time_played != "N/A":
			now_playing["time_played"] = convert_seconds_to_time(time_played)
		if now_playing["album_art"] != "N/A":
			# This feels sleazy, but it's an effective way to download a useful resolution image.
			now_playing["album_art"] = now_playing["album_art"].replace("170x170", "900x900")
		now_playing["status"] = "success"
	
	except requests.exceptions.RequestException as e:
		print(f"Error fetching metadata: {e}")
		now_playing["status"] = f"Error fetching metadata: {e}"
	except ValueError:
		print("Error parsing JSON response.")
		now_playing["status"] = "Error parsing JSON response."
	# pprint(now_playing)
	return now_playing
	

def is_safe_to_post(now_playing):
	last_song_id = read_state(now_playing["state_file"])
	if last_song_id == now_playing["song_id"]:
		safe_to_post = False
	else:
		safe_to_post = True
	return safe_to_post


# Get the artwwork
def fetch_image(url):
	result = {"status": "", "image_data": None}
	try:
		response = requests.get(url, stream=True)
		response.raise_for_status()  # Raise an error for HTTP errors
		# Store binary data
		result["image_data"] = response.content
		result["status"] = "Success"
	except requests.exceptions.RequestException as e:
		result["status"] = f"Error fetching image: {e}"
	return result


# Your standard posting to Mastodon function
def post_to_mastodon(config, current_song):
	# Create an app on your Mastodon instance and get the access token
	mastodon = Mastodon(
		access_token=config["mastodon_access_token"],
		api_base_url=config["mastodon_server"]
	)
	# Text content to post
	text_to_post = current_song["time_played"] + " " + current_song["song"] + " by " + current_song["artist"] + " from " + current_song["album"] + "\n" + config["hashtags"]
	alt_text = "An image of the cover of the album '" + current_song["album"] + "' by " + current_song["artist"]	
	album_art_api_result = fetch_image(current_song["album_art"])
	# If we successfully got a cover image, process it
	if album_art_api_result["image_data"]:
		image_data = album_art_api_result["image_data"]
		# Upload the image and attach it to the status
		media = mastodon.media_post(image_data, mime_type='image/jpeg', description=alt_text)
		# Post the status with text and image attachment
		mastodon.status_post(status=text_to_post, media_ids=[media['id']], visibility="public")
	else:
		mastodon.status_post(status=text_to_post, visibility="public")

	print(f"***** Posted: {text_to_post}")
	return


def post_to_mastodon_preflight(config, now_playing):
	if (is_safe_to_post(now_playing)):
		# print("Safe To Post")
		post_to_mastodon(config, now_playing)
		# Do last. We'll miss fewer songs in case of crash.
		write_state(now_playing["state_file"], now_playing["song_id"])
	# else:
		print("Already Posted Song")
	return
	
	

if __name__ == "__main__":
	# print("\n\n***** Launching Colorado Sound Playlist Bot *****\n")
	if len(sys.argv) > 1:
		working_directory = sys.argv[1]
		# print (f"{working_directory} provided as working directory.")
		config = get_config(working_directory)
	else:
		print("No working directory argument provided. Exiting.\n")
		sys.exit()
	
	# For a variety of reasons, this script is kicked off by a cron job that runs every minute.
	# But we want to check for new songs more frequently that once a minute. So we have a configuration
	# value times_to_poll_per_minute. This loops the number of times specified by that value.
	# It sounds hokey, but it's simple and stable as heck.
	for i in range(0, config["times_to_poll_per_minute"] ):
		now_playing = fetch_current_song(config["plalist_uri"])
		# Stick the working directory into the now_playing array to simplify calling functions
		now_playing["working_directory"] = working_directory
		now_playing["state_file"] = working_directory + "/last_mastodon_post"
		if now_playing["status"] == "success":
			# We successfully got the track info. Let's see how good it is:
			if now_playing["song"] == "The Colorado Sound":
				# This is what a voice break returns from the API:
				# {'album': '', 'album_art': '', 'artist': '', 'song': 'The Colorado Sound'}
				print("*** Voice break. Do nothing.")
			elif len(now_playing["artist"]) > 0 and len(now_playing["album"]) == 0:
				# We're waiting for album art in the feed
				print("*** Pausing 10 seconds for album art to catch up")
				time.sleep(10)
				now_playing_second_try = fetch_current_song(config["plalist_uri"])
				post_to_mastodon_preflight(config, now_playing)
			else:
				# We must be ready to POST
				# print("Posting to Mastodon " + now_playing["song"] + " " + now_playing["artist"] + " " + now_playing["album"] + " ")
				post_to_mastodon_preflight(config, now_playing)
		# print("=====")
		if i < (config["times_to_poll_per_minute"] - 1):
			time.sleep(60/config["times_to_poll_per_minute"])
		