#!/usr/bin/env python3
"""
Generate a barcode image from an IATA BCBP barcode payload.

Supports Aztec (what Ryanair uses) and QR code formats.

Usage:
    python generate_qr.py "<bcbp-payload>" [output.png]              # Aztec (default)
    python generate_qr.py "<bcbp-payload>" [output.png] --format qr  # QR code
    python generate_qr.py  # uses example payload

Requirements:
    pip install treepoem   # for Aztec (recommended — matches Ryanair's format)
    pip install qrcode[pil]  # for QR code fallback
"""

import argparse
import sys


def generate_aztec(payload: str, output_path: str = "boarding_pass_aztec.png") -> None:
    """Generate an Aztec code image from a BCBP payload string.

    This matches the barcode format Ryanair actually uses.
    """
    try:
        import treepoem
    except ImportError:
        print("Install treepoem for Aztec codes: pip install treepoem")
        print("(treepoem requires Ghostscript: apt install ghostscript / brew install ghostscript)")
        sys.exit(1)

    img = treepoem.generate_barcode(
        barcode_type="azteccode",
        data=payload,
        options={"format": "full"},
    )
    # treepoem returns a PIL image; resize for better scanning
    img = img.convert("L")  # grayscale
    scale = max(1, 400 // max(img.size))
    if scale > 1:
        img = img.resize(
            (img.size[0] * scale, img.size[1] * scale),
            resample=0,  # nearest neighbor for sharp edges
        )
    img.save(output_path)
    print(f"Aztec code saved to {output_path}")


def generate_qr(payload: str, output_path: str = "boarding_pass_qr.png") -> None:
    """Generate a QR code image from a BCBP payload string."""
    try:
        import qrcode
    except ImportError:
        print("Install qrcode: pip install qrcode[pil]")
        sys.exit(1)

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


def generate_barcode(payload: str, output_path: str, fmt: str = "aztec") -> None:
    """Generate a barcode image in the specified format."""
    if fmt == "aztec":
        generate_aztec(payload, output_path)
    elif fmt == "qr":
        generate_qr(payload, output_path)
    else:
        print(f"Unknown format: {fmt}. Use 'aztec' or 'qr'.")
        sys.exit(1)


EXAMPLE_PAYLOAD = (
    "M1DOE/JOHN            ABC123 DUBLHRFR 1234 087Y015A0042 "
    "100>5181W 6086BFR 00000000000000A0000000000000 0"
    "                          NN"
)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a barcode from an IATA BCBP payload"
    )
    parser.add_argument(
        "payload",
        nargs="?",
        default=None,
        help="BCBP barcode payload string",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Output image path (default: boarding_pass_<format>.png)",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["aztec", "qr"],
        default="aztec",
        help="Barcode format: aztec (default, matches Ryanair) or qr",
    )
    args = parser.parse_args()

    payload = args.payload
    if not payload:
        payload = EXAMPLE_PAYLOAD
        print("Using example payload (pass your own as first argument)\n")

    output = args.output or f"boarding_pass_{args.format}.png"
    generate_barcode(payload, output, args.format)
