#!/usr/bin/env python3

import json
import unicodedata
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import httpx

# import keyring
from jinja2 import Environment, FileSystemLoader

# # set your api token, run once and then remove your api token it will be stored in your os keystore
# # API_TOKEN = ""
# # keyring.set_password("mealie", "api", API_TOKEN)
# API_TOKEN = keyring.get_password("mealie", "api")
# # print(API_TOKEN)

INDEX_TEMPLATE = "index.tmpl"


# HOST = "localhost"
# PORT = 9925
# BASE_URL = f"http://{HOST}:{PORT}/api"

# DEST = Path.cwd().parent / "static-site"
# assert DEST.exists() and DEST.is_dir()


# TEST = True

# SKIPPED_CATEGORIES = ("Shopping",)
# SKIPPED_TAGS = (None,)


# def request(url):
#     response = httpx.get(url, headers={"Authorization": f"Bearer {API_TOKEN}"})
#     response.raise_for_status()
#     return response


def fprint(s):
    print(s, flush=True)


class Requestor:
    def __init__(self, config):
        self.config = config

    def request(self, url):
        response = httpx.get(
            url, headers={"Authorization": f"Bearer {self.config.api_token}"}
        )
        response.raise_for_status()
        return response


class Recipe(Requestor):
    def __init__(self, config, slug):
        super().__init__(config)
        self.slug = slug
        self.recipe_json = None
        self.recipe_dict = None
        self.url = f"{self.config.api_url}/recipes/{slug}"
        self.render_url = f"{self.config.api_url}/recipes/{self.slug}/exports?template_name=recipes.tmpl"

    def get_recipe(self):
        response = self.request(self.url)
        recipe = response.json()
        self.recipe_dict = recipe
        self.recipe_json = json.dumps(self.recipe_dict, indent=4, sort_keys=True)
        return recipe

    def render(self):
        response = self.request(self.render_url)
        return response.content.decode("utf8")

    def get_json_recipe(self):
        if not self.recipe_json:
            self.get_recipe()
        return self.recipe_json

    def write(self):
        (self.config.dest_dir / (self.slug + ".html")).write_text(self.render())
        (self.config.dest_dir / (self.slug + ".json")).write_text(
            self.get_json_recipe()
        )
        fprint(f"Page for {self.slug} written.")

    @staticmethod
    def _clean(text):
        if text:
            text = "".join(
                c if unicodedata.category(c)[0] == "L" else " " for c in text
            )
            return "".join(c if c.isascii() else " " for c in text)
        return " "

    def get_search_tokens(self):
        recipe = self.recipe_dict
        tokens = [
            recipe["slug"],
            recipe["name"],
            recipe["description"],
            recipe["orgURL"],
        ]
        tokens += self.categories
        tokens += self.tags
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

        tokens = [self._clean(token) for token in tokens]
        return tokens

    def get_index_dict(self):
        recipe = self.recipe_dict
        return {
            "id": self.slug,
            "name": recipe["name"],
            "search_tokens": " ".join([t for t in self.get_search_tokens() if t]),
            "tags": self.tags,
            "categories": self.categories,
            "display_stars": "★" * self.rating + "☆" * (5 - self.rating),
        }

    @staticmethod
    def _extract_list(dict_list: list[dict], field_name="name"):
        """
        Given a list of dict create a list of all of field values for a
        particular field.
        x = [{'a':1, 'b':9}, {'a': 2, 'b': 8}]
        _extract_list(x, 'a') -> [1, 2]
        """
        return [obj[field_name] for obj in dict_list]

    @property
    def tags(self):
        if not self.recipe_dict:
            self.get_recipe()
        return self._extract_list(self.recipe_dict["tags"])

    @property
    def categories(self):
        if not self.recipe_dict:
            self.get_recipe()
        return self._extract_list(self.recipe_dict["recipeCategory"])

    @property
    def rating(self) -> int:
        try:
            return int(self.recipe_dict["rating"] if self.recipe_dict["rating"] else 0)
        except ValueError:
            return 0


