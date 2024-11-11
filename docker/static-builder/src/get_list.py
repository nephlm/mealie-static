import json

# import os
from pathlib import Path

import httpx
from jinja2 import Environment, FileSystemLoader

# env = os.environ
# print(env["API_KEY_FILE"], flush=True)

# with open(env["API_KEY_FILE"], "r") as fp:
#     API_TOKEN = fp.read()
#     print("Got Mealie API Key", flush=True)
#     # print(key, flush=True)

# api_token = API_TOKEN
# # api_token = keyring.get_password("mealie", "api")
# list_id = "e27baaa6-9057-43c3-a64d-16b8218fc4e1"

# # DEST = "~/Src/devops/quasisemi.com/src/caddy/site/list.html"
# # DEST = "../static-site/list.html"
# # DEST = "/site"


class ShoppingList:
    TEMPLATE = "list.tmpl"
    # DEST = Path("/site/list.html")

    def __init__(self, config, list_id):
        self.api_url = config.api_url  # includes /api
        self.mealie_token = config.api_token
        self.list_id = list_id
        self.dest_file = config.dest_dir / "list.html"
        self._last_shopping_list = None

    def compile_list(self):
        path = f"households/shopping/lists/{self.list_id}"
        url = f"{self.api_url}/{path}"
        response = httpx.get(
            url, headers={"Authorization": f"Bearer {self.mealie_token}"}
        )
        shopping_list = json.loads(response.content)
        print("Shopping list Retrieved", flush=True)
        compiled = {}
        for label in shopping_list["labelSettings"]:
            compiled[label["label"]["name"]] = {
                "position": label["position"],
                "items": [],
            }

        compiled["Uncat"] = {"position": 99, "items": []}

        for item in shopping_list["listItems"]:
            if item["checked"]:
                continue
            label = (item.get("label") or {}).get("name", "Uncat")
            compiled[label]["items"].append(item["display"])

        print("Shopping list Compiled", flush=True)
        return {k: v for k, v in compiled.items() if v["items"]}

    def render_list(self, shopping_list):
        loader = FileSystemLoader(Path.cwd())
        environment = Environment(loader=loader)
        template = environment.get_template(self.TEMPLATE)
        page = template.render({"list": shopping_list})
        print("Shopping list Rendered", flush=True)
        return page

    def save_list(self, page):
        path = Path(self.dest_file).expanduser().absolute()
        print("Shopping list Written", flush=True)
        path.write_text(page, encoding="utf-8")

    def write_list(self):
        shopping_list = self.compile_list()
        if shopping_list != self._last_shopping_list:
            page = self.render_list(shopping_list)
            self.save_list(page)
            self._last_shopping_list = shopping_list


# def render_list(shopping_list):
#     loader = FileSystemLoader(Path.cwd())
#     environment = Environment(loader=loader)
#     template = environment.get_template(TEMPLATE)
#     page = template.render({"list": shopping_list})
#     return page


# def compile_list(base_url):
#     # host = "192.168.1.2"
#     # host = "mealie.nephlm.com"
#     # port = 9925
#     # base_url = f"http://{host}:{port}/api"
#     # base_url = f"https://{host}/api"
#     # path = f"groups/shopping/lists/{list_id}"
#     base_url = base_url + "/api"
#     path = f"households/shopping/lists/{list_id}"
#     url = f"{base_url}/{path}"
#     print(url)
#     response = httpx.get(url, headers={"Authorization": f"Bearer {api_token}"})
#     print(response.status_code)
#     # print(response.content)
#     shopping_list = json.loads(response.content)
#     compiled = {}
#     for label in shopping_list["labelSettings"]:
#         compiled[label["label"]["name"]] = {"position": label["position"], "items": []}

#     compiled["Uncat"] = {"position": 99, "items": []}

#     for item in shopping_list["listItems"]:
#         if item["checked"]:
#             continue
#         print(json.dumps(item, indent=4))
#         label = (item.get("label") or {}).get("name", "Uncat")
#         compiled[label]["items"].append(item["display"])

#     return {k: v for k, v in compiled.items() if v["items"]}


# def save_list(page, dest):
#     path = Path(dest).expanduser().absolute()
#     path.write_text(page)


# def main():
#     compiled = compile_list()
#     page = render_list(compiled)
#     # print(page)
#     save(page, DEST)


# if __name__ == "__main__":
#     main()
