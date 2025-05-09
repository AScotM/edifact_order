import logging
from typing import Dict, List, Tuple, Union
from decimal import Decimal

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Constants
UNA = "UNA:+.? '"
ORDERS_MSG_TYPE = "ORDERS:D:96A:UN"
DATE_FORMAT = "102"

def validate_data(data: Dict[str, any]) -> None:
    """Validate required fields in ORDERS data."""
    required_fields = ["message_ref", "order_number", "order_date", "parties", "items"]
    for field in required_fields:
        if not data.get(field):
            raise ValueError(f"Missing required field: {field}")
    if not isinstance(data["items"], list) or not data["items"]:
        raise ValueError("ORDERS must contain at least one item.")

def format_party(party: Dict[str, str]) -> List[str]:
    """Format party segments including optional contact and communication info."""
    lines = []
    if "qualifier" in party and "id" in party:
        lines.append(f"NAD+{party['qualifier']}+{party['id']}::91'")
        if "name" in party:
            lines.append(f"CTA+IC+{party['name']}'")
        if "address" in party:
            lines.append(f"COM+{party['address']}:AD'")
    return lines

def format_item(index: int, item: Dict[str, str]) -> Tuple[List[str], Decimal]:
    """Format item segment and calculate line total."""
    required = ["product_code", "description", "quantity", "price"]
    if any(k not in item for k in required):
        logging.warning("Skipping invalid item: %s", item)
        return [], Decimal("0.00")

    quantity = int(item["quantity"])
    price = Decimal(item["price"])
    total = quantity * price

    lines = [
        f"LIN+{index}++{item['product_code']}:EN'",
        f"IMD+F++:::{item['description']}'",
        f"QTY+21:{quantity}:EA'",
        f"PRI+AAA:{price:.2f}:EA'"
    ]

    return lines, total

def generate_orders(data: Dict[str, any], filename: str = "orders.edi", write_to_file: bool = True) -> str:
    """Generate EDIFACT ORDERS message (D.96A) and optionally write to file."""
    try:
        validate_data(data)
    except ValueError as e:
        logging.error(str(e))
        return ""

    logging.info("Generating ORDERS message...")

    edifact = [UNA]
    edifact.append(f"UNH+{data['message_ref']}+{ORDERS_MSG_TYPE}'")
    edifact.append(f"BGM+220+{data['order_number']}+9'")
    edifact.append(f"DTM+137:{data['order_date']}:{DATE_FORMAT}'")

    if "delivery_date" in data:
        edifact.append(f"DTM+2:{data['delivery_date']}:{DATE_FORMAT}'")

    if "currency" in data:
        edifact.append(f"CUX+2:{data['currency']}:9'")

    # Parties
    for party in data["parties"]:
        edifact.extend(format_party(party))

    # Delivery location
    if "delivery_location" in data:
        edifact.append(f"LOC+7+{data['delivery_location']}::91'")  # 7 = Place of delivery

    # Payment terms
    if "payment_terms" in data:
        edifact.append(f"PAT+1'")
        edifact.append(f"DTM+13:{data['payment_terms']}:{DATE_FORMAT}'")  # 13 = Terms net due date

    # Item lines
    total_amount = Decimal("0.00")
    for i, item in enumerate(data["items"], 1):
        lines, line_total = format_item(i, item)
        if lines:
            edifact.extend(lines)
            total_amount += line_total

    # Add TAX (example VAT at 20%)
    if "tax_rate" in data:
        tax_rate = Decimal(data["tax_rate"])
        tax_amount = (total_amount * tax_rate / 100).quantize(Decimal("0.01"))
        edifact.append(f"TAX+7+VAT+++::: {tax_rate:.2f}'")
        edifact.append(f"MOA+124:{tax_amount:.2f}:'")  # 124 = Tax amount
        grand_total = total_amount + tax_amount
    else:
        grand_total = total_amount

    # Total monetary amount
    edifact.append(f"MOA+79:{grand_total:.2f}:'")

    # Free-text instructions
    if "special_instructions" in data:
        edifact.append(f"FTX+AAI+++{data['special_instructions']}'")

    # Trailer
    segment_count = len(edifact) - 1
    edifact.append(f"UNT+{segment_count}+{data['message_ref']}'")

    edifact_message = "\n".join(edifact)

    if write_to_file:
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(edifact_message)
            logging.info("Message written to %s", filename)
        except IOError as e:
            logging.error("File write failed: %s", e)

    return edifact_message

# Example usage
if __name__ == "__main__":
    sample_data = {
        "message_ref": "ORD0001",
        "order_number": "2025-0509-A",
        "order_date": "20250509",
        "delivery_date": "20250512",
        "currency": "EUR",
        "delivery_location": "9876543210",
        "payment_terms": "20250608",
        "tax_rate": "20.0",
        "parties": [
            {"qualifier": "BY", "id": "1234567890123", "name": "Buyer Corp", "address": "Main St 1"},
            {"qualifier": "SU", "id": "3210987654321", "name": "Supplier Ltd", "address": "Industrial Park"},
            {"qualifier": "DP", "id": "5678901234567", "name": "Delivery Place", "address": "Warehouse 4"}
        ],
        "items": [
            {"product_code": "ITEM001", "description": "Widget A", "quantity": "10", "price": "12.50"},
            {"product_code": "ITEM002", "description": "Gadget B", "quantity": "5", "price": "20.00"}
        ],
        "special_instructions": "Deliver between 9 AM - 5 PM"
    }

    message = generate_orders(sample_data)
    if message:
        print("\nGenerated EDIFACT ORDERS Message:\n")
        print(message)