class Index(Requestor):
    SKIPPED_CATEGORIES = ("Shopping",)
    SKIPPED_TAGS = (None,)

    def __init__(self, config):
        super().__init__(config)
        self.slugs = []
        self.recipes = []

    def populate_recipes(self):
        if not self.slugs:
            self.get_all_slugs()
        for slug in self.slugs:
            recipe = Recipe(self.config, slug)
            self.recipes.append(recipe)

    def get_recipes_summary(self) -> dict:
        next_url = None
        url = f"{self.config.api_url}/recipes"
        fprint(f"{url=}")
        next_path, recipes = self.get_recipe_list_page(url)
        all_recipes = recipes
        if next_path:
            next_url = f"{self.config.base_url}{next_path}"

        while next_url:
            fprint(f"{next_url=}")
            next_path, recipes = self.get_recipe_list_page(next_url)
            next_url = f"{self.config.base_url}{next_path}" if next_path else None
            all_recipes += recipes

        return all_recipes

    def get_recipe_list_page(self, url: str) -> tuple[str, list[dict]]:
        response = self.request(url)
        fprint(f"{url=}")
        fprint(f"{response=}")
        data = response.json()
        # print((data["page"], data["per_page"], data["total"], data["total_pages"]))
        next_url = data["next"]
        next_url = self.fix_api_url(next_url)
        recipes = data["items"]
        return next_url, recipes

    @staticmethod
    def fix_api_url(url: str) -> str:
        """
        It seems the next being returned from the api, is not for the api,
        so we need to change the path if the /api/ prefix is missing.
        """
        parsed_url = urlparse(url)
        if url and parsed_url.path[:4] != "/api":
            fixed_parsed_url = parsed_url._replace(path="/api" + parsed_url.path)
            return urlunparse(fixed_parsed_url)
        return url

    def get_all_slugs(self) -> list[str]:
        all_recipes = self.get_recipes_summary()
        slugs = [
            recipe["slug"] for recipe in all_recipes if self._should_include(recipe)
        ]
        self.slugs = slugs
        return slugs

    def _should_include(self, recipe: dict) -> bool:
        """True if this recipe should be included in the index"""
        categories = recipe["recipeCategory"]
        for category in categories:
            if category["name"] in self.SKIPPED_CATEGORIES:
                return False
        tags = recipe["tags"]
        for tag in tags:
            if tag["name"] in self.SKIPPED_TAGS:
                return False
        return True

    def make(self):
        if not self.recipes:
            self.populate_recipes()

        search_dicts = []
        for recipe in self.recipes:
            recipe.write()
            if "shopping" in [cat.lower() for cat in recipe.categories]:
                continue
            search_dicts.append(recipe.get_index_dict())
        index_page = self.render(search_dicts)
        (self.config.dest_dir / "index.html").write_text(index_page)
        fprint("index written")

        # recipes = []
        # for slug in slugs:
        #     recipe = get_recipe(slug)
        #     (DEST / (slug + ".json")).write_text(json.dumps(recipe, indent=4))
        #     print(json.dumps(recipe, indent=4))
        #     if "shopping" in [c["name"].lower() for c in recipe["recipeCategory"]]:
        #         continue
        #     recipes.append(get_search_tokens(recipe))
        # page = render_index(recipes)
        # (DEST / "index.html").write_text(page)

    def render(self, recipes):
        loader = FileSystemLoader(Path(__file__).parent)
        environment = Environment(loader=loader)
        template = environment.get_template(INDEX_TEMPLATE)
        page = template.render({"recipes": recipes})
        return page


# ==========================================================================
# ==========================================================================
# ==========================================================================
# ==========================================================================
# ==========================================================================
# ==========================================================================
# ==========================================================================


# def get_recipe(slug):
#     url = f"{BASE_URL}/recipes/{slug}"
#     response = request(url)
#     recipe = response.json()
#     return recipe


# def get_recipe_list_page(url):
#     response = request(url)
#     data = response.json()
#     # print((data["page"], data["per_page"], data["total"], data["total_pages"]))
#     next_url = data["next"]
#     recipes = data["items"]
#     return next_url, recipes


