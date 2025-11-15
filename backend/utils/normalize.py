def clean_amount(value):
    if value is None:
        return None
    # Remove all common currency symbols and thousand separators
    cleaned = str(value).strip()
    
    # Remove 3-letter currency codes (USD, EUR, GBP, INR, etc.)
    import re
    cleaned = re.sub(r'^[A-Z]{3}\s*', '', cleaned)  # Remove leading currency codes
    cleaned = re.sub(r'\s*[A-Z]{3}$', '', cleaned)  # Remove trailing currency codes
    
    # Remove currency symbols
    for symbol in ["$", "₹", "€", "£", "¥", "₩", "₪", "₱", "₦", "₴", "₡", "₵", "₲", "₸", "₹", "₺", "₼", "₽", "₾", "₿"]:
        cleaned = cleaned.replace(symbol, "")
    
    # Remove thousand separators (commas, spaces, apostrophes)
    cleaned = cleaned.replace(",", "").replace(" ", "").replace("'", "").strip()
    return float(cleaned)


def normalize_transaction(data):
    normalized = {}

    # Vendor > Customer fallback (but retain vendor_name priority)
    vendor = data.get("vendor_name")
    customer = data.get("customer_name")
    normalized["vendor_name"] = vendor if vendor else customer

    normalized["invoice_number"] = data.get("invoice_number")
    normalized["date"] = data.get("date")
    normalized["category"] = data.get("category")
    normalized["address"] = data.get("address")

    normalized["total_amount"] = clean_amount(data.get("total_amount"))
    normalized["tax_amount"] = clean_amount(data.get("tax_amount"))
    normalized["payment_method"] = data.get("payment_method") or "Unknown"

    # Normalize items
    items_norm = []
    for item in data.get("items", []):
        unit_price = clean_amount(item.get("price"))
        quantity = int(item.get("quantity", 1))

        items_norm.append({
            "item_name": item.get("item_name"),
            "quantity": quantity,
            "unit_price": unit_price,
            "total_price": unit_price * quantity
        })

    normalized["items"] = items_norm

    return normalized
