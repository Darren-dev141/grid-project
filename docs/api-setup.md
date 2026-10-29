# Free API registration

Registration email is pending. No account has been registered by this build.

- EIA: https://www.eia.gov/opendata/register.php
- PJM Data Miner: https://dataminer2.pjm.com/ and https://apiportal.pjm.com/

Use the free access route and review the current provider terms and quotas.
Keep keys in local environment variables `EIA_API_KEY` and `PJM_API_KEY`; do not
paste them into chat or commit them. If a key must be transferred to the agent,
use the application's private secret-entry card.

Before live implementation, verify the current EIA v2 fuel-type endpoint,
PJM real-time hourly LMP endpoint, BGE node metadata, date semantics, pagination,
response fields, licensing and quota limits against provider documentation.
The offline tests use synthetic envelope shapes; they do not certify today's API.
