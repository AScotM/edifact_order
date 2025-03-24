import datetime
import logging
from typing import Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def validate_data(data: Dict) -> None:
    """Validate required fields in ORDERS data."""
    required_fields = ["message_ref", "order_number", "order_date", "parties", "items"]
    for field in required_fields:
        if field not in data or not data[field]:
            raise ValueError(f"Missing required field: {field}")
    if not isinstance(data["items"], list) or len(data["items"]) == 0:
        raise ValueError("ORDERS must contain at least one item.")
    logging.info("Data validation passed.")

def generate_orders(data: Dict, filename: str = "orders.edi") -> str:
    """Generate an EDIFACT ORDERS message and save to a file."""
    try:
        validate_data(data)
    except ValueError as e:
        logging.error(e)
        return ""

    logging.info("Generating ORDERS message...")

    edifact = [
        "UNA:+.? '",  # Service string advice
        f"UNH+{data['message_ref']}+ORDERS:D:96A:UN'"
    ]

    edifact.append(f"BGM+220+{data['order_number']}+9'")  # 220 = Order
    edifact.append(f"DTM+137:{data['order_date']}:102'")

    if "delivery_date" in data:
        edifact.append(f"DTM+2:{data['delivery_date']}:102'")

    for party in data['parties']:
        if "qualifier" not in party or "id" not in party:
            logging.warning("Skipping invalid NAD entry: %s", party)
            continue
        edifact.append(f"NAD+{party['qualifier']}+{party['id']}::91'")

    total_amount = 0.0

    for index, item in enumerate(data['items'], start=1):
        if "product_code" not in item or "description" not in item or "quantity" not in item or "price" not in item:
            logging.warning("Skipping item due to missing fields: %s", item)
            continue
        edifact.append(f"LIN+{index}++{item['product_code']}:EN'")
        edifact.append(f"IMD+F++:::{item['description']}'")
        edifact.append(f"QTY+21:{item['quantity']}:EA'")
        edifact.append(f"PRI+AAA:{item['price']}:EA'")
        line_total = float(item['price']) * int(item['quantity'])
        total_amount += line_total

    edifact.append(f"MOA+79:{total_amount:.2f}:'")  # Total order amount

    if "special_instructions" in data:
        edifact.append(f"FTX+AAI+++{data['special_instructions']}'")

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
