import requests
import json
import re
from datetime import date, datetime
from typing import Dict, List, Optional

from langchain_community.chat_models import ChatOllama

# ---------------- CONFIG ----------------

TOOL_SERVER = "http://127.0.0.1:3333/tools"

print("Flight Booking Assistant (AI + MCP + Java Backend)")
print("Type 'exit' to quit\n")

llm = ChatOllama(
    model="llama3.1:8b",
    temperature=0
)

# ---------------- STATE ---------------- (I am trying to prevent random behaviour from the AI...So maintaining the state.)

conversation_state = "IDLE"
last_flights: List[Dict] = []
selected_flight: Optional[Dict] = None

# ---------------- MCP CALLS ----------------

def search_flights(params: dict):
    return requests.post(
        f"{TOOL_SERVER}/search_flights",
        json={"args": params},
        timeout=15
    ).json()

def create_oneway_booking(payload: dict):
    return requests.post(
        f"{TOOL_SERVER}/create_oneway_booking",
        json={"args": payload},
        timeout=15
    ).json()

# ---------------- INTENT (LLM + RULES) ----------------

def detect_intent(user_input: str) -> str:
    text = user_input.lower()

    if re.search(r"\b(book|reserve)\b", text):
        return "BOOK_FLIGHT" #instead of LLM deciding it, critical process intent initiation is done locally.

    prompt = f"""
Classify intent as ONE of:
- SEARCH_FLIGHTS
- GENERAL_CHAT

User message:
"{user_input}"

Respond with ONLY the label.
"""
    return llm.invoke(prompt).content.strip()

# ---------------- PARAM EXTRACTION ----------------

def extract_search_params(user_input: str) -> Dict:
    today = date.today()

    # --- LLM attempt ---
    llm_prompt = f"""
Extract flight search parameters.

CITY → IATA:
Mumbai/Bombay → BOM
Delhi → DEL
Bengaluru/Bangalore → BLR
Kolkata → CCU
Ranchi → IXR

Return JSON ONLY:
{{
  "origin": "XXX",
  "destination": "YYY",
  "departDate": "YYYY-MM-DD",
  "tripType": "ONEWAY",
  "adults": 1,
  "cabin": "ECONOMY"
}}

Today is {today}

User message:
"{user_input}"
"""
    try:
        parsed = json.loads(llm.invoke(llm_prompt).content)
        if parsed.get("origin") and parsed.get("destination") and parsed.get("departDate"):
            return parsed
    except Exception:
        pass

    # --- Regex fallback --- in case LLM fails to extract the IATA codes internally
    city_map = {
        "mumbai": "BOM", "bombay": "BOM",
        "delhi": "DEL",
        "bengaluru": "BLR", "bangalore": "BLR",
        "kolkata": "CCU",
        "ranchi": "IXR"
    }

    text = user_input.lower()
    origin = destination = None

    for city, code in city_map.items():
        if f"from {city}" in text:
            origin = code
        if f"to {city}" in text:
            destination = code

    date_match = re.search(
        r"(\d{1,2})(st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
        text
    )

    if not (origin and destination and date_match):
        return {}

    day = int(date_match.group(1))
    month = datetime.strptime(date_match.group(3).title(), "%b").month
    year = today.year

    candidate = datetime(year, month, day).date()
    if candidate < today:
        year += 1

    return {
        "origin": origin,
        "destination": destination,
        "departDate": datetime(year, month, day).strftime("%Y-%m-%d"),
        "tripType": "ONEWAY",
        "adults": 1,
        "cabin": "ECONOMY"
    }

# ---------------- UTIL ----------------

def get_cheapest_flights(flights: list, limit=7):
    return sorted(flights, key=lambda f: float(f["price"]))[:limit]

def parse_passenger_details(text: str):
    match = re.match(
        r"(\w+)\s+(\w+)\s+(\d{4}-\d{2}-\d{2})\s+(ECONOMY|BUSINESS|FIRST)",
        text.strip(),
        re.IGNORECASE
    )
    if not match:
        return None

    return {
        "firstName": match.group(1),
        "lastName": match.group(2),
        "dob": match.group(3),
        "travellerClass": match.group(4).upper()
    }

# ---------------- MAIN LOOP ----------------

while True: #It cannot scale, I should be able to scale it with diff features.
    user_input = input("You: ")

    if user_input.lower() in ("exit", "quit"):
        print("Goodbye....")
        break

    intent = detect_intent(user_input)

    # ---------- SEARCH ----------
    if intent == "SEARCH_FLIGHTS" and conversation_state == "IDLE":
        print("AI detected flight search intent")

        params = extract_search_params(user_input)
        if not params:
            print("Assistant: I couldn't understand the flight details.")
            continue

        response = search_flights(params)
        flights = response.get("data") if isinstance(response, dict) else response

        if not flights:
            print("Assistant: No flights found.")
            continue

        last_flights = get_cheapest_flights(flights)
        conversation_state = "SEARCH_DONE"

        print(f"Assistant: I found {len(flights)} flights.")
        print("Assistant: Here are the 7 cheapest options:\n")

        for i, f in enumerate(last_flights, 1):
            print(
                f"{i}. {f['origin']} → {f['destination']} | "
                f"{f['price']} {f['currency']} | OfferId: {f['offerId']}"
            )

        print("\nSay **'Book option 1'** or **'Book cheapest'**")



    # ---------- BOOK SELECT ----------
    elif conversation_state == "SEARCH_DONE" and re.search(r"\b(book option|book cheapest|book\s+\d+)\b", user_input.lower()):
        idx_match = re.search(r"option\s+(\d+)", user_input.lower())
        index = int(idx_match.group(1)) - 1 if idx_match else 0

        selected_flight = last_flights[index]
        conversation_state = "AWAITING_PASSENGER_DETAILS"

        print("Booking selected flight:")
        print(
            f"{selected_flight['origin']} → {selected_flight['destination']} | "
            f"{selected_flight['price']} {selected_flight['currency']}"
        )
        print("\nEnter passenger details:")
        print("Format: FirstName LastName YYYY-MM-DD TRAVELLER_CLASS")

    elif conversation_state == "SEARCH_DONE" and re.search(
            r"\b(no|don't|do not|not now|cancel|exit|stop)\b",
            user_input.lower()
    ):
        print("Assistant: No problem 😁Let me know if you want to search again.")
        conversation_state = "IDLE"
        last_flights = []
        selected_flight = None
        continue

    # ---------- PASSENGER + BOOK ----------
    elif conversation_state == "AWAITING_PASSENGER_DETAILS":
        passenger = parse_passenger_details(user_input)
        if not passenger:
            print("Invalid format. Try again.")
            continue

        booking_payload = {
            "userId": 1,
            "offerId": selected_flight["offerId"],
            "tripType": "ONEWAY",
            "departDate": selected_flight["departDate"],
            "paymentMethod": "CARD",
            "passengers": [passenger]
        }

        result = create_oneway_booking(booking_payload)

        if result.get("bookingReference"):
            print("\nBooking Confirmed!")
            print("Booking Reference:", result["bookingReference"])
        else:
            print("❌ Booking failed:", result)

        # reset
        conversation_state = "IDLE"
        selected_flight = None
        last_flights = []

    # ---------- CHAT ----------
    else:
        safe_prompt = f"""
You are a FLIGHT BOOKING ASSISTANT.

Rules:
- Do NOT roleplay
- Do NOT invent prices or airlines
- Keep responses short
- Guide user to search or booking

User message:
"{user_input}"
"""
        print("Assistant:", llm.invoke(safe_prompt).content)