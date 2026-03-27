# Ryanair Boarding Pass API

Reverse-engineered documentation of Ryanair's boarding pass generation flow, including API endpoints, authentication, and IATA BCBP barcode decoding.

This project provides tools to fetch your own boarding pass data and generate QR codes from Ryanair's API, without needing the Ryanair app.

> **Disclaimer**: This is for educational and personal use only. Use it to access your own booking data. The API is undocumented and may change at any time.

## Quick Start: Generate Your Boarding Pass

### 1. Install dependencies

```bash
pip install requests treepoem qrcode[pil] cryptography

# treepoem (for Aztec codes) requires Ghostscript:
# Ubuntu/Debian: sudo apt install ghostscript
# macOS:         brew install ghostscript
```

### 2. Get your session token

1. Open https://www.ryanair.com and log in
2. Navigate to your trip / booking
3. Open browser DevTools (F12) → **Network** tab → filter by `Fetch/XHR`
4. Look for any request to `/api/booking/` or `/api/bookingfa/`
5. Copy the `x-session-token` header value

> Session tokens expire after ~25 minutes of inactivity. Refresh the page to get a new one.

### 3. Fetch your boarding pass and generate a barcode

```bash
# Fetch boarding pass JSON and save it
python fetch_boarding_pass.py --session-token <your-token> --output boarding_pass.json

# Fetch and generate QR code images in one step
python fetch_boarding_pass.py --session-token <your-token> --qr
```

This calls Ryanair's boarding pass API:
```
GET https://www.ryanair.com/api/booking/boarding-pass/v6/en-gb/boardingPass
```

The response contains a `barcode.payload` field — this is the standard IATA BCBP string that encodes your boarding pass. The barcode is generated directly from this string.

### 4. Or generate from an existing BCBP string

If you already have the barcode payload (e.g. from the Ryanair API response):

```bash
# Aztec code (default — matches what Ryanair uses at the gate)
python generate_qr.py "M1DOE/JOHN            ABC123 DUBLHRFR 1234 087Y015A0042 ..."

# QR code (also works, but Ryanair natively uses Aztec)
python generate_qr.py "M1DOE/JOHN            ABC123 DUBLHRFR 1234 087Y015A0042 ..." --format qr
```

### 5. Add to a wallet app

```bash
# Generate .pkpass file (works with WalletPasses, Pass2U, PassAndroid on Android)
python generate_pkpass.py --boarding-pass boarding_pass.json

# For Apple Wallet (requires Apple Developer certificate):
python generate_pkpass.py --boarding-pass boarding_pass.json \
    --cert certificate.pem --key key.pem --wwdr wwdr.pem

# For Google Wallet (requires Google Cloud service account):
python google_wallet_pass.py --boarding-pass boarding_pass.json \
    --key service-account.json --issuer-id <your-issuer-id>
```

### 6. Decode a BCBP barcode

```bash
python decode_bcbp.py "M1DOE/JOHN            ABC123 DUBLHRFR 1234 087Y015A0042 ..."
```

Output:
```
============================================================
  IATA BCBP Boarding Pass Decode
============================================================

  Passenger:     JOHN DOE
  PNR:           ABC123
  Route:         DUB -> LHR
  Carrier:       FR
  Flight:        FR1234
  Date:          2026-03-28 (Julian 087)
  Class:         Economy (Y)
  Seat:          15A
  Sequence:      0042
```

---

## How Ryanair Generates Boarding Passes

### Flow Overview

```
Login/Retrieve Booking
        |
        v
POST /api/bookingfa/en-gb/graphql  (GetBooking)
        |  Returns: booking details, check-in status, sessionToken
        v
GET /api/booking/boarding-pass/v6/en-gb/boardingPass
        |  Returns: IATA BCBP barcode payload (server-generated)
        v
App renders barcode.payload as Aztec code
```

The boarding pass barcode is a standard **IATA BCBP** (Bar Coded Boarding Pass, Resolution 792) string generated server-side. The Ryanair app renders this string as an **Aztec code** (not QR — though both are supported by airport gate scanners).

### Architecture

Ryanair's web app is built with Angular and uses a micro-frontend architecture:

- **Main app**: Handles booking, check-in flow via GraphQL (`/api/bookingfa/en-gb/graphql`)
- **Boarding pass micro-app**: Separate lazy-loaded bundle (`boarding-pass_dist/`) with its own REST API (`/api/booking/boarding-pass/...`)

GraphQL introspection is disabled on the booking API.

## API Documentation

### 1. Get Booking (GraphQL)

Retrieves full booking details including check-in status.

```
POST https://www.ryanair.com/api/bookingfa/en-gb/graphql
```

**Headers:**
| Header | Value |
|--------|-------|
| `Authorization` | `Bearer <jwt-token>` |
| `Content-Type` | `application/json` |
| `client` | `desktop` |
| `client-version` | `4.173.0` |

**Request body:**
```json
{
  "query": "query GetBooking($sessionToken: String!, ...) { getBooking(sessionToken: $sessionToken, ...) { ...BookingCommon } }",
  "variables": {
    "sessionToken": "",
    "invalidateCache": false
  }
}
```

