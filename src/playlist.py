import constant
import database
from collections import deque
from datetime import datetime as dt
from datetime import timezone as tz
from saved_songs import get_unadded_songs

# returns the season given a time
def get_current_season(now) -> str:
    if now.month > 2 and now.month < 6: # MAR - MAY
        return constant.SPRING
    elif now.month > 5 and now.month < 9: # JUN - AUG
        return constant.SUMMER
    elif now.month > 8 and now.month < 12: # SEPT - NOV
        return constant.FALL
    else: # DEC - FEB
        return constant.WINTER     

# returns the playlist id based on date
def get_target_playlist(date, client) -> str:
    """
    ASSUMPTIONS: a user has no duplicate playlist names
    In the case that a user has a duplicate playlist name, the script will modify the one 'lower' in the user's playlist library
    Solution: no intuitive workaround
    """
    # december of 2019 looks for playlist "winter 2020"
    target_playlist_name = get_current_season(date)+ " " + str(date.year if date.month != 12 else date.year+1)
    chunk, offset = 50, 0
    all_playlists = {}
    while True: 
        playlist_info = client.current_user_playlists(chunk, offset)
        for item in playlist_info['items']:
            all_playlists[item['name']] = item['id']
        if len(all_playlists) >= playlist_info['total']:
            break
        else:
            offset += chunk

    if target_playlist_name not in all_playlists:
        resp = client.user_playlist_create(client.me()['id'], target_playlist_name, public=False, 
            description='AUTOMATED PLAYLIST - https://github.com/turrence/spotify-new-music-sorter')
        return resp['id']
    else:
        return all_playlists[target_playlist_name]

# returns a datetime object of the most recently added song of a playlist
def get_newest_date_in_playlist(pl_id, client):
    """    
    ASSUMPTIONS: the order of the songs in the playlist is in which the songs were added
    Potential Solution: loop through every track's date added and find the max (not implemented)
    """
    songs = client.playlist_tracks(pl_id, fields="total")
    if songs['total'] == 0:
        return start_season_time(dt.now(tz=tz.utc))
    last_song = client.playlist_tracks(
        pl_id, fields="items, total", offset=songs['total']-1)
    return dt.strptime(last_song['items'][len(last_song['items']) - 1]['added_at'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=tz.utc)

# given a datetime, return a dt of the start of the season
# for e.g. if its winter 2020, return DEC 1, 2019 00:00 UTC
# for e.g. if its spring 2020, return MAR 1, 2020 00:00 UTC
def start_season_time(now) -> dt:
    if now.month in [12, 1, 2]:
        return dt(now.year if now.month == 12 else now.year - 1, 12, 1, tzinfo=tz.utc)
    elif now.month in range(3, 6):
        return dt(now.year, 3, 1, tzinfo=tz.utc)
    elif now.month in range(6, 9):
        return dt(now.year, 6, 1, tzinfo=tz.utc)
    else:
        return dt(now.year, 9, 1, tzinfo=tz.utc)

# Updates the playlist for a specific client
# client: the client to update
def update_playlist(client):
    target_playlist = get_target_playlist(dt.now(tz=tz.utc), client)
    # in utc
    last_updated = get_newest_date_in_playlist(target_playlist, client)
    songs_to_be_added = get_unadded_songs(last_updated, client)

    database.update_user(client.me()['id'], "last_playlist", target_playlist)
    if len(songs_to_be_added) < 1:
        # print("No songs to be added for", client.me()['id'])
        pass
    else:
        timestamp = dt.now(tz=tz.utc).strftime('%Y-%m-%d %H:%M:%S')
        # print(timestamp + ": Adding " + str(len(songs_to_be_added)) + " songs for", client.me()['id'])
        database.update_user(client.me()['id'], "last_update", timestamp)
        database.increment_field(client.me()['id'], "update_count")

        # we can only add 100 songs at a time, place all the songs in a queue
        # and dequeue into a chunk 100 songs at a time
        chunk = []
        while songs_to_be_added:
            chunk.append(songs_to_be_added.popleft())
            if (len(chunk) == 100):
                client.user_playlist_add_tracks(
                    client.me()['id'], target_playlist, chunk)
                chunk.clear()
        # if the chunk isn't completely filled then add the rest of the songs
        if (len(chunk) > 0):
            client.user_playlist_add_tracks(
                client.me()['id'], target_playlist, chunk)
