# The Colorado Sound Playlist Bot V2

This is a bot that posts the current song playing on KJAC 105.5 FM, The Colorado Sound, to Mastodon. It also follows the "Buy on iTunes" link on their playlist site, https://coloradosound.org/colorado-sound-playlist/ , and posts the album art if available.

You can view the playlist posts here: https://mastodon.social/@the_colorado_sound_playlist

This is completely unofficial. I'm not affiliated with The Colorado Sound in any way (other than being a member). They're a great station. You should definitely check them out and support them! I do.

Originally I was using the iTunes link in The Colorado Sound's stream API to grab the album artwork. That broke some time ago. So I now use my own local API which currently wraps the LastFM API to get the album art from LastFM. That code is here: https://github.com/wirtes/album-art-api My code is sloppy & experimental, but it works. LastFM's API is very robust. And it includes an important feature that corrects for common misspellings and variations in artist names. It's been surprisingly accurate. I'm working on additional utility APIs in this project, such as fetching an album name from LastFM when the official playlist only lists artist and song. 