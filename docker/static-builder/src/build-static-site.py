#!/usr/bin/env python3

import argparse
import json
import unicodedata
from pathlib import Path

import httpx
import keyring
from jinja2 import Environment, FileSystemLoader

# set your api token, run once and then remove your api token it will be stored in your os keystore
# API_TOKEN = ""
# keyring.set_password("mealie", "api", API_TOKEN)
API_TOKEN = keyring.get_password("mealie", "api")
# print(API_TOKEN)

INDEX_TEMPLATE = "index.tmpl"


HOST = "localhost"
PORT = 9925
BASE_URL = f"http://{HOST}:{PORT}/api"

DEST = Path.cwd().parent / "static-site"
assert DEST.exists() and DEST.is_dir()


TEST = True

SKIPPED_CATEGORIES = ("Shopping",)
SKIPPED_TAGS = (None,)


def request(url):
    response = httpx.get(url, headers={"Authorization": f"Bearer {API_TOKEN}"})
    response.raise_for_status()
    return response


def get_recipe(slug):
    url = f"{BASE_URL}/recipes/{slug}"
    response = request(url)
    recipe = response.json()
    return recipe


def get_recipe_list_page(url):
    response = request(url)
    data = response.json()
    # print((data["page"], data["per_page"], data["total"], data["total_pages"]))
    next_url = data["next"]
    recipes = data["items"]
    return next_url, recipes


def get_all_recipes():
    url = f"{BASE_URL}/recipes"
    next_path, recipes = get_recipe_list_page(url)
    all_recipes = recipes
    if next_path:
        next_url = f"{BASE_URL}{next_path}"

    while next_url:
        # print(next_url)
        next_path, recipes = get_recipe_list_page(next_url)
        next_url = f"{BASE_URL}{next_path}" if next_path else None
        all_recipes += recipes

    return all_recipes


def get_rendered_recipe(slug):
    url = f"{BASE_URL}/recipes/{slug}/exports?template_name=recipes.tmpl"
    response = request(url)
    return response.content.decode("utf8")


def get_json_recipe(slug):
    url = f"{BASE_URL}/recipes/{slug}"
    response = request(url)
    return response.json()


def render_index(recipes):
    loader = FileSystemLoader(Path.cwd())
    environment = Environment(loader=loader)
    template = environment.get_template(INDEX_TEMPLATE)
    page = template.render({"recipes": recipes})
    return page


def should_include(recipe):
    categories = recipe["recipeCategory"]
    for category in categories:
        if category["name"] in SKIPPED_CATEGORIES:
            return False
    tags = recipe["tags"]
    for tag in tags:
        if tag["name"] in SKIPPED_TAGS:
            return False
    return True


def clean(text):
    if text:
        text = "".join(c if unicodedata.category(c)[0] == "L" else " " for c in text)
        return "".join(c if c.isascii() else " " for c in text)
    return " "


def get_search_tokens(recipe):
    def extract_list(obj_list, field_name="name"):
        return [obj[field_name] for obj in obj_list]

    tokens = [recipe["slug"], recipe["name"], recipe["description"], recipe["orgURL"]]
    categories = extract_list(recipe["recipeCategory"])
    tokens += categories
    tags = extract_list(recipe["tags"])
    tokens += tags
    for ingredient in recipe["recipeIngredient"]:
        food = ingredient["food"]
        # print(json.dumps(food, indent=4))
        tokens += [
            food["name"] if food else "",
            ingredient["note"],
            ingredient["display"],
            ingredient["originalText"],
        ]

    for note in recipe["notes"] + recipe["recipeInstructions"]:
        tokens += [note["title"], note["text"]]

    tokens = [clean(x) for x in tokens]

    try:
        int_rating = int(recipe["rating"] if recipe["rating"] else 0)
    except ValueError:
        int_rating = 0

    return {
        "id": recipe["slug"],
        "name": recipe["name"],
        "search_tokens": " ".join([t for t in tokens if t]),
        "tags": tags,
        "categories": categories,
        "display_stars": "★" * int_rating + "☆" * (5 - int_rating),
    }


def make_index(slugs):
    recipes = []
    for slug in slugs:
        recipe = get_recipe(slug)
        (DEST / (slug + ".json")).write_text(json.dumps(recipe, indent=4))
        print(json.dumps(recipe, indent=4))
        if "shopping" in [c["name"].lower() for c in recipe["recipeCategory"]]:
            continue
        recipes.append(get_search_tokens(recipe))
    page = render_index(recipes)
    (DEST / "index.html").write_text(page)
    print("index written")


def main(test=False):
    all_recipes = get_all_recipes()
    slugs = [x["slug"] for x in all_recipes if should_include(x)]
    print(json.dumps(slugs, indent=4))

    if test:
        # print(get_json_recipe("cha-cha-s-white-chicken-chili"))
        slugs = [
            "cha-cha-s-white-chicken-chili",
            "goulash-v2",
            "slow-cooker-balsamic-garlic-pork-tenderloin",
            "key-lime-pie",
        ]

    for slug in slugs:
        print(slug)
        (DEST / (slug + ".html")).write_text(get_rendered_recipe(slug))

    make_index(slugs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", default=False)
    args = parser.parse_args()
    main(test=args.test)
