import time
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from curl_cffi import requests

from logger import get_logger

logger = get_logger(__name__)

API_URL = "https://www.olx.pl/api/v1/offers/"


def is_olx_url(url):
    """
    Check if a URL points to olx.pl.

    Args:
        url (str): Any URL

    Returns:
        bool: True for www.olx.pl / olx.pl URLs
    """
    host = urlparse(url).netloc.lower().split(":")[0]
    return host == "olx.pl" or host.endswith(".olx.pl")


def get_search_text(url):
    """
    Extract the search text of an OLX search URL.

    OLX keeps it in the path, e.g. /oferty/q-raspberry-pi-5/ -> "raspberry pi 5".

    Args:
        url (str): The OLX search URL

    Returns:
        str: The search text, empty if the URL has none
    """
    for part in urlparse(url).path.split("/"):
        if part.startswith("q-"):
            return part[2:].replace("-", " ").strip()
    return ""


def normalize_url(url):
    """
    Drop the parts of an OLX search URL that change between visits.

    Args:
        url (str): The OLX search URL

    Returns:
        str: The URL without paging and sorting parameters
    """
    parsed = urlparse(url)
    params = [
        (k, v)
        for k, v in parse_qsl(parsed.query)
        if k not in ("page", "search[order]", "reason", "search_reason")
    ]
    return urlunparse(parsed._replace(query=urlencode(params), fragment=""))


def parse_url(url, nbr_items=20):
    """
    Turn an OLX search URL into parameters for the offers API.

    Filters come as search[filter_...] in the URL and go to the API as filter_...
    Category and city path segments are not mapped to API ids and are ignored.

    Args:
        url (str): The OLX search URL
        nbr_items (int, optional): Number of items to request. Defaults to 20.

    Returns:
        dict: Parameters for the offers API
    """
    params = {
        "offset": 0,
        "limit": nbr_items,
        "sort_by": "created_at:desc",
    }
    text = get_search_text(url)
    if text:
        params["query"] = text
    for key, value in parse_qsl(urlparse(url).query):
        if key.startswith("search[filter_") and key.endswith("]"):
            # search[filter_float_price:from] -> filter_float_price:from
            # search[filter_enum_state][0]    -> filter_enum_state[0]
            params[key[len("search[") :].replace("]", "", 1)] = value
    return params


class OlxItem:
    """
    A single OLX offer, exposing the same attributes the bot reads from Vinted items.

    The offers API does give a listing time, but promoted offers keep their old one,
    so like Vinted items these are deduplicated by id and stamped with the time we
    first saw them.
    """

    site_name = "OLX"

    def __init__(self, data):
        self.raw_data = data
        # OLX and Vinted ids come from overlapping ranges and share the items table.
        self.id = f"olx-{data['id']}"
        self.title = data["title"]

        price = next(
            (p.get("value") or {} for p in data.get("params", []) if p.get("key") == "price"),
            {},
        )
        self.price = price.get("value") or 0
        self.currency = price.get("currency") or "PLN"

        # No brand on OLX; the city is what matters for pickup.
        city = ((data.get("location") or {}).get("city") or {}).get("name")
        self.brand_title = f"OLX, {city}" if city else "OLX"
        self.size_title = None

        photos = data.get("photos") or []
        self.photo = (
            photos[0]["link"].replace("{width}", "640").replace("{height}", "480")
            if photos
            else None
        )
        self.url = data["url"]
        self.buy_url = self.url

        self.has_real_timestamp = False
        self.raw_timestamp = int(time.time())
        self.created_at_ts = datetime.fromtimestamp(self.raw_timestamp, tz=timezone.utc)

    def is_new_item(self, minutes=20):
        return True


class Olx:
    """
    Search olx.pl through the offers API used by the OLX website.

    Plain HTTP clients get 403 from OLX, so requests go through curl_cffi with a
    Chrome TLS fingerprint.
    """

    def __init__(self):
        self.session = requests.Session(impersonate="chrome")

    def search(self, url, nbr_items=20):
        """
        Retrieve the newest offers for an OLX search URL.

        Args:
            url (str): The OLX search URL
            nbr_items (int, optional): Number of items to return. Defaults to 20.

        Returns:
            list: OlxItem objects, newest first

        Raises:
            requests.exceptions.HTTPError: If OLX rejects the request
        """
        response = self.session.get(API_URL, params=parse_url(url, nbr_items), timeout=20)
        response.raise_for_status()
        return [OlxItem(offer) for offer in response.json().get("data", [])]
