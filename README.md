# abs-bigfinish

## Overview

This is a fork of  Vito0912/abs-bigfinish original Big Finish scraper for Audiobookshelf. 

The purpose of this fork is to add additional features, including:


- Series mapping
- Importing character information into Audiobookshelf as tags

## Usage

The easiest way to use this is to use Docker

### Docker Compose

```
services:
  abs-bigfinish:
    image: ghcr.io/sas-1/abs-bigfinish:latest
    ports:
      - 7777:7777
    container_name: abs-bigfinish
    hostname: abs-bigfinish
    restart: always
```

Start the container:

```
docker compose up -d
```


## Audiobookshelf Setup

1) Log in to Audiobookshelf as an Administrator.
2) Go to Settings.
3) Select Item Metadata Utils from the menu.
4) Select Custom Metadata Providers.
5) Click Add.

Enter the following details:

| Field | Value                       |
| ----- | --------------------------- |
| Name  | Big Finish                  |
| URL   | `http://192.168.0.100:7777` |


Replace the example IP address with the IP address or hostname of your Docker host.

1) Click Save.
2) Go to your library.
3) Select an audiobook.
4) Click Edit → Match.
5) Under Provider, select your new Big Finish metadata source.
6) Click Search.
7) Select the correct result.
8) Verify the metadata and click Save.


## Features
- Retrieves metadata from Big Finish releases
- Imports cover artwork
- Imports descriptions
- Imports character names as Audiobookshelf tags
- Provides a custom metadata provider for Audiobookshelf

## Known Issues

- Search results can sometimes be inconsistent depending on the title searched.
- Metadata quality depends on the information available on the Big Finish website.

Previously Reported Issues

- ✅ ISBN missing — appears fixed
- ✅ Cast/Characters missing — appears fixed
- ✅ Description only partially returned — appears fixed
- ✅ Series information not working — appears fixed
=======
1st attemp to rewrite for new Bigfinish website. 
Site uses NEXT JS to provid*e data and is not easy to get data from.

Issues:

* ~~ISBN Missing~~ Seems to be fixed
* ~~Cast/Characters Missing~~ Needs some checks done
* ~~Description - only partial info returned~~ Needs some checks done
* Search is hit or miss
* ~~Series doesn't work~~
>>>>>>> 7801fc55270fddae8803b6eb6beeb306da195e62
