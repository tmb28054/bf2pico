# Brewfather to Pico

I am an SDK that transforms Brewfather recipes into pico brewing instructions.

## How to install

```
python -m pip install bf2pico
```

## How to use bf2pico

```
from bf2pico import BrewFather

recipe = BrewFather(
    userid=userid,
    apikey=apikey
)

recipe = recipe.pico()
```
