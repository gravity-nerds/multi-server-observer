import ServerListPing
import threading
import requests
import time
import json
import os

servers = {}
class Server(threading.Thread):
    def __init__(self, settings):
        threading.Thread.__init__(self)

        assert settings["use_dynmap"] != settings["use_slp"], "You must use one ping method only"

        self.player_cache = {}
        self.playercount = {}
        self.player_accounts_last = []
        self.join_cache = {}
        self.logs = []
        self.name = settings["name"]
        self.settings = settings
        
        self.default_world = None
        self.slp_address = None
        self.slp_port = None

        self.uuid_lookup = {}

        self._last_playercount_timestamp = 0
        self.server_up = False

        if not os.path.exists(f"./store/{self.name}/"):
            os.mkdir(f"./store/{self.name}/")

        if settings["use_dynmap"]:
            self.dynmap_url = settings["dynmap"]

            # Fetch default world
            request = requests.get(self.dynmap_url + "up/configuration")
            
            if request.status_code != 200:
                print("Failed to get dynmap configuration")

            dynmap_config = json.loads(request.text)
            self.default_world = dynmap_config["defaultworld"]

            self.worlds = [world["title"] for world in dynmap_config["worlds"]]

        elif settings["use_slp"]:
            self.slp_address = settings["slp_address"]
            self.slp_port = settings["slp_port"]

        self.webhook = None
        if settings["webhook"] != "":
            self.webhook = settings["webhook"]

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

    def addLog(self, line):
        with open(f"./store/{self.name}/main.log", "a") as f:
            f.write(f"[{time.asctime()}] {line}\n")


        self.logs.append(f"[{time.asctime()}] [{self.name}] {line}")

        if self.webhook:
            response = requests.post(self.webhook, json.dumps({
                "content": line,
                "username": "Satelite",
                "avatar_url": "https://cdn.discordapp.com/avatars/1219692243196051617/f118cfe014c37b062c9283d6cb475664.webp?size=256",
            }), headers={
                "Content-Type": "application/json"
            })


    def cycle(self, first=False):

        if first:
            self.addLog(f"Thread opened")

        up = False

        if self.default_world != None:
            request = requests.get(self.dynmap_url + f"up/{self.default_world}/{self.worlds[0]}/0")

            decoded = json.loads(request.text)

            player_accounts = [player["account"] for player in decoded["players"]]

            up = True

            if self._last_playercount_timestamp + 30 < time.time():
                self.playercount[time.time()] = len(player_accounts)
                self._last_playercount_timestamp = time.time()

                with open(f"./store/{self.name}/playercount.log", "a") as f:
                    f.write(str(len(player_accounts)) + "\n")

            joined = [account for account in player_accounts if not account in self.player_accounts_last]
            left = [account for account in self.player_accounts_last if not account in player_accounts]

            for account in joined:
                if not first:
                    self.addLog(f"{account} joined the game")
                self.join_cache[account] = time.time()
                
                try:
                    with open(f"./store/{self.name}/{account}.player") as f:
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
                    self.addLog(f"{account} left the game")

                playtime = time.time() - self.join_cache[account]

                self.player_cache[account]["playtime"] += playtime

                with open(f"./store/{self.name}/{account}.player", "w") as f:
                    f.write(json.dumps(self.player_cache[account]))

                del self.player_cache[account]
                del self.join_cache[account]

            self.player_accounts_last = player_accounts
        elif self.slp_address != None and self.slp_port != None:
            success, server_data = ServerListPing.ping(self.slp_address, self.slp_port)

            if success:
                up = True
            else:
                return

            player_accounts = []

            if "sample" in server_data["players"]:
                player_accounts = []
                for player in server_data["players"]["sample"]:
                    player_accounts.append(player["id"])
                    self.uuid_lookup[player["id"]] = player["name"]

            if self._last_playercount_timestamp + 30 < time.time():
                self.playercount[time.time()] = len(player_accounts)
                self._last_playercount_timestamp = time.time()

                with open(f"./store/{self.name}/playercount.log", "a") as f:
                    f.write(str(len(player_accounts)) + "\n")

            joined = [account for account in player_accounts if not account in self.player_accounts_last]
            left = [account for account in self.player_accounts_last if not account in player_accounts]

            self.player_accounts_last = player_accounts

            for account in joined:
                if not first:
                    self.addLog(f"{self.uuid_lookup[account] if account in self.uuid_lookup else account} joined the game")
                self.join_cache[account] = time.time()
                
                try:
                    with open(f"./store/{self.name}/{account}.player") as f:
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
                    self.addLog(f"{self.uuid_lookup[account] if account in self.uuid_lookup else account} left the game")

                playtime = time.time() - self.join_cache[account]

                self.player_cache[account]["playtime"] += playtime

                with open(f"./store/{self.name}/{account}.player", "w") as f:
                    f.write(json.dumps(self.player_cache[account]))

                del self.player_cache[account]
                del self.join_cache[account]

        if up != self.server_up:
            if not first:
                if up == True:
                    self.addLog("Server Opened")
                else:
                    self.addLog("Server Closed")

            self.server_up = up

        if first:
            self.addLog(f"{len(self.player_cache)} players online.")
            

