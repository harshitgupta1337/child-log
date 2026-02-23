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


# ---------------------------------
# Main Parser
# ---------------------------------

BREAST_SIDES = [LEFT, RIGHT, EACH, BOTH] = ["left", "right", "each", "both"]

DIAPER_EVENT_TYPES = [PEE, POO, BOTH] = ["pee", "poo", "both"]
DIAPER_COLOR = [YELLOW, GREEN, BROWN, BLACK, RED] = ["yellow", "green", "brown", "black", "red"]
DIAPER_AMOUNT = {"little": "little", "small": "little", "medium": "medium", "big": "big"}
DIAPER_CONSISTENCY = [RUNNY, SOFT, SOLID, HARD] = ["runny", "soft", "solid", "hard"]
BOTTLE_TYPES = {"formula": "Formula", "milk": "Breast Milk", "breastmilk": "Breast Milk"}

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

    all_events = diaper_events + breastfeeding_events + bottle_events
    logger.debug("parse_message: %d event(s), %d error(s)", len(all_events), len(errors))
    return {
        "timestamp": timestamp,
        "events": all_events,
        "errors": errors
    }


import sys
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
    message = sys.argv[1]
    actions = parse_message(message, datetime.now())
    print (actions["timestamp"])
    for event in actions["events"]:
      print (event)
    print (actions["errors"])
