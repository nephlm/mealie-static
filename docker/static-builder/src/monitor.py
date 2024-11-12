import os
import time
from dataclasses import dataclass
from pathlib import Path

import build_static_site as site

# from . import get_list
import get_list
import httpx

# BASE_URL = "http://mealie:9000"
# API_URL = BASE_URL + "/api"
# DEST = Path("/site")

env = os.environ

KEY_FILE = Path(env["API_KEY_FILE"])
API_TOKEN = KEY_FILE.read_text("utf8")
LIST_ID = env["LIST_ID"]


@dataclass
class Config:
    base_url: str = "http://mealie:9000"
    api_token: str = API_TOKEN
    dest_dir: Path = Path("/site")

    @property
    def api_url(self):
        sep = "" if self.base_url[-1] == "/" else "/"
        return f"{self.base_url}{sep}api"


def fprint(s):
    print(s, flush=True)


def check_mealie_webserver(config):
    fprint(f"Checking if {config.base_url} is up.")
    try:
        response = httpx.get(config.base_url, timeout=1)
        return response.status_code == 200
    except httpx.ConnectError:
        fprint("Mealie not up yet, or unaccessble")
        return False
    except Exception:
        fprint("Unexpected Error checking Mealie server")
        return False


def main():
    fprint("===================== PROGRAM STARTED SUCCESSFULLY ===================")
    config = Config()
    iterations = 0
    while not check_mealie_webserver(config):
        time.sleep(10)
    shopping_list = get_list.ShoppingList(config, LIST_ID)
    while True:
        shopping_list.write_list()

        if not iterations % 2:
            index = site.Index(config)
            index.make()

        for _ in range(30):
            time.sleep(1)
        iterations += 1


if __name__ == "__main__":
    main()
