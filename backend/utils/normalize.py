def clean_amount(value):
    if value is None or value == "":
        return None
    try:
        return float(
            str(value)
            .replace("$", "")
            .replace("₹", "")
            .replace(",", "")
            .strip()
        )
    except (ValueError, AttributeError):
        return None


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
        try:
            unit_price = clean_amount(item.get("price"))
            quantity = int(item.get("quantity", 1))
            
            # Skip items with invalid data
            if unit_price is None or quantity <= 0:
                continue

            items_norm.append({
                "item_name": item.get("item_name") or "Unknown Item",
                "quantity": quantity,
                "unit_price": unit_price,
                "total_price": unit_price * quantity
            })
        except (ValueError, TypeError, AttributeError) as e:
            # Skip items that can't be normalized
            print(f"⚠️  Skipping item due to error: {e}")
            continue

    normalized["items"] = items_norm

    return normalized
