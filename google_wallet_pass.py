#!/usr/bin/env python3
"""
Generate an "Add to Google Wallet" URL for a Ryanair boarding pass.

Usage:
    # From Ryanair API response (JSON file):
    python google_wallet_pass.py --boarding-pass boarding_pass.json --key service-account.json --issuer-id 3388000000012345678

    # From session token (fetches boarding pass first):
    python google_wallet_pass.py --session-token <token> --key service-account.json --issuer-id 3388000000012345678

Setup:
    1. Create a Google Pay & Wallet Console issuer account:
       https://pay.google.com/business/console
    2. Create a Google Cloud service account and download the JSON key
    3. Link the service account to your issuer in the Wallet Console
    4. Enable the Google Wallet API in your Cloud project

Requirements:
    pip install google-auth requests
"""

import argparse
import json
import sys
import time

try:
    from google.auth import crypt, jwt
except ImportError:
    print("Install google-auth: pip install google-auth")
    sys.exit(1)


def build_flight_class(issuer_id: str, bp: dict) -> dict:
    """Build a Google Wallet FlightClass from boarding pass data."""
    carrier_code = bp.get("carrierCode", "FR")
    flight_num = bp.get("flightNumber", "").replace(carrier_code, "")
    departure_date = bp["departure"]["date"].split("T")[0]
    class_suffix = f"{carrier_code}{flight_num}_{departure_date}"

    return {
        "id": f"{issuer_id}.{class_suffix}",
        "issuerName": bp.get("operatedBy", "Ryanair"),
        "reviewStatus": "UNDER_REVIEW",
        "localScheduledDepartureDateTime": bp["departure"]["date"],
        "localScheduledArrivalDateTime": bp["arrival"]["date"],
        "flightHeader": {
            "carrier": {
                "carrierIataCode": carrier_code,
            },
            "flightNumber": flight_num,
            "operatingCarrier": {
                "carrierIataCode": carrier_code,
            },
            "operatingFlightNumber": flight_num,
        },
        "origin": {
            "airportIataCode": bp["departure"]["code"],
            "terminal": bp.get("departureTerminal", ""),
            "gate": bp.get("departureGate", ""),
        },
        "destination": {
            "airportIataCode": bp["arrival"]["code"],
        },
    }


def build_flight_object(issuer_id: str, pnr: str, bp: dict, class_id: str) -> dict:
    """Build a Google Wallet FlightObject from boarding pass data."""
    carrier_code = bp.get("carrierCode", "FR")
    flight_num = bp.get("flightNumber", "").replace(carrier_code, "")
    departure_date = bp["departure"]["date"].split("T")[0]
    seq = bp.get("sequence", 0)
    pax_num = bp.get("paxNum", 0)
    object_suffix = f"{carrier_code}{flight_num}_{departure_date}_pax{pax_num}_seq{seq}"

    name = bp.get("name", {})
    passenger_name = f"{name.get('first', '')} {name.get('last', '')}".strip()

    flight_object = {
        "id": f"{issuer_id}.{object_suffix}",
        "classId": class_id,
        "state": "ACTIVE",
        "passengerName": passenger_name,
        "reservationInfo": {
            "confirmationCode": pnr,
        },
        "boardingAndSeatingInfo": {
            "seatNumber": bp.get("seat", {}).get("designator", ""),
            "sequenceNumber": str(seq),
        },
    }

    # Add boarding time if available
    boarding_time = bp.get("boardingTime")
    if boarding_time:
        flight_object["boardingAndSeatingInfo"]["boardingDateTime"] = boarding_time

    # Add the BCBP barcode
    barcode_payload = bp.get("barcode", {}).get("payload")
    if barcode_payload:
        flight_object["barcode"] = {
            "type": "AZTEC",
            "value": barcode_payload,
            "alternateText": pnr,
        }

    return flight_object


def generate_wallet_url(service_account_file: str, issuer_id: str, data: dict) -> list:
    """
    Generate "Add to Google Wallet" URLs for each boarding pass.

    Returns a list of (passenger_name, url) tuples.
    """
    signer = crypt.RSASigner.from_service_account_file(service_account_file)

    with open(service_account_file) as f:
        sa_info = json.load(f)
    service_account_email = sa_info["client_email"]

    pnr = data.get("pnr", "")
    results = []

    for bp in data.get("boardingPasses", []):
        flight_class = build_flight_class(issuer_id, bp)
        flight_object = build_flight_object(issuer_id, pnr, bp, flight_class["id"])

        claims = {
            "iss": service_account_email,
            "aud": "google",
            "typ": "savetowallet",
            "iat": int(time.time()),
            "origins": [],
            "payload": {
                "flightClasses": [flight_class],
                "flightObjects": [flight_object],
            },
        }

        token = jwt.encode(signer, claims).decode("utf-8")
        url = f"https://pay.google.com/gp/v/save/{token}"

        name = bp.get("name", {})
        passenger_name = f"{name.get('first', '')} {name.get('last', '')}".strip()
        results.append((passenger_name, url))

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Generate 'Add to Google Wallet' URLs for Ryanair boarding passes"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--boarding-pass",
        help="Path to boarding pass JSON file (from Ryanair API response)",
    )
    group.add_argument(
        "--session-token",
        help="Ryanair x-session-token (fetches boarding pass first)",
    )
    parser.add_argument(
        "--key",
        required=True,
        help="Path to Google Cloud service account JSON key file",
    )
    parser.add_argument(
        "--issuer-id",
        required=True,
        help="Google Pay & Wallet Console issuer ID",
    )
    args = parser.parse_args()

    # Get boarding pass data
    if args.boarding_pass:
        with open(args.boarding_pass) as f:
            data = json.load(f)
    else:
        try:
            from fetch_boarding_pass import fetch_boarding_pass
        except ImportError:
            print("fetch_boarding_pass.py not found in current directory")
            sys.exit(1)
        print("Fetching boarding pass from Ryanair...")
        data = fetch_boarding_pass(args.session_token)

    # Generate URLs
    results = generate_wallet_url(args.key, args.issuer_id, data)

    if not results:
        print("No boarding passes found in data")
        sys.exit(1)

    for passenger_name, url in results:
        print(f"\n{'=' * 60}")
        print(f"  Passenger: {passenger_name}")
        print(f"{'=' * 60}")
        print(f"\nAdd to Google Wallet:")
        print(url)
        print()


if __name__ == "__main__":
    main()