def main():

    if not os.path.exists("./store"):
        os.mkdir("./store")

    with open("servers.json") as config:

        for server_name, settings in json.load(config).items():

            settings["name"] = server_name

            server = Server(settings)
            server.daemon = True
            server.start()

            servers[server_name] = server

    print("\nMulti Server tracker v1.0")
    print(f"Currently tracking {len(servers)} servers!")
    print("(" + "".join([server + ", " for server in servers.keys()]) + ")\n")
    while True:
        inp = input("\u001b[37m> ")

        split = inp.split(" ")

        command, args = split[0], split[1:]

        if command == "stop":
            exit(0)
        elif command == "help":
            print(" help - shows this message")
            print(" stop - kills the process")
            print(" servers - shows all loaded servers")
            print(" threads - display all utilised threads")
            print(" online <server> - get data for the online players on a server")
            print(" logs <server> - get the logs for an individual server")
        elif command == "servers":
            print("".join([server + "\n" for server in servers.keys()]))
        elif command == "threads":
            print("".join([str(server) + "\n" for server in servers.values()]))
        elif command == "online":
            if len(args) == 0:
                print("\u001b[31m online <server>")
                continue
            if args[0] in servers:
                player_cache = servers[args[0]].player_cache
                if len(player_cache) == 0:
                    print("\u001b[32m No one online.")

                for player in player_cache.values():
                    (name, playtime, sessions) = player["account"], player["playtime"], player["session_count"]

                    if len(name) == 36:
                        if name in servers[args[0]].uuid_lookup:
                            name = servers[args[0]].uuid_lookup[name]

                    print(f"\u001b[32m {name} [{playtime}s #{sessions}]")
        elif command == "logs":
            if len(args) == 0:
                print("\u001b[31m logs <server>")
                continue
            if args[0] in servers:
                meta = servers[args[0]].logs

                print("".join([" " + line + "\n" for line in meta[-10:]]))
        elif command == "meta":
            if len(args) == 0:
                print("\u001b[31m meta <server>")
                continue
            if args[0] in servers:
                meta = servers[args[0]].settings

                print(json.dumps(meta, indent=4))
        elif command == "live":
            if len(args) == 0:
                print("\u001b[31m live <server>")
                continue
            if args[0] in servers:
                last = ""
                while True:
                    meta = servers[args[0]].logs

                    c = meta[-1][27:]

                    if c != last:
                        print(c)
                    last = c
                    time.sleep(0.1)
                    
        else:
            print("\u001b[31m unrecognised command")
            

if __name__ == "__main__":
    main()