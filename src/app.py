import config
import constant
import playlist
import saved_songs
import os
import threading
import time
import traceback
from client_manager import ClientManager
from datetime import datetime as dt
from datetime import timezone as tz
from web_auth import auth_server

class App(object):
    def __init__(self):
        if not os.path.exists(constant.CACHE_PATH):
            os.mkdir(constant.CACHE_PATH)
        self.clients = ClientManager()
        # load all clients
        self.clients.load_clients_from_cache()

    def update_playlists(self):
        for c in ClientManager.clients:
            target_playlist = playlist.get_target_playlist(dt.now(tz=tz.utc), c)
            # in utc
            last_updated = playlist.get_newest_date_in_playlist(target_playlist, c)
            songs_to_be_added = saved_songs.get_unadded_songs(last_updated, c)
            if len(songs_to_be_added) >= 1:
                c.user_playlist_add_tracks(c.me()['id'], target_playlist, songs_to_be_added)

    def run_periodically(self):
        # update every 10 minutes
        threading.Timer(constant.UPDATE_FREQUENCY, self.run_periodically).start()
        try:
            self.clients.refresh_clients()
            self.update_playlists()
        except Exception as e:
            with open('error.txt', 'a') as f:
                f.write(str(e))
                f.write(traceback.format_exc())

app = App()
app.run_periodically()
