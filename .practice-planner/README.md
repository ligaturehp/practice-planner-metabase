# Practice Planner Analytics

This is the deployment layer for the Metabase fork at stable OSS v0.63.16 (upstream commit 72a49b19fa81e047936b70520324eb9b744ae2a1). It uses that upstream release image and preserves the upstream source and license notices. Customizations are confined to this directory.

The dashboard uses the existing Metabase interface and individual accounts. The initial owner is admin@ligaturehp.com. A second person can be added through Admin settings → People when needed. Public sharing, embedding, external AI, version checks, and outbound usage tracking are disabled in the entrypoint.

Run the dashboard and a separate analytics PostgreSQL service in the same Railway project/environment. Use the Railway-generated dashboard address. PostgreSQL needs a persistent volume. Keep its port private. Metabase's writable application database is separate from its read-only analytics connection; neither connects to the live planner database.

Deploy branch codex/practice-planner-analytics. Apply railway-service.json to this service's native settings through Railway's serviceInstanceUpdate API (or enter the same Dockerfile path, watch path, healthcheck, restart policy, and replica count in the dashboard). Scope the update to this analytics service and environment. New services no longer accept railway.toml; see [Railway configuration changes](https://docs.railway.com/infrastructure-as-code#migrating-from-config-as-code). Required environment variables:

- MB_DB_HOST: private analytics PostgreSQL hostname
- MB_DB_PORT: 5432
- MB_DB_DBNAME: metabase_app
- MB_DB_USER: metabase_app
- MB_DB_PASS: its password
- MB_ENCRYPTION_SECRET_KEY: independent random secret
- MB_SITE_URL: generated HTTPS dashboard address, once provisioned

Apply the analytics schema with the migration command in the Practice Planner repository, then run provision-postgres.sql as the analytics database owner. It reads ANALYTICS_READER_PASSWORD, ANALYTICS_WRITER_PASSWORD, and METABASE_APP_PASSWORD from the process environment. Credentials stay in Railway variables.

Complete initial administrator setup over a private/loopback connection before creating the public Railway domain. The bootstrap script provisions the initial user, a read-only PostgreSQL connection, and the versioned dashboard questions. Its credentials come from environment variables, never command-line values or committed files.

Run `python3 .practice-planner/bootstrap.py` with METABASE_URL, METABASE_ADMIN_EMAIL, METABASE_ADMIN_PASSWORD, ANALYTICS_DB_HOST, and ANALYTICS_READER_PASSWORD in the environment. Optional ANALYTICS_DB_PORT defaults to 5432, ANALYTICS_DB_NAME to analytics, and ANALYTICS_DB_SSL to false for the Railway private network. Bootstrap owns one named collection and refuses to replace unmanaged questions with matching names. Re-running it updates questions and layouts without duplicating them. It never changes an existing database connection's destination or password.

Run `python3 .practice-planner/verify.py` with the same environment to check all 18 default and filtered queries, repeatable provisioning, read-only database privileges, and disabled sharing/tracking. The check updates only the managed collection through bootstrap; it does not insert analytics events.

Keep production analytics empty until the instrumented planner release is approved. Verify dashboards against synthetic data in a separate database. Account/login totals include unlinked lifecycle records; personal interaction, active-time, and editing histories cover accounts that enabled usage analytics.

An analytics-retention Railway cron service uses postgres:17-alpine (pinned digest sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73) and retention-service.json. Set PGHOST to the private analytics PostgreSQL host, PGPORT=5432, PGDATABASE=analytics, PGUSER=postgres, PGPASSWORD from that database's owner secret, and PGCONNECT_TIMEOUT=10. It removes raw events older than 90 days daily at 07:17 UTC. It has no public domain or persistent process between runs. The planner's analytics maintenance CLI performs the same operation when run manually. Returning-user measures are limited to retained history.

Before upgrading, back up both databases, update the pinned release deliberately, and rerun bootstrap/API and browser verification.
