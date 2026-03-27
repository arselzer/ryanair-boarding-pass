# Ryanair Boarding Pass API

Documentation and tools for Ryanair's boarding pass generation system, discovered through browser DevTools network analysis of the ryanair.com web check-in flow.

## API Endpoints

### 1. Get Booking (GraphQL)

```
POST https://www.ryanair.com/api/bookingfa/en-gb/graphql
```

**Authentication:** Bearer token (JWT) in `Authorization` header

**Key Headers:**
| Header | Value |
|--------|-------|
| `Authorization` | `Bearer <jwt-token>` |
| `Content-Type` | `application/json` |
| `client` | `desktop` |
| `client-version` | `4.173.0` |

**Operation:** `GetBooking`

**Variables:**
```json
{
  "sessionToken": "<session-token>",
  "invalidateCache": false
}
```

**Response includes:**
- Passenger details, journey info, segments
- Check-in status (`segCheckin.status`: `"reprint"` = already checked in)
- `mobilebp: true` = mobile boarding pass enabled
- Seat assignments, baggage, extras

### 2. Get Boarding Pass (REST)

```
GET https://www.ryanair.com/api/booking/boarding-pass/v6/en-gb/boardingPass
```

**Authentication:** Session-based (cookies + session token)

**Key Headers:**
| Header | Value |
|--------|-------|
| `x-session-token` | `<session-token>` |
| `client` | `desktop` |
| `client-version` | `1.13.0` |

**Response:**
```json
{
  "pnr": "ABC123",
  "boardingPasses": [
    {
      "paxType": "ADT",
      "journeyNum": 0,
      "paxNum": 0,
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
        "date": "2026-03-28T10:50:00+01:00"
      },
      "arrival": {
        "code": "LHR",
        "name": "London Heathrow",
        "date": "2026-03-28T12:30:00+00:00"
      },
      "seat": {
        "designator": "15A",
        "location": "Window",
        "door": 0
      },
      "mobileBp": true,
      "sequence": 42,
      "gateCloseTime": 30,
      "boardingTime": "2026-03-28T10:20:00.000",
      "carrierCode": "FR",
      "operatedBy": "Lauda Europe",
      "blockBarCode": {
        "barCodeBlocked": false
      }
    }
  ]
}
```

## IATA BCBP Barcode Format

