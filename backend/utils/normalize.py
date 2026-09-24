"""Turn the vision model's loosely-typed JSON into a transaction row.

The model returns whatever it read off the invoice: "Rs 1,121.00", "₹1121",
"14/09/2026", "2 pcs", null items. Nothing here may raise on odd input; a
field that can't be parsed becomes None.
"""
import logging
import re
from datetime import date, datetime

from dateutil import parser as date_parser

logger = logging.getLogger(__name__)

_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?|-?\.\d+")
_MISSING = {"", "null", "none", "n/a", "na", "-", "unknown"}


def _text(value):
    """Strip a string field; treat "null"/"N/A" and non-strings like {} as missing."""
    if value is None or isinstance(value, (dict, list)):
        return None
    text = str(value).strip()
    return None if text.lower() in _MISSING else text


def clean_amount(value):
    """Parse an amount like "Rs 1,121.00", "₹1,12,100", "USD 12.5" or 12.5.

    Returns a float, or None when there is no number in it.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = _NUMBER.search(str(value))
    if not match:
        return None
    try:
        return float(match.group().replace(",", ""))
    except ValueError:
        return None


def parse_date(value):
    """Return the date as ISO YYYY-MM-DD, or None.

    Analytics compare `Transaction.date` as a string, so anything else
    ("14/09/2026", "Sep 14, 2026") would sort and filter wrongly. Ambiguous
    numeric dates are read day-first, as printed on Indian invoices.
    """
    text = _text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        pass
    try:
        parsed = date_parser.parse(text, dayfirst=True, default=datetime(1900, 1, 1))
    except (ValueError, OverflowError):
        logger.info("Could not parse invoice date %r", text)
        return None
    if parsed.year == 1900:  # no year on the invoice; don't invent one
        return None
    return parsed.date().isoformat()


def _quantity(value):
    """ "2", 2, "2 pcs", "1.0" -> int >= 1 (the column is an integer)."""
    amount = clean_amount(value)
    if amount is None or amount <= 0:
        return 1
    return max(1, round(amount))


def _items(raw):
    if not isinstance(raw, list):
        return []
    items = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = _text(item.get("item_name") or item.get("name") or item.get("description"))
        unit_price = clean_amount(item.get("price") if item.get("price") is not None else item.get("unit_price"))
        if not name and unit_price is None:
            continue
        quantity = _quantity(item.get("quantity"))
        items.append({
            "item_name": name or "Item",
            "quantity": quantity,
            "unit_price": unit_price,
            "total_price": round(unit_price * quantity, 2) if unit_price is not None else None,
        })
    return items


def normalize_transaction(data):
    if not isinstance(data, dict):
        data = {}
    normalized = {}

    # Vendor > Customer fallback (but retain vendor_name priority)
    normalized["vendor_name"] = _text(data.get("vendor_name")) or _text(data.get("customer_name"))

    normalized["invoice_number"] = _text(data.get("invoice_number"))
    normalized["date"] = parse_date(data.get("date"))
    normalized["category"] = _text(data.get("category")) or "Other"
    normalized["address"] = _text(data.get("address"))

    normalized["total_amount"] = clean_amount(data.get("total_amount"))
    normalized["tax_amount"] = clean_amount(data.get("tax_amount"))
    normalized["payment_method"] = _text(data.get("payment_method")) or "Unknown"

    normalized["items"] = _items(data.get("items"))

    return normalized
