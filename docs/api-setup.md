# Free API registration

The user has supplied the registration email in the session. No account has been
registered by this build. Keep the address out of tracked project files.

- EIA: https://www.eia.gov/opendata/register.php
- PJM Data Miner: https://dataminer2.pjm.com/ and https://apiportal.pjm.com/

Use the free access route and review the current provider terms and quotas.
Keep the key in the local environment variable `EIA_API_KEY` (the direct PJM route is retired in plan v2); do not
paste them into chat or commit them. If a key must be transferred to the agent,
use the application's private secret-entry card.

EIA's public DEMO_KEY enabled a bounded live check of the fuel-type endpoint on
October 28: hourly UTC data, MWh units, PJM respondent, eight fuel codes and
four-page pagination were verified. See `docs/evidence/eia-live-2026-10-28.json`.
This does not replace free personal registration or establish production quotas.

PJM status on October 29: `api.pjm.com` answered HTTP 401 (subscription key
required) when reached by IP, so the request shape is ready but unauthenticated.
With ProtonVPN connected, its resolver (10.2.0.1) times out on every `*.pjm.com`
name while public resolvers return addresses. Disconnect the VPN, exclude PJM via
split tunneling, or change its DNS before fetching or registering.

Still verify PJM real-time hourly LMP, BGE node metadata, date semantics,
pagination, response fields, licensing and quota limits before operational use.
