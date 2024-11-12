# Mealie Static Site 

Basically I run mealie locally inside my firewall, and I don't feel 
a need to change that.  But I would like to be able to have by recipes
available when I'm not at home. 

## Sidecar Container

`docker/static-builder` is a container that runs a loop that publishes the 
shopping list specified by whichever id is specified in 
`docker-compose.yml` and all recipes every 60 seconds.  

TODO: detect changes in recipes and only publish when needed.
TODO: Publish all lists and stop hardcoding the special one I 
    actually use.
TODO: The path to my RAID is hardcoded in the `docker-compose.yml`,
    that should be more configurable. It points to the `data` 
    directory that is checked it which contains my recipes, so...
    Have some recipes.

Dependencies:

* There needs to be a `mealie-api-key.txt` file in the same dir as 
the `docker-compose.yml`.  This contains the API key and nothing else.
* `data/templates/recipes.tmpl` is a jinja2 template which is the 
recipe page for each individual recipe.
* `docker/static-builder/src/index.tmpl` is the jinja2 template for 
the index page.
* `docker/static-builder/src/list.tmpl` is the jinja2 template for 
the shopping list page.

## Github pages

Github is configured to publish the static site whenever there are 
changes to `static-site`.