**Key response fields:**
```json
{
  "data": {
    "getBooking": {
      "info": {
        "pnr": "ABC123",
        "status": "Confirmed",
        "bookingId": 123456789
      },
      "journeys": [{
        "mobilebp": true,
        "flt": "FR 1234",
        "orig": "DUB",
        "dest": "LHR",
        "checkInOpenUtcDate": "...",
        "checkInCloseUtcDate": "..."
      }],
      "passengers": [{
        "segCheckin": [{
          "status": "reprint"
        }],
        "segSeats": [{
          "code": "15A"
        }]
      }],
      "sessionToken": "",
      "tripId": ""
    }
  }
}
```

**Check-in status values:**
- `"reprint"` — checked in, boarding pass available
- Other values indicate check-in is pending or in progress

### 2. Get Boarding Pass (REST)

Fetches the boarding pass with the BCBP barcode payload.

```
GET https://www.ryanair.com/api/booking/boarding-pass/v6/en-gb/boardingPass
```

**Headers:**
| Header | Value |
|--------|-------|
| `x-session-token` | `<session-token>` |
| `client` | `desktop` |
| `client-version` | `1.13.0` |
| `accept` | `application/json` |

**Authentication:** Session-based via `x-session-token` header + cookies (not the JWT Bearer token from GraphQL).

**Response:**
```json
{
  "pnr": "ABC123",
  "boardingPasses": [
    {
      "paxType": "ADT",
      "name": {
        "title": "MR",
        "first": "JOHN",
        "last": "DOE"
      },
      "barcode": {
        "payload": "M1DOE/JOHN            ABC123 DUBLHRFR 1234 087Y015A0042 100>5181W 6086BFR ..."
      },
      "flightNumber": "FR1234",
      "departure": {
        "code": "DUB",
        "name": "Dublin",
        "date": "2026-03-28T08:30:00+01:00"
      },
      "arrival": {
        "code": "LHR",
        "name": "London Heathrow",
        "date": "2026-03-28T09:50:00+01:00"
      },
      "seat": {
        "designator": "15A",
        "location": "Window",
        "door": 0
      },
      "sequence": 42,
      "boardingTime": "2026-03-28T08:00:00.000",
      "gateCloseTime": 30,
      "carrierCode": "FR",
      "operatedBy": "Ryanair",
      "mobileBp": true,
      "blockBarCode": {
        "barCodeBlocked": false
      }
    }
  ]
}
```

### 3. Known GraphQL Operations

Discovered from the frontend JavaScript bundles:

| Operation | Type | Description |
|-----------|------|-------------|
| `GetBooking` | Query | Full booking details |
| `GetPassengers` | Query | Passenger info |
| `GetSeatsQuery` | Query | Seat map / availability |
| `GetBasket` | Query | Shopping basket |
| `GetTotal` | Query | Price total |
| `CommitBooking` | Mutation | Finalize booking |
| `CreateBasket` | Mutation | Create shopping basket |
| `AssignSeat` | Mutation | Assign/change seat |
| `AddBag` | Mutation | Add baggage |
| `AddPriorityBoarding` | Mutation | Add priority boarding |
| `AddFastTrack` | Mutation | Add fast track |
| `Products` | Query | Available products/extras |

GraphQL introspection (`__schema`) is disabled.

## BCBP Barcode Format

The `barcode.payload` follows the [IATA BCBP standard](https://www.iata.org/en/programs/passenger/common-use/) (Resolution 792, version 5+).

### Mandatory Unique Section

| Offset | Length | Field | Example |
|--------|--------|-------|---------|
| 0 | 1 | Format code | `M` (BCBP) |
| 1 | 1 | Number of legs | `1` |
| 2 | 20 | Passenger name (LAST/FIRST) | `DOE/JOHN           ` |
| 22 | 1 | Electronic ticket indicator | ` ` |
| 23 | 7 | PNR code | `ABC123 ` |
| 30 | 3 | From airport (IATA) | `DUB` |
| 33 | 3 | To airport (IATA) | `LHR` |
| 36 | 3 | Operating carrier | `FR ` |
| 39 | 5 | Flight number | `1234 ` |
| 44 | 3 | Date of flight (Julian) | `087` (= Mar 28) |
| 47 | 1 | Compartment code | `Y` (Economy) |
| 48 | 4 | Seat number | `015A` |
| 52 | 5 | Check-in sequence | `0042 ` |
| 57 | 1 | Passenger status | ` ` |
| 58 | 2 | Conditional section size | `34` |

### Conditional Section (after `>`)

| Field | Value | Meaning |
|-------|-------|---------|
| Version | `5` | BCBP version 5 |
| Unique conditional size | `181` | Bytes following |
| Passenger description | `W` | Adult male |
| Source of check-in | ` ` | Web |
| Source of boarding pass | `6` | Online |
| Date of BP issuance | `086` | Julian day (Mar 27) |
| Document type | `B` | Boarding pass |
| Airline of BP issuer | `FR` | Ryanair |

### Julian Date Conversion

The BCBP uses Julian day-of-year (001-366). To convert:
- Day `087` in 2026 = **March 28, 2026**
- Day `086` = March 27, 2026

## Related Resources

- [IATA BCBP Implementation Guide (PDF)](https://www.iata.org/contentassets/1dccc9ed041b4f3bbdcf8ee8682e75c4/2021_03_02-bcbp-implementation-guide-version-7-.pdf)
- [BCBP Barcode Decoder (online tool)](https://orcascan.com/tools/bcbp-barcode-decoder)
- [Ryanair API Endpoints (GitHub Gist)](https://gist.github.com/vool/bbd64eeee313d27a82ab)

## License

MIT
