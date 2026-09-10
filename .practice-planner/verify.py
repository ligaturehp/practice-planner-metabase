#!/usr/bin/env python3
"""Integration check against a running Metabase; same environment as bootstrap."""

import bootstrap as b
from dashboards import DAY_WINDOW, WINDOW


def verify():
    names = [q["name"] for d in b.DASHBOARDS for q in d["questions"]]
    queries = {q["name"]: q["sql"] for d in b.DASHBOARDS for q in d["questions"]}
    assert len(names) == len(set(names)), "Question names must be unique"
    first = b.bootstrap()
    before = {(c["id"], c["name"]) for c in b.api("GET", "/card")}
    assert first == b.bootstrap(), "Dashboard IDs changed during reprovisioning"
    assert before == {(c["id"], c["name"]) for c in b.api("GET", "/card")}, "Reprovisioning duplicated questions"
    cards = [c for c in b.api("GET", "/card") if c["name"] in names and (c.get("description") or "").startswith(b.MARKER)]
    assert len(cards) == len(names)
    for card in cards:
        result = b.api("POST", f"/card/{card['id']}/query", {"parameters": []})
        assert result.get("status") == "completed", f"Query failed: {card['name']}"
        parameters = [{"id": "days", "type": "number/=", "target": ["variable", ["template-tag", "days"]], "value": 7}]
        for name in ("route", "actor", "control"):
            if name in b.tags(queries[card["name"]]):
                parameters.append({"id": name, "type": "string/=", "target": ["variable", ["template-tag", name]], "value": "no_matching_value"})
        result = b.api("POST", f"/card/{card['id']}/query", {"parameters": parameters})
        assert result.get("status") == "completed", f"Filtered query failed: {card['name']}"
    database_id = cards[0]["database_id"]
    privilege_query = "SELECT current_user, has_table_privilege(current_user,'analytics.events','SELECT'), has_table_privilege(current_user,'analytics.events','INSERT'), has_table_privilege(current_user,'analytics.raw_interactions','SELECT')"
    result = b.api("POST", "/dataset", {"database": database_id, "type": "native", "native": {"query": privilege_query}})
    assert result["data"]["rows"] == [["analytics_reader", False, False, True]], "Reader privileges are too broad"
    boundary_query = "WITH samples AS (SELECT occurred_at, (occurred_at AT TIME ZONE 'UTC')::date AS day FROM generate_series(now()-interval '100 days',now(),interval '1 hour') AS occurred_at) SELECT count(*) FROM samples WHERE (" + WINDOW.replace("{{days}}", "7") + ") <> (" + DAY_WINDOW.replace("{{days}}", "7") + ")"
    result = b.api("POST", "/dataset", {"database": database_id, "type": "native", "native": {"query": boundary_query}})
    assert result["data"]["rows"] == [[0]], "Daily and event cards disagree at the UTC period boundary"
    effective = b.api("GET", "/session/properties")
    for setting in ("anon-tracking-enabled", "metaplow-tracking-enabled", "enable-public-sharing", "check-for-updates", "enable-embedding", "enable-embedding-sdk", "enable-embedding-static", "enable-embedding-interactive", "enable-embedding-simple", "ai-features-enabled?"):
        assert effective.get(setting) is False, f"Setting is not disabled: {setting}"
    print(f"Passed: {len(cards)} default and filtered queries, stable provisioning, read-only access, private settings")


if __name__ == "__main__":
    verify()
