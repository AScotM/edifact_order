import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Literal, Optional, Tuple, TypedDict  # Added Tuple here

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Constants
UNA_SEGMENT = "UNA:+.? '"
ORDERS_MSG_TYPE = "ORDERS:D:96A:UN"
DATE_FORMAT = "102"

# TypedDict for type-safe data validation
class OrderItem(TypedDict):
    product_code: str
    description: str
    quantity: str
    price: str

class OrderParty(TypedDict):
    qualifier: str
    id: str
    name: Optional[str]
    address: Optional[str]

class OrderData(TypedDict):
    message_ref: str
    order_number: str
    order_date: str
    parties: List[OrderParty]
    items: List[OrderItem]
    delivery_date: Optional[str]
    currency: Optional[str]
    delivery_location: Optional[str]
    payment_terms: Optional[str]
    tax_rate: Optional[str]
    special_instructions: Optional[str]

@dataclass
class EdifactConfig:
    """Configuration for EDIFACT generation."""
    una_segment: str = UNA_SEGMENT
    message_type: str = ORDERS_MSG_TYPE
    date_format: str = DATE_FORMAT

class EdifactGenerationError(Exception):
    """Custom exception for EDIFACT generation failures."""
    pass

def validate_order_data(data: Dict) -> OrderData:
    """Validate and normalize input data."""
    required_fields = ["message_ref", "order_number", "order_date", "parties", "items"]
    if not all(field in data for field in required_fields):
        raise EdifactGenerationError("Missing required fields.")

    if not isinstance(data["items"], list) or not data["items"]:
        raise EdifactGenerationError("At least one item is required.")

    return data  # type: ignore (TypedDict ensures type safety)

def format_party(party: OrderParty) -> List[str]:
    """Format NAD/CTA/COM segments for a party."""
    segments = []
    qualifier, party_id = party["qualifier"], party["id"]
    segments.append(f"NAD+{qualifier}+{party_id}::91'")

    if name := party.get("name"):
        segments.append(f"CTA+IC+{name}'")

    if address := party.get("address"):
        segments.append(f"COM+{address}:AD'")

    return segments

def format_order_item(index: int, item: OrderItem) -> Tuple[List[str], Decimal]:
    """Format LIN/IMD/QTY/PRI segments for an item."""
    quantity = int(item["quantity"])
    price = Decimal(item["price"])
    line_total = quantity * price

    segments = [
        f"LIN+{index}++{item['product_code']}:EN'",
        f"IMD+F++:::{item['description']}'",
        f"QTY+21:{quantity}:EA'",
        f"PRI+AAA:{price:.2f}:EA'",
    ]

    return segments, line_total

def generate_edifact_orders(
    data: Dict,
    config: EdifactConfig = EdifactConfig(),
    output_file: Optional[str] = None,
) -> str:
    """Generate EDIFACT ORDERS message."""
    try:
        validated_data = validate_order_data(data)
    except EdifactGenerationError as e:
        logger.error(f"Validation failed: {e}")
        raise

    edifact_segments = [config.una_segment]
    edifact_segments.append(f"UNH+{validated_data['message_ref']}+{config.message_type}'")
    edifact_segments.append(f"BGM+220+{validated_data['order_number']}+9'")
    edifact_segments.append(f"DTM+137:{validated_data['order_date']}:{config.date_format}'")

    # Optional segments
    if delivery_date := validated_data.get("delivery_date"):
        edifact_segments.append(f"DTM+2:{delivery_date}:{config.date_format}'")

    if currency := validated_data.get("currency"):
        edifact_segments.append(f"CUX+2:{currency}:9'")

    # Process parties
    for party in validated_data["parties"]:
        edifact_segments.extend(format_party(party))

    # Process items
    total_amount = Decimal("0.00")
    for idx, item in enumerate(validated_data["items"], 1):
        item_segments, line_total = format_order_item(idx, item)
        edifact_segments.extend(item_segments)
        total_amount += line_total

    # Calculate taxes and totals
    if tax_rate := validated_data.get("tax_rate"):
        tax_amount = (total_amount * Decimal(tax_rate) / 100).quantize(Decimal("0.01"))
        edifact_segments.extend([
            f"TAX+7+VAT+++:::{tax_rate}%'",
            f"MOA+124:{tax_amount:.2f}:'",
        ])
        total_amount += tax_amount

    edifact_segments.append(f"MOA+79:{total_amount:.2f}:'")

    # Finalize message
    segment_count = len(edifact_segments) - 1  # Exclude UNA
    edifact_segments.append(f"UNT+{segment_count}+{validated_data['message_ref']}'")

    edifact_message = "\n".join(edifact_segments)

    if output_file:
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(edifact_message)
            logger.info(f"EDIFACT message written to {output_file}")
        except IOError as e:
            logger.error(f"Failed to write file: {e}")
            raise EdifactGenerationError("File write failed.") from e

    return edifact_message

# Example Usage
if __name__ == "__main__":
    sample_order: OrderData = {
        "message_ref": "ORD0001",
        "order_number": "2025-0509-A",
        "order_date": "20250509",
        "parties": [
            {"qualifier": "BY", "id": "1234567890123", "name": "Buyer Corp"},
            {"qualifier": "SU", "id": "3210987654321", "address": "Industrial Park"},
        ],
        "items": [
            {"product_code": "ITEM001", "description": "Widget A", "quantity": "10", "price": "12.50"},
        ],
    }

    try:
        message = generate_edifact_orders(sample_order, output_file="orders.edi")
        print("\nGenerated EDIFACT ORDERS:\n", message)
    except EdifactGenerationError:
        print("Failed to generate EDIFACT message.")
