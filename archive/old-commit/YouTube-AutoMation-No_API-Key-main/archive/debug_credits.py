"""Debug: check the actual flow_client state and try /v1/credits with the real token."""
import asyncio
import httpx

async def main():
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Get health
        health = await client.get("http://127.0.0.1:8101/api/health")
        h = health.json()
        ws = h.get("ws_stats", {})
        print(f"extension_connected: {h.get('extension_connected')}")
        print(f"flow_key_present: {ws.get('flow_key_present')}")
        print(f"token_age_s: {ws.get('token_age_s')}")
        print(f"request_count: {ws.get('request_count')}")
        print(f"failed_count: {ws.get('failed_count')}")
        print(f"last_error: {ws.get('last_error')}")

        # Trigger scan and check result
        scan = await client.post("http://127.0.0.1:8101/api/auth/scan")
        s = scan.json()
        print(f"\nscan result: {s}")

        # Now try calling /v1/credits directly through the agent
        # by hitting a debug endpoint that shows the token state
        # We can't get the token directly, but we can check if the
        # agent's flow_client has it by checking the scan result
        # more carefully

        # The key insight: scan shows tier_fetched=False but extension is
        # connected. This means fetch_paygate_tier() was called and returned
        # False. Let's see why by checking if _flow_key is populated.
        # We can't access it directly from outside the process, but we
        # can infer: if token_age_s is set but tier_fetched is False,
        # the token exists but the /v1/credits call failed.

        # Let's try the credits call ourselves with a fresh token
        # captured from the browser. We can't do that, but we can
        # test if the endpoint works at all by checking the error format.

        print(f"\n=== Checking if /v1/credits endpoint is reachable ===")
        resp = await client.get(
            "https://aisandbox-pa.googleapis.com/v1/credits",
            params={"key": "AIzaSyBtrm0o5ab1c-Ec8ZuLcGt3oJAA5VWt3pY"},
            headers={
                "origin": "https://labs.google",
                "referer": "https://labs.google/",
            },
        )
        print(f"  status: {resp.status_code}")
        body = resp.json()
        print(f"  error message: {body.get('error', {}).get('message', 'N/A')[:200]}")
        print(f"  error reason: {[d.get('reason') for d in body.get('error', {}).get('details', [])]}")

if __name__ == "__main__":
    asyncio.run(main())
