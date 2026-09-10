"""Versioned questions, using only the analytics reader's reporting views."""

WINDOW = "occurred_at >= (((now() AT TIME ZONE 'UTC')::date - greatest(1, least({{days}}, 90)) + 1)::timestamp AT TIME ZONE 'UTC')"
DAY_WINDOW = "day >= (now() AT TIME ZONE 'UTC')::date - greatest(1, least({{days}}, 90)) + 1"
DETAIL_FILTERS = "[[AND route = {{route}}]] [[AND actor_id = {{actor}}]]"
COVERAGE = "Personal activity covers users who enabled usage analytics. Periods include today and the preceding UTC calendar days; raw history is retained for 90 days."


def question(name, sql, description, display="table", dimensions=None, metrics=None):
    settings = {}
    if dimensions:
        settings = {"graph.dimensions": dimensions, "graph.metrics": metrics}
    return dict(name=name, sql=sql, description=description, display=display,
                visualization_settings=settings)


DASHBOARDS = [
    {
        "name": "Usage overview",
        "description": "Account and login totals include unlinked records from users who have not opted in. " + COVERAGE,
        "questions": [
            question("New accounts", f"SELECT coalesce(sum(new_accounts),0) AS new_accounts FROM analytics.daily_accounts WHERE {DAY_WINDOW}", "Successful account creations recorded after collection was enabled; no historical backfill.", "scalar"),
            question("Successful logins", f"SELECT coalesce(sum(logins),0) AS logins FROM analytics.daily_logins WHERE {DAY_WINDOW}", "Successful credential logins, including unlinked totals. An existing session does not count as a new login.", "scalar"),
            question("Observed active users", f"SELECT count(DISTINCT actor_id) AS active_users FROM analytics.raw_interactions WHERE {WINDOW} AND name IN ('page_viewed','ui_click','active_time','day_plan_opened','plan_created','plan_updated','day_plan_created','day_plan_updated','day_plan_event_created','day_plan_event_updated','day_plan_event_deleted')", "Distinct consenting users with recorded interaction or planning activity during this period.", "scalar"),
            question("Foreground active hours", f"SELECT round(coalesce(sum((properties->>'active_ms')::numeric),0)/3600000,2) AS active_hours FROM analytics.raw_interactions WHERE {WINDOW} AND name='active_time'", "Consenting browser users' measured foreground activity. Pauses when hidden, unfocused or idle; coordinated across tabs.", "scalar"),
            question("Accounts and logins by day", "SELECT coalesce(a.day,l.day) AS day, coalesce(a.new_accounts,0) AS new_accounts, coalesce(l.logins,0) AS logins FROM analytics.daily_accounts a FULL JOIN analytics.daily_logins l USING(day) WHERE coalesce(a.day,l.day) >= (now() AT TIME ZONE 'UTC')::date - greatest(1,least({{days}},90)) + 1 ORDER BY 1", "UTC daily totals recorded since analytics launch.", "line", ["day"], ["new_accounts", "logins"]),
            question("Returning users by day", f"SELECT day, consenting_users, returning_users FROM analytics.daily_logins WHERE {DAY_WINDOW} ORDER BY day", "Returning means a consenting user logged in on an earlier UTC day within the retained 90-day history. Users without linked history are excluded.", "line", ["day"], ["consenting_users", "returning_users"]),
            question("Daily active users", f"SELECT day, active_users FROM analytics.daily_usage WHERE {DAY_WINDOW} ORDER BY day", "Distinct consenting users with observed activity on each UTC day.", "line", ["day"], ["active_users"]),
            question("Weekly active users", f"SELECT date_trunc('week', occurred_at AT TIME ZONE 'UTC')::date AS week, count(DISTINCT actor_id) AS active_users FROM analytics.raw_interactions WHERE {WINDOW} AND name IN ('page_viewed','ui_click','active_time','day_plan_opened','plan_created','plan_updated','day_plan_created','day_plan_updated','day_plan_event_created','day_plan_event_updated','day_plan_event_deleted') GROUP BY 1 ORDER BY 1", "Distinct consenting active users per UTC Monday-start week, limited to the selected period; edge weeks may be partial.", "bar", ["week"], ["active_users"]),
        ],
    },
    {
        "name": "Day planning",
        "description": "Creation is the first persisted schedule for a plan and day; the app may initialize this when a day is first opened. Edits are accepted settings or drill changes; replayed commands are excluded. " + COVERAGE,
        "questions": [
            question("Day plans created and edited", f"SELECT day, creations, edits FROM analytics.daily_day_plans WHERE {DAY_WINDOW} ORDER BY day", "Server-confirmed first day-schedule creations and subsequent settings or drill edits. First opening may initialize the schedule; reopening an existing schedule does not create another.", "line", ["day"], ["creations", "edits"]),
            question("Day planning rates", f"SELECT day, users AS planning_users, round(creations_per_user,2) AS creations_per_planning_user, round(edits_per_user,2) AS edits_per_planning_user FROM analytics.daily_day_plans WHERE {DAY_WINDOW} ORDER BY day DESC", "Daily events divided by distinct users who persisted a day creation or edit that day; this is a count per user, not a conversion percentage."),
            question("Browser save outcomes", f"SELECT properties->>'outcome' AS outcome, count(*) AS saves FROM analytics.raw_interactions WHERE {WINDOW} AND name='plan_save_observed' {DETAIL_FILTERS} GROUP BY 1 ORDER BY 2 DESC", "Completion outcomes observed by the browser, including conflicts and failures. Superseded saves do not count. These are separate from server persistence counts.", "bar", ["outcome"], ["saves"]),
            question("Day openings and persisted changes", f"SELECT route, name, count(*) AS events, count(DISTINCT actor_id) AS users FROM analytics.raw_interactions WHERE {WINDOW} AND name IN ('day_plan_opened','day_plan_created','day_plan_updated','day_plan_event_created','day_plan_event_updated','day_plan_event_deleted') {DETAIL_FILTERS} GROUP BY 1,2 ORDER BY 3 DESC", "Compare day openings with persisted activity to find flows worth inspecting. Counts are event volumes, not an ordered conversion funnel."),
        ],
    },
    {
        "name": "Friction and reliability",
        "description": "Use request latency, failures, and save outcomes to find slow or unsuccessful paths. " + COVERAGE,
        "questions": [
            question("Request latency and failures", f"SELECT route, count(*) AS requests, round(100.0 * count(*) FILTER (WHERE (properties->>'status')::int >= 400)/nullif(count(*),0),2) AS failure_percent, round(percentile_cont(0.5) WITHIN GROUP (ORDER BY (properties->>'duration_ms')::numeric)::numeric,1) AS p50_ms, round(percentile_cont(0.95) WITHIN GROUP (ORDER BY (properties->>'duration_ms')::numeric)::numeric,1) AS p95_ms FROM analytics.raw_interactions WHERE {WINDOW} AND name='request_completed' {DETAIL_FILTERS} GROUP BY 1 ORDER BY p95_ms DESC", "HTTP responses for observed consenting-user requests. Failure means status 400 or above and includes validation errors and conflicts. Times are server processing durations, excluding network latency."),
            question("Failed request details", f"SELECT occurred_at, route, properties->>'status' AS status, properties->>'duration_ms' AS duration_ms, actor_id, session_id, release FROM analytics.raw_interactions WHERE {WINDOW} AND name='request_completed' AND (properties->>'status')::int >= 400 {DETAIL_FILTERS} ORDER BY occurred_at DESC LIMIT 1000", "Most recent 1,000 matching failures. Filter actor and route to correlate with the interaction timeline."),
            question("Client error codes", f"SELECT route, properties->>'code' AS error_code, properties->>'client_release' AS client_release, count(*) AS errors FROM analytics.raw_interactions WHERE {WINDOW} AND name='client_error' {DETAIL_FILTERS} GROUP BY 1,2,3 ORDER BY 4 DESC", "Allowlisted error categories only. No error message, stack trace, request body, or entered content is collected."),
        ],
    },
    {
        "name": "Interaction explorer",
        "description": "Filter a route or pseudonymous actor, then inspect individual actions and related server outcomes. Actor and session IDs are hashes. " + COVERAGE,
        "questions": [
            question("Clicks by control", f"SELECT route, properties->>'control' AS control, properties->>'modality' AS modality, count(*) AS clicks, count(DISTINCT actor_id) AS users FROM analytics.raw_interactions WHERE {WINDOW} AND name='ui_click' {DETAIL_FILTERS} [[AND properties->>'control' = {{{{control}}}}]] GROUP BY 1,2,3 ORDER BY 4 DESC", "Individual activations of authored controls, including keyboard actions. No screen recording, entered values, or DOM text."),
            question("Active minutes by screen", f"SELECT route, round(sum((properties->>'active_ms')::numeric)/60000,2) AS active_minutes, count(DISTINCT actor_id) AS users FROM analytics.raw_interactions WHERE {WINDOW} AND name='active_time' {DETAIL_FILTERS} GROUP BY 1 ORDER BY 2 DESC", "Foreground active time on each normalized screen, excluding hidden, unfocused and idle intervals.", "bar", ["route"], ["active_minutes"]),
            question("Raw interaction timeline", f"SELECT occurred_at, name, source, route, actor_id, session_id, resource_id, release, properties, event_id FROM analytics.raw_interactions WHERE {WINDOW} {DETAIL_FILTERS} [[AND properties->>'control' = {{{{control}}}}]] ORDER BY occurred_at DESC, received_at DESC, event_id LIMIT 1000", "Latest 1,000 matching events. Use actor and time filters to investigate sequences; each row is a recorded event. Browser occurrence times can be approximate. Properties contain only validated identifiers, categories, and numeric details."),
        ],
    },
]