# def get_all_recipes():
#     url = f"{BASE_URL}/recipes"
#     next_path, recipes = get_recipe_list_page(url)
#     all_recipes = recipes
#     if next_path:
#         next_url = f"{BASE_URL}{next_path}"

#     while next_url:
#         # print(next_url)
#         next_path, recipes = get_recipe_list_page(next_url)
#         next_url = f"{BASE_URL}{next_path}" if next_path else None
#         all_recipes += recipes

#     return all_recipes


# def get_rendered_recipe(slug):
#     url = f"{BASE_URL}/recipes/{slug}/exports?template_name=recipes.tmpl"
#     response = request(url)
#     return response.content.decode("utf8")


# def get_json_recipe(slug):
#     url = f"{BASE_URL}/recipes/{slug}"
#     response = request(url)
#     return response.json()


# def render_index(recipes):
#     loader = FileSystemLoader(Path.cwd())
#     environment = Environment(loader=loader)
#     template = environment.get_template(INDEX_TEMPLATE)
#     page = template.render({"recipes": recipes})
#     return page


# def should_include(recipe):
#     categories = recipe["recipeCategory"]
#     for category in categories:
#         if category["name"] in SKIPPED_CATEGORIES:
#             return False
#     tags = recipe["tags"]
#     for tag in tags:
#         if tag["name"] in SKIPPED_TAGS:
#             return False
#     return True


# def clean(text):
#     if text:
#         text = "".join(c if unicodedata.category(c)[0] == "L" else " " for c in text)
#         return "".join(c if c.isascii() else " " for c in text)
#     return " "


# def get_search_tokens(recipe):
#     def extract_list(obj_list, field_name="name"):
#         return [obj[field_name] for obj in obj_list]

#     tokens = [recipe["slug"], recipe["name"], recipe["description"], recipe["orgURL"]]
#     categories = extract_list(recipe["recipeCategory"])
#     tokens += categories
#     tags = extract_list(recipe["tags"])
#     tokens += tags
#     for ingredient in recipe["recipeIngredient"]:
#         food = ingredient["food"]
#         # print(json.dumps(food, indent=4))
#         tokens += [
#             food["name"] if food else "",
#             ingredient["note"],
#             ingredient["display"],
#             ingredient["originalText"],
#         ]

#     for note in recipe["notes"] + recipe["recipeInstructions"]:
#         tokens += [note["title"], note["text"]]

#     tokens = [clean(x) for x in tokens]

#     try:
#         int_rating = int(recipe["rating"] if recipe["rating"] else 0)
#     except ValueError:
#         int_rating = 0

#     return {
#         "id": recipe["slug"],
#         "name": recipe["name"],
#         "search_tokens": " ".join([t for t in tokens if t]),
#         "tags": tags,
#         "categories": categories,
#         "display_stars": "★" * int_rating + "☆" * (5 - int_rating),
#     }


# def make_index(slugs):
#     recipes = []
#     for slug in slugs:
#         recipe = get_recipe(slug)
#         (DEST / (slug + ".json")).write_text(json.dumps(recipe, indent=4))
#         print(json.dumps(recipe, indent=4))
#         if "shopping" in [c["name"].lower() for c in recipe["recipeCategory"]]:
#             continue
#         recipes.append(get_search_tokens(recipe))
#     page = render_index(recipes)
#     (DEST / "index.html").write_text(page)
#     print("index written")


# def main(test=False):
#     all_recipes = get_all_recipes()
#     slugs = [x["slug"] for x in all_recipes if should_include(x)]
#     print(json.dumps(slugs, indent=4))

#     if test:
#         # print(get_json_recipe("cha-cha-s-white-chicken-chili"))
#         slugs = [
#             "cha-cha-s-white-chicken-chili",
#             "goulash-v2",
#             "slow-cooker-balsamic-garlic-pork-tenderloin",
#             "key-lime-pie",
#         ]

#     for slug in slugs:
#         print(slug)
#         (DEST / (slug + ".html")).write_text(get_rendered_recipe(slug))

#     make_index(slugs)


# if __name__ == "__main__":
#     parser = argparse.ArgumentParser()
#     parser.add_argument("--test", action="store_true", default=False)
#     args = parser.parse_args()
#     main(test=args.test)
