#!/usr/bin/env python3
"""Create/update this deployment's Metabase collection. Credentials are env-only."""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from dashboards import DASHBOARDS

COLLECTION = "Practice Planner Analytics"
MARKER = "Managed by .practice-planner/bootstrap.py. "
SESSION = None
URL = os.environ.get("METABASE_URL", "http://127.0.0.1:3000").rstrip("/")
PARAMETERS = {
    "days": {"id": "days", "name": "Past days (1–90)", "slug": "days", "type": "number/=", "default": "30", "required": True},
    "route": {"id": "route", "name": "Route", "slug": "route", "type": "string/=", "values_query_type": "none"},
    "actor": {"id": "actor", "name": "Actor ID", "slug": "actor", "type": "string/=", "values_query_type": "none"},
    "control": {"id": "control", "name": "Control", "slug": "control", "type": "string/=", "values_query_type": "none"},
}


def api(method, path, body=None):
    headers = {"Content-Type": "application/json"}
    if SESSION:
        headers["X-Metabase-Session"] = SESSION
    request = urllib.request.Request(URL + "/api" + path,
                                     data=None if body is None else json.dumps(body).encode(),
                                     headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            data = response.read()
            return json.loads(data) if data else None
    except urllib.error.HTTPError as error:
        # Request/response bodies can contain credentials or connection details.
        raise RuntimeError(f"Metabase {method} {path} returned HTTP {error.code}") from None
    except urllib.error.URLError:
        raise RuntimeError(f"Cannot reach Metabase at {URL}") from None


def env(key):
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def tags(sql):
    names = set(re.findall(r"{{(\w+)}}", sql))
    if not names <= PARAMETERS.keys():
        raise ValueError("Unknown query filter")
    return {name: {"id": name, "name": name, "display-name": PARAMETERS[name]["name"],
                   "type": "number" if name == "days" else "text",
                   **({"required": True, "default": 30} if name == "days" else {})}
            for name in sorted(names)}


def upsert(path, existing, body):
    matches = [item for item in existing if item.get("name") == body["name"]]
    if len(matches) > 1:
        raise RuntimeError(f"Multiple items named {body['name']}; resolve duplicates before provisioning")
    if matches:
        item = matches[0]
        if not (item.get("description") or "").startswith(MARKER):
            raise RuntimeError(f"Refusing to replace unmanaged item: {body['name']}")
        return api("PUT", f"{path}/{item['id']}", body)
    return api("POST", path, body)


def bootstrap():
    global SESSION
    parsed = urllib.parse.urlparse(URL)
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")):
        raise RuntimeError("Use HTTPS, or loopback HTTP through a private connection")
    email, password = env("METABASE_ADMIN_EMAIL"), env("METABASE_ADMIN_PASSWORD")
    properties = api("GET", "/session/properties")
    setup_token = properties.get("setup-token")
    if setup_token:
        if parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise RuntimeError("Complete first-admin setup privately before exposing the public address")
        SESSION = api("POST", "/setup", {"token": setup_token,
            "user": {"email": email, "password": password, "first_name": "Practice Planner", "last_name": "Admin"},
            "prefs": {"site_name": COLLECTION, "allow_tracking": False}})["id"]
    else:
        SESSION = api("POST", "/session", {"username": email, "password": password})["id"]

    connection_name = "Practice Planner usage (read only)"
    databases = api("GET", "/database")["data"]
    details = {"host": env("ANALYTICS_DB_HOST"), "port": int(os.environ.get("ANALYTICS_DB_PORT", "5432")),
               "dbname": os.environ.get("ANALYTICS_DB_NAME", "analytics"), "user": "analytics_reader",
               "password": env("ANALYTICS_READER_PASSWORD"), "ssl": os.environ.get("ANALYTICS_DB_SSL", "false") == "true",
               "schema-filters-type": "inclusion", "schema-filters-patterns": "analytics"}
    matches = [item for item in databases if item["name"] == connection_name]
    if len(matches) > 1:
        raise RuntimeError("Duplicate analytics connections")
    if matches:
        # Changing an existing reader connection requires a deliberate admin action.
        # Bootstrap updates questions; it does not redirect existing data connections.
        database = matches[0]
        current = api("GET", f"/database/{database['id']}")
        if current["engine"] != "postgres" or any(current["details"].get(key) != details[key] for key in ("host", "dbname", "user")):
            raise RuntimeError("Existing analytics connection differs from the requested reader; inspect it in Admin settings")
    else:
        database = api("POST", "/database", {"name": connection_name, "engine": "postgres", "details": details,
                                              "is_full_sync": False, "auto_run_queries": True})
    collections = api("GET", "/collection")
    collection = upsert("/collection", collections, {"name": COLLECTION, "description": MARKER + "Private usage reporting; invite individual users through Admin settings."})
    cards = [c for c in api("GET", "/card") if c.get("collection_id") == collection["id"]]
    dashboards = [d for d in api("GET", "/dashboard") if d.get("collection_id") == collection["id"]]
    links = []
    for spec in DASHBOARDS:
        dashboard = upsert("/dashboard", dashboards, {"name": spec["name"], "description": MARKER + spec["description"], "collection_id": collection["id"]})
        current = api("GET", f"/dashboard/{dashboard['id']}")
        previous = {item.get("card_id"): item["id"] for item in current.get("dashcards", [])}
        dashcards, filters = [], set()
        row = 0
        for index, spec_card in enumerate(spec["questions"]):
            native_tags = tags(spec_card["sql"])
            filters.update(native_tags)
            card = upsert("/card", cards, {"name": spec_card["name"], "description": MARKER + spec_card["description"],
                "collection_id": collection["id"], "display": spec_card["display"],
                "visualization_settings": spec_card["visualization_settings"],
                "dataset_query": {"database": database["id"], "type": "native", "native": {"query": spec_card["sql"], "template-tags": native_tags}}})
            # Native 24-column Metabase grid. Scalars fit four across; charts fill a row.
            scalar = spec_card["display"] == "scalar"
            dashcards.append({"id": previous.get(card["id"], -(index + 1)), "card_id": card["id"],
                "row": 0 if scalar else row, "col": index * 6 if scalar else 0,
                "size_x": 6 if scalar else 24, "size_y": 4 if scalar else 8,
                "parameter_mappings": [{"parameter_id": name, "card_id": card["id"], "target": ["variable", ["template-tag", name]]} for name in native_tags],
                "visualization_settings": {}})
            row = 4 if scalar else row + 8
        api("PUT", f"/dashboard/{dashboard['id']}", {"dashcards": dashcards, "parameters": [value for key, value in PARAMETERS.items() if key in filters], "enable_embedding": False})
        links.append({"name": spec["name"], "url": f"{URL}/dashboard/{dashboard['id']}"})
    # Native instance settings stay off in addition to the entrypoint's env overrides.
    for key in ("anon-tracking-enabled", "enable-public-sharing", "check-for-updates"):
        api("PUT", "/setting/" + key, {"value": False})
    return links


if __name__ == "__main__":
    try:
        print(json.dumps(bootstrap(), indent=2))
    except (RuntimeError, ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
