import requests
import time
import json
import threading
import os

servers = {}

class Server(threading.Thread):
    def __init__(self, settings):
        threading.Thread.__init__(self)

        self.player_cache = {}
        self.playercount = {}
        self.dynmap_players_last = []
        self.join_cache = {}
        self.logs = []
        self.address = settings["address"]

        self._last_playercount_timestamp = 0

        if settings["use_dynmap"]:
            self.dynmap_url = settings["dynmap"]

            # Fetch default world
            request = requests.get(self.dynmap_url + "up/configuration")
            
            if request.status_code != 200:
                print("Failed to get dynmap configuration")

            dynmap_config = json.loads(request.text)
            self.default_world = dynmap_config["defaultworld"]

            self.worlds = [world["title"] for world in dynmap_config["worlds"]]

    def load_data(self):
        pass

    def save_data(self):
        json.dumps({
            "playercount": self.playercount,
            "players": self.player_cache
        })

    def run(self):
        self.cycle(first=True)
        while True:
            self.cycle()
            time.sleep(1)


    def cycle(self, first=False):

        if first:
            self.logs.append(f"[{self.address}] Thread opened")

        if self.default_world:
            request = requests.get(self.dynmap_url + f"up/{self.default_world}/{self.worlds[0]}/0")

            decoded = json.loads(request.text)

            player_accounts = [player["account"] for player in decoded["players"]]

            if self._last_playercount_timestamp + 30 < time.time():
                self.playercount[time.time()] = len(player_accounts)
                self._last_playercount_timestamp = time.time()

                with open("./store/playercount.log", "a") as f:
                    f.write(str(len(player_accounts)) + "\n")

            joined = [account for account in player_accounts if not account in self.dynmap_players_last]
            left = [account for account in self.dynmap_players_last if not account in player_accounts]

            for account in joined:
                if not first:
                    self.logs.append(f"{account} joined the game")
                self.join_cache[account] = time.time()
                
                try:
                    with open(f"./store/{account}.player") as f:
                        data = json.load(f)
                except FileNotFoundError:
                    data = {
                        "account": account,
                        "playtime": 0,
                        "session_count": 0
                    }

                data["session_count"] += 1

                self.player_cache[account] = data

                
            for account in left:
                if not first:
                    self.logs.append(f"{account} left the game")

                playtime = time.time() - self.join_cache[account]

                self.player_cache[account]["playtime"] += playtime

                with open(f"./store/{account}.player", "w") as f:
                    f.write(json.dumps(self.player_cache[account]))

                del self.player_cache[account]
                del self.join_cache[account]
                


            self.dynmap_players_last = player_accounts
        
        if first:
            self.logs.append(f"[{self.address}] {len(self.player_cache)} players online.")

def main():

    if not os.path.exists("./store"):
        os.mkdir("./store")

    with open("servers.json") as config:

        for server_address, settings in json.load(config).items():

            settings["address"] = server_address

            server = Server(settings)
            server.daemon = True
            server.start()

            servers[server_address] = server

    print("\nMulti Server tracker v1.0")
    print(f"Currently tracking {len(servers)} servers!")
    print("(" + "".join(servers.keys()) + ")\n")
    while True:
        inp = input("> ")

        split = inp.split(" ")

        command, args = split[0], split[1:]

        if command == "stop":
            exit(0)
        elif command == "help":
            print("help - shows this message")
            print("stop - kills the process")
            print("servers - shows all loaded servers")
            print("threads - display all utilised threads")
            print("online <server> - get data for the online players on a server")
            print("logs <server> - get the logs for an individual server")
        elif command == "servers":
            print("".join(servers.keys()))
        elif command == "threads":
            print("".join([str(server) for server in servers.values()]))
        elif command == "online":
            if len(args) == 0:
                print("online <server>")
                continue
            if args[0] in servers:
                player_cache = servers[args[0]].player_cache

                for player in player_cache.values():
                    print(player)
        elif command == "logs":
            if len(args) == 0:
                print("logs <server>")
                continue
            if args[0] in servers:
                logs = servers[args[0]].logs

                print("".join([line + "\n" for line in logs[-10:]]))
        else:
            print("unrecognised command")
            

if __name__ == "__main__":
    main()