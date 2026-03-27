#!/usr/bin/env python3
"""
Generate a QR code from an IATA BCBP barcode payload.

Usage:
    python generate_qr.py "<bcbp-payload>" [output.png]
    python generate_qr.py  # uses example payload

Requirements:
    pip install qrcode[pil]
"""

import sys

try:
    import qrcode
except ImportError:
    print("Install qrcode: pip install qrcode[pil]")
    sys.exit(1)


def generate_qr(payload: str, output_path: str = "boarding_pass_qr.png") -> None:
    """Generate a QR code image from a BCBP payload string."""
    qr = qrcode.QRCode(
        version=None,  # auto-detect size
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(output_path)
    print(f"QR code saved to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        payload = sys.argv[1]
    else:
        payload = (
            "M1DOE/JOHN            ABC123 DUBLHRFR 1234 087Y015A0042 "
            "100>5181W 6086BFR 00000000000000A0000000000000 0"
            "                          NN"
        )
        print("Using example payload (pass your own as first argument)\n")

    output = sys.argv[2] if len(sys.argv) > 2 else "boarding_pass_qr.png"
    generate_qr(payload, output)