The `barcode.payload` field contains a standard **IATA BCBP** (Bar Coded Boarding Pass) string per [Resolution 792](https://www.iata.org/en/programs/passenger/common-use/).

### Mandatory Fields (first 58 characters)

| Position | Length | Field | Example |
|----------|--------|-------|--------|
| 0 | 1 | Format code | `M` |
| 1 | 1 | Number of legs | `1` |
| 2-21 | 20 | Passenger name (LAST/FIRST) | `DOE/JOHN` |
| 22 | 1 | Electronic ticket indicator | `E` or space |
| 23-29 | 7 | PNR code | `ABC123` |
| 30-32 | 3 | From airport (IATA) | `DUB` |
| 33-35 | 3 | To airport (IATA) | `LHR` |
| 36-38 | 3 | Operating carrier | `FR` |
| 39-43 | 5 | Flight number | `1234` |
| 44-46 | 3 | Julian date of flight | `087` (= Mar 28) |
| 47 | 1 | Compartment code | `Y` (Economy) |
| 48-51 | 4 | Seat number | `015A` |
| 52-56 | 5 | Check-in sequence | `00042` |
| 57 | 1 | Passenger status | `1` |

### Conditional Section (after `>`)

| Offset | Length | Field |
|--------|--------|-------|
| 0 | 1 | Version number (`5`) |
| 1-3 | 3 | Size of unique conditional |
| 4 | 1 | Passenger description (`W` = adult male) |
| 5 | 1 | Source of check-in |
| 6 | 1 | Source of boarding pass issuance |
| 7-9 | 3 | Date of boarding pass issuance (Julian) |
| 10 | 1 | Document type (`B` = boarding pass) |
| 11-13 | 3 | Airline designator of boarding pass issuer |

## Authentication Flow

1. **Login** to ryanair.com (establishes session cookies)
2. **Retrieve booking** via the trip page (gets `sessionToken` and JWT)
3. **GraphQL `GetBooking`** query confirms check-in status and `mobilebp: true`
4. **REST boarding pass endpoint** returns the BCBP barcode payload
5. **App renders** the payload as a QR/Aztec code

The barcode is **generated server-side** and returned as a pre-built IATA BCBP string.

## Available GraphQL Operations

Discovered from the Ryanair web app JavaScript bundles:

### Queries
- `GetBooking` - Full booking details
- `GetPassengers` / `GetPassengersQuery` - Passenger information
- `GetSeatsQuery` - Seat map/availability
- `GetBasket` - Shopping basket
- `GetTotal` - Price totals
- `Products` - Available products/extras
- `FligthExtrasQuery` - Flight extras

### Mutations
- `CreateBasket` / `CreateBasketForActiveTrip` - Initialize basket
- `CreateBooking` / `CommitBooking` - Create/finalize booking
- `AssignSeat` - Seat assignment
- `AddBag` - Add baggage
- `AddPriorityBoarding` - Add priority boarding
- `AddFastTrack` - Add fast track
- `AddCarRental` / `AddCar` - Add car rental
- `AddExpressBagDropOff` - Add express bag drop
- `AddVoucher` / `ApplyVoucher` / `CeaseVoucher` - Voucher management
- `AddWhatsappNotifications` - WhatsApp notifications
- `AddUnpaidQuote` - Add unpaid quote
- `RemoveComponents` / `RemoveFlights` - Remove items
- `SetCarbonDonation` / `SetIspccDonation` - Donations
- `SetSmsItinerary` - SMS itinerary

**Note:** GraphQL introspection is disabled (`"Introspection queries are disabled"`).

## Web App Architecture

Ryanair's web app is an Angular application with lazy-loaded micro-frontends:

| App ID | Route | Asset Prefix |
|--------|-------|--------------|
| `CHECKIN` | `/trip/flights/checkin/` | `checkin_dist/` |
| `CHECKIN_PAXS` | `/trip/flights/checkin/passengers` | `checkin_dist/` |
| `CHECKIN_SEATS` | `/trip/flights/checkin/seats` | `checkin_dist/` |
| `CHECKIN_BAGS` | `/trip/flights/checkin/bags` | `checkin_dist/` |
| `CHECKIN_EXTRAS` | `/trip/flights/checkin/extras` | `checkin_dist/` |
| `BOARDING_PASS` | `/trip/flights/boarding-pass` | `boarding-pass_dist/` |
| `PAYMENT` | `/trip/flights/checkin/payment` | `payment_dist/` |

## Tools

### decode_bcbp.py

Decode any IATA BCBP barcode string:

```bash
python decode_bcbp.py "M1DOE/JOHN            ABC123 DUBLHRFR 1234 087Y015A0042 100>5181W 6086BFR ..."
```

### generate_qr.py

Generate a QR code image from a BCBP payload:

```bash
pip install qrcode[pil]
python generate_qr.py "<bcbp-payload>" output.png
```

### fetch_boarding_pass.py

Fetch your boarding pass directly from the API:

```bash
pip install requests qrcode[pil]
python fetch_boarding_pass.py --session-token <token> --qr
```

To get the session token:
1. Log in to ryanair.com and navigate to your trip
2. Open DevTools (F12) > Network tab > filter by Fetch/XHR
3. Look for requests to `/api/booking/` and copy the `x-session-token` header value

## How This Was Discovered

All information was gathered using standard browser DevTools:

1. **Network tab** monitoring during the check-in and boarding pass flow
2. **JavaScript bundle analysis** to find GraphQL operation names:
   ```javascript
   const scripts = performance.getEntriesByType('resource').filter(r => r.name.includes('.js'));
   Promise.all(scripts.map(s => fetch(s.name).then(r => r.text()))).then(texts => {
     const ops = new Set();
     texts.join('\n').replace(/query\s+(\w+)|mutation\s+(\w+)/g, (_, q, m) => ops.add(q || m));
     console.log([...ops].sort().join('\n'));
   })
   ```
3. **Console fetch interception** to log API calls in real-time

No APK decompilation, SSL pinning bypass, or unauthorized access was used.

## Important Notes

- **Digital boarding passes only**: Since November 2025, Ryanair only accepts digital boarding passes via their app (or Apple/Google Wallet). Printed passes are no longer accepted.
- **Session tokens expire quickly** (~25 minutes of inactivity)
- **SSL certificate pinning** is used in the mobile app, making traffic interception difficult. The web flow has no such restriction.
- All example data in this repository is fictional.

## License

MIT
