import logging
from typing import Dict, List
from decimal import Decimal

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# EDIFACT Segment Identifiers
UNA = "UNA:+.? '"
ORDERS_MSG_TYPE = "ORDERS:D:96A:UN"
DATE_FORMAT = "102"

def validate_data(data: Dict[str, any]) -> None:
    """Validate required fields in ORDERS data."""
    required_fields = ["message_ref", "order_number", "order_date", "parties", "items"]
    
    for field in required_fields:
        if not data.get(field):
            logging.error("Missing required field: %s", field)
            raise ValueError(f"Missing required field: {field}")

    if not isinstance(data["items"], list) or not data["items"]:
        logging.error("ORDERS must contain at least one item.")
        raise ValueError("ORDERS must contain at least one item.")
    
    logging.info("Data validation passed.")

def format_party(party: Dict[str, str]) -> str:
    """Format party segment if valid."""
    if "qualifier" not in party or "id" not in party:
        logging.warning("Skipping invalid NAD entry: %s", party)
        return ""
    return f"NAD+{party['qualifier']}+{party['id']}::91'"

def format_item(index: int, item: Dict[str, str]) -> List[str]:
    """Format item segment if valid."""
    required_item_fields = ["product_code", "description", "quantity", "price"]
    if any(field not in item for field in required_item_fields):
        logging.warning("Skipping item due to missing fields: %s", item)
        return []

    quantity = int(item["quantity"])
    price = Decimal(item["price"])
    line_total = price * quantity

    return [
        f"LIN+{index}++{item['product_code']}:EN'",
        f"IMD+F++:::{item['description']}'",
        f"QTY+21:{quantity}:EA'",
        f"PRI+AAA:{price}:EA'"
    ], line_total

def generate_orders(data: Dict[str, any], filename: str = "orders.edi") -> str:
    """Generate an EDIFACT ORDERS message and save to a file."""
    try:
        validate_data(data)
    except ValueError as e:
        return ""

    logging.info("Generating ORDERS message...")

    edifact = [
        UNA,
        f"UNH+{data['message_ref']}+{ORDERS_MSG_TYPE}'",
        f"BGM+220+{data['order_number']}+9'",
        f"DTM+137:{data['order_date']}:{DATE_FORMAT}'"
    ]

    if "delivery_date" in data:
        edifact.append(f"DTM+2:{data['delivery_date']}:{DATE_FORMAT}'")

    # Add party details
    edifact.extend(filter(None, (format_party(p) for p in data["parties"])))

    total_amount = Decimal("0.00")

    # Add items
    for index, item in enumerate(data["items"], start=1):
        formatted_item, line_total = format_item(index, item)
        if formatted_item:
            edifact.extend(formatted_item)
            total_amount += line_total

    # Add monetary total
    edifact.append(f"MOA+79:{total_amount:.2f}:'")

    if "special_instructions" in data:
        edifact.append(f"FTX+AAI+++{data['special_instructions']}'")

    # Finalize message
    segment_count = len(edifact) - 1
    edifact.append(f"UNT+{segment_count}+{data['message_ref']}'")

    edifact_message = "\n".join(edifact)
    
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(edifact_message)
        logging.info("ORDERS message generated and saved to %s", filename)
    except IOError as e:
        logging.error("Failed to write ORDERS message to file: %s", e)
        return ""

    return edifact_message

# Example data
orders_data = {
    "message_ref": "456789",
    "order_number": "ORD2025001",
    "order_date": "20250322",
    "delivery_date": "20250329",
    "parties": [
        {"qualifier": "BY", "id": "123456789"},
        {"qualifier": "SU", "id": "987654321"},
        {"qualifier": "DP", "id": "555555555"}  # Delivery Party
    ],
    "items": [
        {"product_code": "ABC123", "description": "Product A", "quantity": "10", "price": "25.50"},
        {"product_code": "XYZ456", "description": "Product B", "quantity": "5", "price": "40.00"}
    ],
    "special_instructions": "Deliver between 9 AM - 5 PM"
}

# Generate and save ORDERS
orders_message = generate_orders(orders_data)
if orders_message:
    print("\nGenerated ORDERS Message:\n")
    print(orders_message)
