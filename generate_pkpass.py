#!/usr/bin/env python3
"""
Generate an Apple Wallet .pkpass boarding pass from Ryanair API data.

Usage:
    # Unsigned (works with Android wallet apps like WalletPasses, Pass2U, PassAndroid):
    python generate_pkpass.py --boarding-pass boarding_pass.json

    # Signed (works with Apple Wallet on iOS):
    python generate_pkpass.py --boarding-pass boarding_pass.json \
        --cert certificate.pem --key key.pem --wwdr wwdr.pem \
        --pass-type-id pass.com.example.boarding --team-id ABCDE12345

    # Fetch from Ryanair API and generate:
    python generate_pkpass.py --session-token <token>

Signing setup (for Apple Wallet):
    1. Join Apple Developer Program ($99/year)
    2. Create a Pass Type ID at developer.apple.com > Certificates, Identifiers & Profiles
    3. Create a certificate for that Pass Type ID, download and export as .pem
    4. Download the Apple WWDR G4 certificate:
       https://www.apple.com/certificateauthority/AppleWWDRCAG4.cer
       Convert: openssl x509 -inform DER -in AppleWWDRCAG4.cer -out wwdr.pem

Requirements:
    pip install cryptography requests  # requests only needed for --session-token
"""

import argparse
import hashlib
import io
import json
import os
import sys
import zipfile


# Ryanair brand colors
RYANAIR_BLUE = "rgb(7, 48, 105)"
RYANAIR_YELLOW = "rgb(255, 200, 0)"
RYANAIR_WHITE = "rgb(255, 255, 255)"


def build_pass_json(pnr: str, bp: dict, pass_type_id: str, team_id: str) -> dict:
    """Build the pass.json dict from a Ryanair boarding pass response."""
    name = bp.get("name", {})
    passenger_name = f"{name.get('last', '')}/{name.get('first', '')}"
    passenger_display = f"{name.get('title', '')} {name.get('first', '')} {name.get('last', '')}".strip()
    flight_number = bp.get("flightNumber", "")
    carrier_code = bp.get("carrierCode", "FR")
    seat = bp.get("seat", {})
    departure = bp.get("departure", {})
    arrival = bp.get("arrival", {})
    sequence = bp.get("sequence", 0)
    boarding_time = bp.get("boardingTime", "")
    operated_by = bp.get("operatedBy", "Ryanair")

    # Build a unique serial number
    serial = f"{pnr}-{flight_number}-{bp.get('paxNum', 0)}"

    # Barcode: use the IATA BCBP payload
    barcode_payload = bp.get("barcode", {}).get("payload", "")

    barcode_dict = {
        "format": "PKBarcodeFormatAztec",
        "message": barcode_payload,
        "messageEncoding": "iso-8859-1",
    }

    pass_json = {
        "formatVersion": 1,
        "passTypeIdentifier": pass_type_id,
        "serialNumber": serial,
        "teamIdentifier": team_id,
        "organizationName": operated_by,
        "description": f"Boarding pass for {flight_number} {departure.get('code', '')} to {arrival.get('code', '')}",
        "logoText": operated_by,
        "backgroundColor": RYANAIR_BLUE,
        "foregroundColor": RYANAIR_WHITE,
        "labelColor": RYANAIR_YELLOW,
        # Both barcodes (iOS 9+) and barcode (legacy) for compatibility
        "barcodes": [barcode_dict],
        "barcode": barcode_dict,
        "boardingPass": {
            "transitType": "PKTransitTypeAir",
            "headerFields": [
                {
                    "key": "flight",
                    "label": "FLIGHT",
                    "value": flight_number,
                },
            ],
            "primaryFields": [
                {
                    "key": "origin",
                    "label": departure.get("name", departure.get("code", "")),
                    "value": departure.get("code", ""),
                },
                {
                    "key": "destination",
                    "label": arrival.get("name", arrival.get("code", "")),
                    "value": arrival.get("code", ""),
                },
            ],
            "secondaryFields": [
                {
                    "key": "passenger",
                    "label": "PASSENGER",
                    "value": passenger_display,
                },
                {
                    "key": "seat",
                    "label": "SEAT",
                    "value": seat.get("designator", ""),
                },
            ],
            "auxiliaryFields": [
                {
                    "key": "boardingTime",
                    "label": "BOARDING",
                    "value": boarding_time.replace(".000", "") if boarding_time else "",
                },
                {
                    "key": "seatLocation",
                    "label": "SEAT TYPE",
                    "value": seat.get("location", ""),
                },
                {
                    "key": "seq",
                    "label": "SEQ",
                    "value": str(sequence),
                },
                {
                    "key": "pnr",
                    "label": "PNR",
                    "value": pnr,
                },
            ],
            "backFields": [
                {
                    "key": "operatedBy",
                    "label": "Operated by",
                    "value": operated_by,
                },
                {
                    "key": "carrier",
                    "label": "Carrier code",
                    "value": carrier_code,
                },
                {
                    "key": "paxType",
                    "label": "Passenger type",
                    "value": bp.get("paxType", "ADT"),
                },
            ],
        },
    }

    # Add departure date as relevant date (for lock screen)
    dep_date = departure.get("date")
    if dep_date:
        pass_json["relevantDate"] = dep_date

    return pass_json


