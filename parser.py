import re
from datetime import datetime
from typing import List, Dict, Optional
from rapidfuzz import fuzz


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
            if fuzz.ratio(token, keyword) >= FUZZY_THRESHOLD:
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
        return best_match

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
            return int(single.group())

    return total if total > 0 else None


def parse_amount(text: str) -> Optional[float]:
    match = AMOUNT_REGEX.search(text)
    if not match:
        return None

    value = float(match.group(1))
    unit = match.group(2).lower()

    if unit == "oz":
        return round(value * 29.5735, 2)
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

    return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)


# ---------------------------------
# Main Parser
# ---------------------------------

def parse_message(text: str, telegram_datetime: datetime) -> Dict:

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    timestamp = None
    events = []
    errors = []
    current_context = None

    # --------- Time Detection ----------
    for line in lines:
        maybe_time = parse_time_line(line, telegram_datetime)
        if maybe_time:
            timestamp = maybe_time
            break

    if not timestamp:
        errors.append("No valid time found.")
        return {"timestamp": None, "events": [], "errors": errors}

    # --------- Event Parsing ----------
    # Note: Consider the timestamp line to also contain information about child's activity
    for line in lines:
        # marker to indicate whether the line was processed
        line_processed = False
        lower = line.lower()

        if parse_time_line(line, telegram_datetime):
            # Time has already been processed earlier
            line_processed = True

        # Breastfeed intent
        if fuzzy_contains(lower, ["breastfeed", "breast", "nurse"]):
            duration = parse_duration(lower)
            current_context = "breastfeed"

            if duration:
                events.append({
                    "event_type": "breastfeed",
                    "side": None,
                    "duration_minutes": duration,
                    "timestamp": timestamp
                })
                line_processed = True
            else:
                errors.append(f"Breastfeed duration missing: {line}")

        # Side-specific breastfeeding
        if current_context == "breastfeed":
            side = fuzzy_extract_keyword(lower, ["left", "right"])
            if side:
                duration = parse_duration(lower)
                if duration:
                    events.append({
                        "event_type": "breastfeed",
                        "side": side,
                        "duration_minutes": duration,
                        "timestamp": timestamp
                    })
                    line_processed = True
                else:
                    errors.append(f"Side duration missing: {line}")

        # Bottle feeding
        if fuzzy_contains(lower, ["formula", "bottle", "fed", "milk"]):
            amount = parse_amount(lower)
            if amount:
                events.append({
                    "event_type": "bottle_feed",
                    "quantity_ml": amount,
                    "timestamp": timestamp
                })
                current_context = None
                line_processed = True

        # Diaper wet
        if fuzzy_contains(lower, ["pee", "wet", "urine"]):
            size = fuzzy_extract_keyword(lower, ["small", "big"])
            events.append({
                "event_type": "diaper",
                "diaper_type": "wet",
                "size": size,
                "timestamp": timestamp
            })
            line_processed = True
            current_context = None

        # Diaper poop
        if fuzzy_contains(lower, ["poop", "potty", "dirty"]):
            size = fuzzy_extract_keyword(lower, ["small", "big"])
            events.append({
                "event_type": "diaper",
                "diaper_type": "poop",
                "size": size,
                "timestamp": timestamp
            })
            line_processed = True
            current_context = None

        # Sleep
        if fuzzy_contains(lower, ["sleep", "slept", "nap"]):
            duration = parse_duration(lower)
            if duration:
                events.append({
                    "event_type": "sleep",
                    "sleep_minutes": duration,
                    "timestamp": timestamp
                })
            else:
                errors.append(f"Sleep duration missing: {line}")
            line_processed = True
            current_context = None

        if not line_processed:
            errors.append(f"Unrecognized line: {line}")

    return {
        "timestamp": timestamp,
        "events": events,
        "errors": errors
    }


import sys
if __name__ == "__main__":
    message = sys.argv[1]
    actions = parse_message(message, datetime.now())
    print (actions["timestamp"])
    for event in actions["events"]:
      print (event)
    print (actions["errors"])
