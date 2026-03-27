#!/usr/bin/env python3
"""
Fetch your Ryanair boarding pass and optionally generate a QR code.

Usage:
    python fetch_boarding_pass.py --session-token <token>
    python fetch_boarding_pass.py --session-token <token> --qr

The session token can be found in browser DevTools:
1. Log in to ryanair.com and navigate to your trip
2. Open DevTools (F12) -> Network tab -> filter by Fetch/XHR
3. Find a request to /api/booking/ and copy the x-session-token header

Requirements:
    pip install requests
    pip install qrcode[pil]  # only for --qr flag
"""

import argparse
import json
import sys

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)


BOARDING_PASS_URL = (
    "https://www.ryanair.com/api/booking/boarding-pass/v6/en-gb/boardingPass"
)


def fetch_boarding_pass(session_token: str) -> dict:
    """Fetch boarding pass data from Ryanair API."""
    headers = {
        "accept": "application/json",
        "client": "desktop",
        "client-version": "1.13.0",
        "x-session-token": session_token,
    }

    response = requests.get(BOARDING_PASS_URL, headers=headers)
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description="Fetch Ryanair boarding pass")
    parser.add_argument(
        "--session-token", required=True, help="x-session-token from browser"
    )
    parser.add_argument(
        "--qr", action="store_true", help="Generate QR code image(s)"
    )
    parser.add_argument(
        "--output", default=None, help="Output JSON file (default: stdout)"
    )
    args = parser.parse_args()

    print(f"Fetching boarding pass...")
    data = fetch_boarding_pass(args.session_token)

    # Output JSON
    formatted = json.dumps(data, indent=2)
    if args.output:
        with open(args.output, "w") as f:
            f.write(formatted)
        print(f"Saved to {args.output}")
    else:
        print(formatted)

    # Generate QR codes
    if args.qr:
        try:
            from generate_qr import generate_qr
        except ImportError:
            print("\nInstall qrcode for QR generation: pip install qrcode[pil]")
            return

        for i, bp in enumerate(data.get("boardingPasses", [])):
            payload = bp.get("barcode", {}).get("payload")
            if not payload:
                print(f"\nPassenger {i}: No barcode payload found")
                continue

            name = f"{bp['name']['first']} {bp['name']['last']}"
            filename = f"boarding_pass_{bp['name']['last'].lower()}_{i}.png"
            print(f"\nPassenger {i}: {name}")
            print(f"  Flight: {bp['flightNumber']}")
            print(f"  Route:  {bp['departure']['code']} -> {bp['arrival']['code']}")
            print(f"  Seat:   {bp['seat']['designator']}")
            generate_qr(payload, filename)


if __name__ == "__main__":
    main()
