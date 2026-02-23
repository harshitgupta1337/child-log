import re
import logging
from datetime import datetime
from typing import List, Dict, Optional
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


# ---------------------------------
# Fuzzy Matching Utilities
# ---------------------------------

FUZZY_THRESHOLD = 80  # similarity score


def fuzzy_contains(text: str, keywords: List[str]) -> bool:
    """
    Returns True if any keyword fuzzy-matches
    any token in text above threshold.
    """
    tokens = re.findall(r'\w+', text.lower())

    for token in tokens:
        for keyword in keywords:
            score = fuzz.ratio(token, keyword)
            if score >= FUZZY_THRESHOLD:
                logger.debug("fuzzy_contains: token=%r matched keyword=%r (score=%d)", token, keyword, score)
                return True
    return False


def fuzzy_extract_keyword(text: str, keywords: List[str]) -> Optional[str]:
    tokens = re.findall(r'\w+', text.lower())

    best_score = 0
    best_match = None

    for token in tokens:
        for keyword in keywords:
            score = fuzz.ratio(token, keyword)
            if score > best_score:
                best_score = score
                best_match = keyword

    if best_score >= FUZZY_THRESHOLD:
        logger.debug("fuzzy_extract_keyword: best_match=%r (score=%d)", best_match, best_score)
        return best_match

    logger.debug("fuzzy_extract_keyword: no match above threshold (best=%r, score=%d)", best_match, best_score)
    return None


# ---------------------------------
# Duration / Amount / Time Parsers
# ---------------------------------

DURATION_REGEX = re.compile(
    r'(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?',
    re.IGNORECASE
)

CLOCK_REGEX = re.compile(
    r'(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?',
    re.IGNORECASE
)

AMOUNT_REGEX = re.compile(
    r'(\d+(?:\.\d+)?)\s*(ml|oz)',
    re.IGNORECASE
)


def parse_duration(text: str) -> Optional[int]:
    text = text.lower()
    text = text.replace("hours", "h").replace("hour", "h")
    text = text.replace("minutes", "m").replace("minute", "m")
    text = text.replace("mins", "m")
    text = text.replace("minuts", "m")  # common typo

    match = DURATION_REGEX.search(text)
    if not match:
        return None

    hours = match.group(1)
    minutes = match.group(2)

    total = 0
    if hours:
        total += int(hours) * 60
    if minutes:
        total += int(minutes)

    if total == 0:
        single = re.search(r'\d+', text)
        if single:
            logger.debug("parse_duration: fallback single number=%s", single.group())
            return int(single.group())

    logger.debug("parse_duration: total=%d minutes", total)
    return total if total > 0 else None


def parse_amount(text: str) -> Optional[float]:
    match = AMOUNT_REGEX.search(text)
    if not match:
        return None

    value = float(match.group(1))
    unit = match.group(2).lower()

    if unit == "oz":
        converted = round(value * 29.5735, 2)
        logger.debug("parse_amount: %.2f oz -> %.2f ml", value, converted)
        return converted
    logger.debug("parse_amount: %.2f ml", value)
    return value


def parse_time_line(text: str, base_date: datetime) -> Optional[datetime]:
    lower = text.lower().replace("time", "").strip()

    match = CLOCK_REGEX.search(lower)
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2)) if match.group(2) else 0
    meridian = match.group(3)

    if meridian:
        meridian = meridian.replace(".", "")
        if meridian == "pm" and hour != 12:
            hour += 12
        if meridian == "am" and hour == 12:
            hour = 0

    try:
        result = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        logger.debug("parse_time_line: parsed %r -> %s", text, result)
        return result
    except:
        logger.debug("parse_time_line: failed to build datetime from hour=%d minute=%d", hour, minute)
        return None

BREAST_SIDES = [LEFT, RIGHT, EACH, BOTH] = ["left", "right", "each", "both"]

DIAPER_EVENT_TYPES = [PEE, POO, BOTH] = ["pee", "poo", "both"]
DIAPER_COLOR = [YELLOW, GREEN, BROWN, BLACK, RED] = ["yellow", "green", "brown", "black", "red"]
DIAPER_AMOUNT = {"little": "little", "small": "little", "medium": "medium", "big": "big", "large": "big"}
DIAPER_CONSISTENCY = [RUNNY, SOFT, SOLID, HARD] = ["runny", "soft", "solid", "hard"]
BOTTLE_TYPES = {"formula": "Formula", "milk": "Breast Milk", "breastmilk": "Breast Milk"}

