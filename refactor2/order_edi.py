import logging
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from typing import Dict, List, Optional, TypedDict

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Constants
UNA_SEGMENT = "UNA:+.? '"
ORDERS_MSG_TYPE = "ORDERS"
DATE_FORMAT = "102"
EDIFACT_SPECIAL_CHARS = ["?", "'", "+", ":", "*"]  # Fixed typo in variable name

class OrderItem(TypedDict):
    product_code: str
    description: str
    quantity: str
    price: Decimal

class OrderParty(TypedDict):
    qualifier: str
    id: str
    name: Optional[str]
    address: Optional[str]
    contact: Optional[str]

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
    tax_rate: Optional[Decimal]
    special_instructions: Optional[str]
    incoterms: Optional[str]

@dataclass
class EdifactConfig:
    """Enhanced configuration for EDIFACT generation"""
    una_segment: str = UNA_SEGMENT
    message_type: str = ORDERS_MSG_TYPE
    date_format: str = DATE_FORMAT
    version: str = "D"
    release: str = "96A"
    controlling_agency: str = "UN"
    decimal_rounding: str = "0.01"

class SegmentGenerator:
    """Helper class for EDIFACT segment generation"""
    
    @staticmethod
    def escape_edifact(value: str) -> str:
        """Escape special EDIFACT characters"""
        if not value:
            return value
        for char in EDIFACT_SPECIAL_CHARS:
            value = value.replace(char, f"?{char}")
        return value
    
    @classmethod
    def una(cls, config: EdifactConfig) -> str:
        return config.una_segment
    
    @classmethod
    def unh(cls, message_ref: str, config: EdifactConfig) -> str:
        return f"UNH+{message_ref}+{config.message_type}:{config.version}:{config.release}:{config.controlling_agency}'"
    
    @classmethod
    def bgm(cls, order_number: str) -> str:
        return f"BGM+220+{order_number}+9'"
    
    @classmethod
    def dtm(cls, qualifier: str, date: str, date_format: str) -> str:
        return f"DTM+{qualifier}:{date}:{date_format}'"
    
    @classmethod
    def nad(cls, qualifier: str, party_id: str, name: Optional[str] = None) -> str:
        segment = f"NAD+{qualifier}+{party_id}::91'"
        if name:
            segment += f"\nCTA+IC+{cls.escape_edifact(name)}'"
        return segment
    
    @classmethod
    def com(cls, contact: str, contact_type: str = "TE") -> str:
        return f"COM+{cls.escape_edifact(contact)}:{contact_type}'"
    
    @classmethod
    def lin(cls, line_num: int, product_code: str) -> str:
        return f"LIN+{line_num}++{product_code}:EN'"
    
    @classmethod
    def imd(cls, description: str) -> str:
        return f"IMD+F++:::{cls.escape_edifact(description)}'"
    
    @classmethod
    def qty(cls, quantity: int, unit: str = "EA") -> str:
        return f"QTY+21:{quantity}:{unit}'"
    
    @classmethod
    def pri(cls, price: Decimal, config: EdifactConfig) -> str:
        return f"PRI+AAA:{price.quantize(Decimal(config.decimal_rounding), rounding=ROUND_HALF_UP)}:EA'"
    
    @classmethod
    def moa(cls, qualifier: str, amount: Decimal, config: EdifactConfig) -> str:
        return f"MOA+{qualifier}:{amount.quantize(Decimal(config.decimal_rounding), rounding=ROUND_HALF_UP)}'"
    
    @classmethod
    def tax(cls, rate: Decimal, tax_type: str = "VAT") -> str:
        return f"TAX+7+{tax_type}+++:::{rate}%'"
    
    @classmethod
    def loc(cls, qualifier: str, location: str) -> str:
        return f"LOC+{qualifier}+{location}:92'"
    
    @classmethod
    def pai(cls, terms: str) -> str:
        return f"PAI+{terms}:3'"
    
    @classmethod
    def unt(cls, segment_count: int, message_ref: str) -> str:
        return f"UNT+{segment_count}+{message_ref}'"

class EdifactGenerationError(Exception):
    """Enhanced exception with error codes"""
    def __init__(self, message: str, code: str = "EDIFACT_001"):
        self.code = code
        super().__init__(f"{code}: {message}")

def validate_date(date_str: str, date_format: str) -> bool:
    """Validate date format according to EDIFACT standards"""
    try:
        if date_format == "102":  # CCYYMMDD
            datetime.strptime(date_str, "%Y%m%d")
        elif date_format == "203":  # CCYYMMDDHHMM
            datetime.strptime(date_str, "%Y%m%d%H%M")
        return True
    except ValueError:
        return False

