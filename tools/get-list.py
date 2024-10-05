import json
from pathlib import Path

import httpx
import keyring
from jinja2 import Environment, FileSystemLoader

api_token = keyring.get_password("mealie", "api")
list_id = "e27baaa6-9057-43c3-a64d-16b8218fc4e1"

TEMPLATE = "list.tmpl"
# DEST = "~/Src/devops/quasisemi.com/src/caddy/site/list.html"
DEST = "../static-site/list.html"


def render(shopping_list):
    loader = FileSystemLoader(Path.cwd())
    environment = Environment(loader=loader)
    template = environment.get_template(TEMPLATE)
    page = template.render({"list": shopping_list})
    return page


def compile_list():
    host = "localhost"
    port = 9925
    base_url = f"http://{host}:{port}/api"
    path = f"groups/shopping/lists/{list_id}"
    url = f"{base_url}/{path}"
    response = httpx.get(url, headers={"Authorization": f"Bearer {api_token}"})
    shopping_list = json.loads(response.content)
    compiled = {}
    for label in shopping_list["labelSettings"]:
        compiled[label["label"]["name"]] = {"position": label["position"], "items": []}

    compiled["Uncat"] = {"position": 99, "items": []}

    for item in shopping_list["listItems"]:
        if item["checked"]:
            continue
        print(json.dumps(item, indent=4))
        label = (item.get("label") or {}).get("name", "Uncat")
        compiled[label]["items"].append(item["display"])

    return {k: v for k, v in compiled.items() if v["items"]}


def save(page, dest):
    path = Path(dest).expanduser().absolute()
    path.write_text(page)


def main():
    compiled = compile_list()
    page = render(compiled)
    # print(page)
    save(page, DEST)


if __name__ == "__main__":
    main()