class DiaperEvent:
    diaper_type: str  # pee, poo, both
    poo_size: Optional[str]  # little, medium, big
    pee_size: Optional[str]  # little, medium, big
    color: Optional[str]  # yellow, green, brown, black, red
    consistency: Optional[str]  # runny, soft, solid, hard
    timestamp: datetime

    def __init__(self, diaper_type: str, poo_size: Optional[str], pee_size: Optional[str], color: Optional[str], consistency: Optional[str], timestamp: datetime):
        self.diaper_type = diaper_type
        self.poo_size = poo_size
        self.pee_size = pee_size
        self.color = color
        self.consistency = consistency
        self.timestamp = timestamp

    def __str__(self):
        return f"DiaperEvent(timestamp={self.timestamp}, type={self.diaper_type}, poo_size={self.poo_size}, pee_size={self.pee_size}, color={self.color}, consistency={self.consistency})"

# Data structure for breastfeeding event
class BreastFeedingEvent:
    right_duration_minutes: int
    left_duration_minutes: int
    timestamp: datetime

    # constructor to initialize the breastfeeding event with durations for both sides and timestamp
    def __init__(self, right_duration_minutes: int, left_duration_minutes: int, timestamp: datetime):
        self.right_duration_minutes = right_duration_minutes
        self.left_duration_minutes = left_duration_minutes
        self.timestamp = timestamp

    # function to pretty-print the breastfeeding event
    def __str__(self):
        return f"BreastFeedingEvent(timestamp={self.timestamp}, left_duration={self.left_duration_minutes} min, right_duration={self.right_duration_minutes} min)"

# Data structure for bottle feeding event
class BottleFeedingEvent:
    quantity_ml: float
    feed_type: str  # formula, breast milk, etc.
    timestamp: datetime

    def __init__(self, quantity_ml: float, feed_type: str, timestamp: datetime):
        self.quantity_ml = quantity_ml
        self.feed_type = feed_type
        self.timestamp = timestamp

    def __str__(self):
        return f"BottleFeedingEvent(timestamp={self.timestamp}, quantity={self.quantity_ml} ml, type={self.feed_type})"

# function to combine multiple bottle feeding lines into one event with total quantity and feed type
# if there are multiple events with the same feed type, combine their quantities
# if there are events with different feed types, we will create separate events for each feed type
def combine_bottle_feeding_events(events: List[Dict]) -> List[BottleFeedingEvent]:
    combined = {}
    for event in events:
        feed_type = event["feed_type"]
        quantity = event["quantity_ml"]
        if feed_type in combined:
            combined[feed_type] += quantity
        else:
            combined[feed_type] = quantity

    return [BottleFeedingEvent(quantity_ml=qty, feed_type=ftype, timestamp=None) for ftype, qty in combined.items()]

# function for combining multiple breastfeeding lines into one event with duration for left and right breasts
# breastfeeding side EACH means that the duration needs to be added to both right and left sides, while BOTH means that the duration is the total for both sides (e.g., 20 minutes each breast would be "each 20 minutes" or "both 40 minutes")
def combine_breastfeeding_events(events: List[Dict]) -> BreastFeedingEvent:
    if len(events) == 0:
        return None
    
    left_duration = 0
    right_duration = 0

    for event in events:
        if event["side"] == LEFT:
            left_duration += event["duration_minutes"]
        elif event["side"] == RIGHT:
            right_duration += event["duration_minutes"]
        elif event["side"] == EACH:
            left_duration += event["duration_minutes"]
            right_duration += event["duration_minutes"]
        elif event["side"] == BOTH:
            left_duration += event["duration_minutes"] / 2
            right_duration += event["duration_minutes"] / 2

    return BreastFeedingEvent(right_duration_minutes=right_duration, left_duration_minutes=left_duration, timestamp=None)

# function for combining multiple diaper lines into one event with type, size, color, consistency
# only combine if there are 2 events in the input list, one for pee and another for poop
def combine_diaper_events(events: List[Dict]) -> DiaperEvent:
    if len(events) == 0:
        return None
    if len(events) == 1:
        e = events[0]
        return DiaperEvent(diaper_type=e["diaper_type"], poo_size=e.get("poo_size"), pee_size=e.get("pee_size"), color=e.get("color"), consistency=e.get("consistency"), timestamp=None)

    # proceed if there are more than 1 events
    pee_event = next((e for e in events if e["diaper_type"] == PEE), None)
    poo_event = next((e for e in events if e["diaper_type"] == POO), None)

    if not pee_event or not poo_event:
        raise ValueError("Both pee and poo events are required to combine")

    # For simplicity, we will take the size, color, consistency from the poo event if available, otherwise from the pee event
    poo_size = poo_event.get("size")
    pee_size = pee_event.get("size")
    color = poo_event.get("color")
    consistency = poo_event.get("consistency")

    return DiaperEvent(diaper_type=BOTH, poo_size=poo_size, pee_size=pee_size, color=color, consistency=consistency, timestamp=None)

