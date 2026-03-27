#!/usr/bin/env python3
"""
Decode an IATA BCBP (Bar Coded Boarding Pass) string.

Usage:
    python decode_bcbp.py "<bcbp-payload>"
    python decode_bcbp.py  # uses example payload

Reference: IATA Resolution 792, BCBP Implementation Guide v7
"""

import sys
from datetime import datetime, timedelta


def julian_to_date(julian_day: int, year: int = None) -> str:
    """Convert Julian day-of-year to a date string."""
    if year is None:
        year = datetime.now().year
    date = datetime(year, 1, 1) + timedelta(days=julian_day - 1)
    return date.strftime("%Y-%m-%d")


def decode_bcbp(payload: str) -> dict:
    """Decode a BCBP barcode payload string into structured fields."""
    if len(payload) < 58:
        raise ValueError(f"Payload too short ({len(payload)} chars, minimum 58)")

    result = {
        "raw": payload,
        "format_code": payload[0],
        "number_of_legs": int(payload[1]),
        "passenger_name": payload[2:22].strip(),
        "electronic_ticket_indicator": payload[22],
        "pnr": payload[23:30].strip(),
        "from_airport": payload[30:33],
        "to_airport": payload[33:36],
        "operating_carrier": payload[36:39].strip(),
        "flight_number": payload[39:44].strip(),
        "julian_date": payload[44:47],
        "compartment_code": payload[47],
        "seat_number": payload[48:52].strip(),
        "checkin_sequence": payload[52:57].strip(),
        "passenger_status": payload[57],
    }

    # Parse Julian date
    try:
        julian_day = int(result["julian_date"])
        result["flight_date"] = julian_to_date(julian_day)
    except ValueError:
        result["flight_date"] = "unknown"

    # Parse compartment code
    compartment_map = {
        "F": "First",
        "A": "First (discounted)",
        "J": "Business",
        "C": "Business",
        "D": "Business (discounted)",
        "W": "Premium Economy",
        "Y": "Economy",
        "B": "Economy",
        "H": "Economy",
        "K": "Economy",
        "L": "Economy",
        "M": "Economy",
        "N": "Economy",
        "Q": "Economy",
        "T": "Economy",
        "V": "Economy",
        "X": "Economy",
        "G": "Economy",
        "O": "Economy",
    }
    result["compartment"] = compartment_map.get(
        result["compartment_code"], "Unknown"
    )

    # Parse conditional section
    conditional_start = payload.find(">")
    if conditional_start != -1:
        cond = payload[conditional_start + 1 :]
        if len(cond) >= 4:
            result["conditional"] = {
                "version": cond[0],
                "unique_conditional_size": cond[1:4],
            }

            if len(cond) >= 5:
                pax_desc_map = {
                    "0": "Adult",
                    "1": "Male",
                    "2": "Female",
                    "3": "Child",
                    "4": "Infant",
                    "5": "No passenger (cabin baggage)",
                    "6": "Adult (animal in cabin)",
                    "7": "Unaccompanied minor",
                    "W": "Adult male",
                }
                pax_code = cond[4]
                result["conditional"]["passenger_description"] = (
                    pax_desc_map.get(pax_code, f"Unknown ({pax_code})")
                )

            if len(cond) >= 6:
                checkin_source_map = {
                    "W": "Web",
                    "K": "Airport kiosk",
                    "R": "Remote/off-site kiosk",
                    "M": "Mobile device",
                    "O": "Airport agent",
                    "T": "Town agent",
                    "V": "Third party vendor",
                    " ": "Not set",
                }
                src = cond[5]
                result["conditional"]["source_of_checkin"] = (
                    checkin_source_map.get(src, f"Unknown ({src})")
                )

            if len(cond) >= 7:
                bp_source_map = {
                    "W": "Web",
                    "K": "Airport kiosk",
                    "X": "Transfer kiosk",
                    "R": "Remote/off-site kiosk",
                    "M": "Mobile device",
                    "O": "Airport agent",
                    "T": "Town agent",
                    "V": "Third party vendor",
                    "6": "Online",
                    " ": "Not set",
                }
                src = cond[6]
                result["conditional"]["source_of_boarding_pass"] = (
                    bp_source_map.get(src, f"Unknown ({src})")
                )

            if len(cond) >= 10:
                try:
                    bp_julian = int(cond[7:10])
                    result["conditional"]["bp_issue_date"] = julian_to_date(bp_julian)
                except ValueError:
                    pass

            if len(cond) >= 11:
                doc_type_map = {
                    "B": "Boarding pass",
                    "I": "Itinerary receipt",
                }
                doc = cond[10]
                result["conditional"]["document_type"] = (
                    doc_type_map.get(doc, f"Unknown ({doc})")
                )

            if len(cond) >= 14:
                result["conditional"]["bp_issuer_airline"] = cond[11:14].strip()

    return result


def print_bcbp(decoded: dict) -> None:
    """Pretty-print decoded BCBP data."""
    name_parts = decoded["passenger_name"].split("/")
    last_name = name_parts[0] if len(name_parts) > 0 else ""
    first_name = name_parts[1] if len(name_parts) > 1 else ""

    print("=" * 60)
    print("  IATA BCBP Boarding Pass Decode")
    print("=" * 60)
    print()
    print(f"  Passenger:     {first_name} {last_name}")
    print(f"  PNR:           {decoded['pnr']}")
    print(f"  Route:         {decoded['from_airport']} -> {decoded['to_airport']}")
    print(f"  Carrier:       {decoded['operating_carrier']}")
    print(f"  Flight:        {decoded['operating_carrier']}{decoded['flight_number']}")
    print(f"  Date:          {decoded['flight_date']} (Julian {decoded['julian_date']})")
    print(f"  Class:         {decoded['compartment']} ({decoded['compartment_code']})")
    print(f"  Seat:          {decoded['seat_number']}")
    print(f"  Sequence:      {decoded['checkin_sequence']}")
    print(f"  Legs:          {decoded['number_of_legs']}")
    print()

    if "conditional" in decoded:
        cond = decoded["conditional"]
        print("  Conditional Section:")
        print(f"    BCBP Version:    {cond.get('version', 'N/A')}")
        if "passenger_description" in cond:
            print(f"    Passenger type:  {cond['passenger_description']}")
        if "source_of_checkin" in cond:
            print(f"    Check-in source: {cond['source_of_checkin']}")
        if "source_of_boarding_pass" in cond:
            print(f"    BP source:       {cond['source_of_boarding_pass']}")
        if "bp_issue_date" in cond:
            print(f"    BP issued:       {cond['bp_issue_date']}")
        if "document_type" in cond:
            print(f"    Document type:   {cond['document_type']}")
        if "bp_issuer_airline" in cond:
            print(f"    BP issuer:       {cond['bp_issuer_airline']}")
        print()

    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        payload = sys.argv[1]
    else:
        # Example payload (fictional data)
        payload = (
            "M1DOE/JOHN            ABC123 DUBLHRFR 1234 087Y015A0042 "
            "100>5181W 6086BFR 00000000000000A0000000000000 0"
            "                          NN"
        )
        print("Using example payload (pass your own as first argument)\n")

    decoded = decode_bcbp(payload)
    print_bcbp(decoded)