def validate_order_data(data: Dict, config: EdifactConfig) -> OrderData:
    """Enhanced validation with date checking"""
    required_fields = ["message_ref", "order_number", "order_date", "parties", "items"]
    if not all(field in data for field in required_fields):
        raise EdifactGenerationError("Missing required fields", "VALID_001")

    if not isinstance(data["items"], list) or not data["items"]:
        raise EdifactGenerationError("At least one item is required", "VALID_002")

    if not validate_date(data["order_date"], config.date_format):
        raise EdifactGenerationError(f"Invalid order_date format for {config.date_format}", "VALID_003")

    if "delivery_date" in data and data["delivery_date"] and not validate_date(data["delivery_date"], config.date_format):
        raise EdifactGenerationError(f"Invalid delivery_date format for {config.date_format}", "VALID_004")

    # Convert string numbers to Decimal
    try:
        converted_items = []
        for item in data["items"]:
            converted_item = {
                "product_code": item["product_code"],
                "description": item["description"],
                "quantity": str(int(item["quantity"])),
                "price": Decimal(str(item["price"]))
            }
            converted_items.append(converted_item)
        data["items"] = converted_items
        
        if "tax_rate" in data and data["tax_rate"]:
            data["tax_rate"] = Decimal(str(data["tax_rate"]))
    except (ValueError, TypeError) as e:
        raise EdifactGenerationError(f"Invalid numeric format: {str(e)}", "VALID_005")

    return data  # type: ignore

def generate_edifact_orders(
    data: Dict,
    config: EdifactConfig = EdifactConfig(),
    output_file: Optional[str] = None,
) -> str:
    """Enhanced EDIFACT ORDERS generator with all improvements"""
    try:
        validated_data = validate_order_data(data, config)
    except EdifactGenerationError as e:
        logger.error(f"Validation failed: {e}")
        raise

    segments = [
        SegmentGenerator.una(config),
        SegmentGenerator.unh(validated_data["message_ref"], config),
        SegmentGenerator.bgm(validated_data["order_number"]),
        SegmentGenerator.dtm("137", validated_data["order_date"], config.date_format)
    ]

    # Optional date segments
    if validated_data.get("delivery_date"):
        segments.append(SegmentGenerator.dtm("2", validated_data["delivery_date"], config.date_format))

    # Currency segment
    if validated_data.get("currency"):
        segments.append(f"CUX+2:{validated_data['currency']}:9'")

    # Process parties
    for party in validated_data["parties"]:
        segments.append(SegmentGenerator.nad(
            party["qualifier"],
            party["id"],
            party.get("name")
        ))
        if party.get("address"):
            segments.append(SegmentGenerator.com(party["address"], "AD"))
        if party.get("contact"):
            segments.append(SegmentGenerator.com(party["contact"], "TE"))

    # Process items
    total_amount = Decimal("0.00")
    for idx, item in enumerate(validated_data["items"], 1):
        quantity = int(item["quantity"])
        price = item["price"]
        line_total = price * quantity
        
        segments.extend([
            SegmentGenerator.lin(idx, item["product_code"]),
            SegmentGenerator.imd(item["description"]),
            SegmentGenerator.qty(quantity),
            SegmentGenerator.pri(price, config)
        ])
        total_amount += line_total

    # Tax calculation
    if validated_data.get("tax_rate"):
        tax_rate = validated_data["tax_rate"]
        tax_amount = (total_amount * tax_rate / 100).quantize(
            Decimal(config.decimal_rounding), rounding=ROUND_HALF_UP
        )
        segments.extend([
            SegmentGenerator.tax(tax_rate),
            SegmentGenerator.moa("124", tax_amount, config)
        ])
        total_amount += tax_amount

    # Delivery location
    if validated_data.get("delivery_location"):
        segments.append(SegmentGenerator.loc("11", validated_data["delivery_location"]))

    # Payment terms
    if validated_data.get("payment_terms"):
        segments.append(SegmentGenerator.pai(validated_data["payment_terms"]))

    # Final totals
    segments.append(SegmentGenerator.moa("79", total_amount, config))

    # Message trailer (correct segment count includes UNT)
    segments.append(SegmentGenerator.unt(len(segments), validated_data["message_ref"]))

    edifact_message = "\n".join(segments)

    if output_file:
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(edifact_message)
            logger.info(f"EDIFACT message written to {output_file}")
        except IOError as e:
            logger.error(f"Failed to write file: {e}")
            raise EdifactGenerationError("File write failed", "IO_001") from e

    return edifact_message

# Example Usage
if __name__ == "__main__":
    sample_order = {
        "message_ref": "ORD0001",
        "order_number": "2025-0509-A",
        "order_date": "20250509",
        "parties": [
            {
                "qualifier": "BY", 
                "id": "1234567890123", 
                "name": "Buyer Corp",
                "contact": "+123456789"
            },
            {
                "qualifier": "SU", 
                "id": "3210987654321", 
                "address": "Industrial?Park",
                "contact": "supplier@example.com"
            },
        ],
        "items": [
            {
                "product_code": "ITEM001",
                "description": "Widget A (Special)",
                "quantity": "10",
                "price": Decimal("12.50")
            },
        ],
        "delivery_date": "20250515",
        "currency": "USD",
        "delivery_location": "WAREHOUSE1",
        "payment_terms": "NET30",
        "tax_rate": Decimal("7.5"),
        "incoterms": "FOB"
    }

    enhanced_config = EdifactConfig(
        version="4",
        release="22A",
        controlling_agency="ISO"
    )

    try:
        message = generate_edifact_orders(
            sample_order,
            config=enhanced_config,
            output_file="orders.edi"
        )
        print("\nGenerated EDIFACT ORDERS:\n", message)
    except EdifactGenerationError as e:
        print(f"Generation failed: {e.code} - {str(e)}")