# ---------------------------------
# Main Parser
# ---------------------------------

def parse_message(text: str, telegram_datetime: datetime) -> Dict:
    logger.debug("parse_message: input text=%r", text)

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    timestamp = None
    errors = []

    # --------- Time Detection ----------
    for line in lines:
        maybe_time = parse_time_line(line, telegram_datetime)
        if maybe_time:
            timestamp = maybe_time
            break

    if not timestamp:
        logger.debug("parse_message: no valid time found")
        errors.append("No valid time found.")
        return {"timestamp": None, "events": [], "errors": errors}

    logger.debug("parse_message: timestamp=%s", timestamp)

    # --------- Event Parsing ----------
    # Note: Consider the timestamp line to also contain information about child's activity

    # maintain lists of different types of events in case we need to combine multiple before logging
    # e.g., 2 lines for breastfeeding at left and right should be combined into 1 event with duration for left and right breasts

    breastfeeding_events = []
    bottle_events = []
    diaper_events = []

    for line in lines:
        logger.debug("parse_message: parsing line=%r", line)
        # marker to indicate whether the line was processed
        line_processed = False
        lower = line.lower()

        if parse_time_line(line, telegram_datetime):
            # Time has already been processed earlier
            line_processed = True

        # Breastfeeding 
        if fuzzy_contains(lower, BREAST_SIDES) and DURATION_REGEX.search(text):
            side = fuzzy_extract_keyword(lower, BREAST_SIDES)
            duration = parse_duration(lower)
            if duration:
                breastfeeding_events.append({
                    "side": side,
                    "duration_minutes": duration,
                })
                line_processed = True
            else:
                errors.append(f"Side duration missing: {line}")

        # Bottle feeding
        if fuzzy_contains(lower, list(BOTTLE_TYPES.keys())) and AMOUNT_REGEX.search(lower):
            feed_type = fuzzy_extract_keyword(lower, list(BOTTLE_TYPES.keys()))
            amount = parse_amount(lower)
            if amount:
                bottle_events.append({
                    "quantity_ml": amount,
                    "feed_type": BOTTLE_TYPES[feed_type] if feed_type else None,
                })
                line_processed = True

        # Diaper wet
        if fuzzy_contains(lower, ["pee", "wet", "urine"]):
            size = fuzzy_extract_keyword(lower, list(DIAPER_AMOUNT.keys()))
            diaper_events.append({
                "diaper_type": PEE,
                "size": DIAPER_AMOUNT[size] if size else None,
            })
            print (diaper_events)
            line_processed = True

        # Diaper poop
        if fuzzy_contains(lower, ["poop", "potty", "dirty"]):
            size = fuzzy_extract_keyword(lower, list(DIAPER_AMOUNT.keys()))
            diaper_events.append({
                "diaper_type": POO,
                "size": DIAPER_AMOUNT[size] if size else None,
            })
            line_processed = True

        if not line_processed:
            errors.append(f"Unrecognized line: {line}")

    # Combine breastfeeding events
    combined_breastfeeding_event = combine_breastfeeding_events(breastfeeding_events)
    if combined_breastfeeding_event:
        combined_breastfeeding_event.timestamp = timestamp

    # Combine diaper events
    combined_diaper_event = combine_diaper_events(diaper_events)
    if combined_diaper_event:
        combined_diaper_event.timestamp = timestamp

    # Combine bottle feeding events
    combined_bottle_feeding_events = combine_bottle_feeding_events(bottle_events)
    for event in combined_bottle_feeding_events:
        event.timestamp = timestamp

    all_events = [combined_breastfeeding_event] + [combined_diaper_event] + combined_bottle_feeding_events

    for event in all_events:
        logger.debug("combined event: %s", event)

    return all_events

import sys
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s: %(message)s")
    message = sys.argv[1]
    events = parse_message(message, datetime.now())
    print (events)