def create_icon_png() -> bytes:
    """Create a minimal 29x29 blue PNG icon (no external dependencies)."""
    import struct
    import zlib

    width, height = 29, 29
    # Ryanair blue: R=7, G=48, B=105
    r, g, b = 7, 48, 105

    # Build raw pixel data (each row: filter byte + RGB pixels)
    raw_data = b""
    for _ in range(height):
        raw_data += b"\x00"  # filter: none
        raw_data += bytes([r, g, b]) * width

    def make_chunk(chunk_type, data):
        chunk = chunk_type + data
        return struct.pack(">I", len(data)) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += make_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += make_chunk(b"IDAT", zlib.compress(raw_data))
    png += make_chunk(b"IEND", b"")
    return png


def sign_manifest(manifest_bytes: bytes, cert_path: str, key_path: str,
                   wwdr_path: str, key_password: str = None) -> bytes:
    """Sign manifest.json using PKCS7 with Apple certificates."""
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.serialization import pkcs7
    except ImportError:
        print("Install cryptography: pip install cryptography")
        sys.exit(1)

    with open(cert_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())

    password = key_password.encode() if key_password else None
    with open(key_path, "rb") as f:
        key = serialization.load_pem_private_key(f.read(), password=password)

    with open(wwdr_path, "rb") as f:
        wwdr = x509.load_pem_x509_certificate(f.read())

    return (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(manifest_bytes)
        .add_signer(cert, key, hashes.SHA256())
        .add_certificate(wwdr)
        .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature])
    )


def create_pkpass(pass_json: dict, sign: bool = False,
                  cert_path: str = None, key_path: str = None,
                  wwdr_path: str = None, key_password: str = None) -> bytes:
    """Create a .pkpass ZIP archive."""
    # Serialize pass.json
    pass_json_bytes = json.dumps(pass_json, indent=2).encode("utf-8")

    # Create icon (required)
    icon_png = create_icon_png()

    # All files to include
    files = {
        "icon.png": icon_png,
        "icon@2x.png": icon_png,
    }

    # Build manifest (SHA-1 hashes)
    manifest = {}
    manifest["pass.json"] = hashlib.sha1(pass_json_bytes).hexdigest()
    for name, data in files.items():
        manifest[name] = hashlib.sha1(data).hexdigest()
    manifest_bytes = json.dumps(manifest).encode("utf-8")

    # Sign if certificates provided
    signature_bytes = None
    if sign and cert_path and key_path and wwdr_path:
        signature_bytes = sign_manifest(
            manifest_bytes, cert_path, key_path, wwdr_path, key_password
        )

    # Build ZIP
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("pass.json", pass_json_bytes)
        zf.writestr("manifest.json", manifest_bytes)
        if signature_bytes:
            zf.writestr("signature", signature_bytes)
        for name, data in files.items():
            zf.writestr(name, data)

    return buf.getvalue()


def main():
    parser = argparse.ArgumentParser(
        description="Generate Apple Wallet .pkpass boarding pass from Ryanair data"
    )

    # Input source
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--boarding-pass",
        help="Path to boarding pass JSON file (from Ryanair API)",
    )
    group.add_argument(
        "--session-token",
        help="Ryanair x-session-token (fetches boarding pass first)",
    )

    # Signing (optional — required for Apple Wallet, not needed for Android apps)
    parser.add_argument("--cert", help="Path to signing certificate PEM")
    parser.add_argument("--key", help="Path to private key PEM")
    parser.add_argument("--wwdr", help="Path to Apple WWDR G4 certificate PEM")
    parser.add_argument("--key-password", help="Private key password (if encrypted)")

    # Pass identifiers (use placeholders for unsigned passes)
    parser.add_argument(
        "--pass-type-id",
        default="pass.com.ryanair.boardingpass",
        help="Pass Type Identifier (default: pass.com.ryanair.boardingpass)",
    )
    parser.add_argument(
        "--team-id",
        default="XXXXXXXXXX",
        help="Apple Developer Team ID (default: XXXXXXXXXX)",
    )

    # Output
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Output directory for .pkpass files (default: current dir)",
    )

    args = parser.parse_args()

    # Load boarding pass data
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

    # Determine if we should sign
    sign = all([args.cert, args.key, args.wwdr])
    if sign:
        print("Signing enabled (Apple Wallet compatible)")
    else:
        print("No signing certificates provided — generating unsigned .pkpass")
        print("(Works with Android apps: WalletPasses, Pass2U, PassAndroid)")
        print()

    pnr = data.get("pnr", "UNKNOWN")
    os.makedirs(args.output_dir, exist_ok=True)

    for i, bp in enumerate(data.get("boardingPasses", [])):
        name = bp.get("name", {})
        passenger = f"{name.get('first', '')} {name.get('last', '')}".strip()
        flight = bp.get("flightNumber", "unknown")
        dep = bp.get("departure", {}).get("code", "")
        arr = bp.get("arrival", {}).get("code", "")
        seat = bp.get("seat", {}).get("designator", "")

        print(f"Passenger: {passenger}")
        print(f"  Flight:  {flight} {dep} -> {arr}")
        print(f"  Seat:    {seat}")

        pass_json = build_pass_json(pnr, bp, args.pass_type_id, args.team_id)
        pkpass_bytes = create_pkpass(
            pass_json,
            sign=sign,
            cert_path=args.cert,
            key_path=args.key,
            wwdr_path=args.wwdr,
            key_password=args.key_password,
        )

        filename = f"boarding_pass_{name.get('last', 'unknown').lower()}_{flight}_{dep}{arr}.pkpass"
        filepath = os.path.join(args.output_dir, filename)
        with open(filepath, "wb") as f:
            f.write(pkpass_bytes)

        size_kb = len(pkpass_bytes) / 1024
        print(f"  Saved:   {filepath} ({size_kb:.1f} KB)")
        print()


if __name__ == "__main__":
    main()
