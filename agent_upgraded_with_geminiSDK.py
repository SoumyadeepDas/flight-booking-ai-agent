import os
import requests
from datetime import date
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool

# ---------------- CONFIG ----------------

# Direct connection to Java Backend (bypassing server.py)
JAVA_BACKEND_URL = "http://localhost:8080/api/v1"

# Configure the SDK (assumes GOOGLE_API_KEY is set in environment variables)
# if "GOOGLE_API_KEY" not in os.environ:
#     print("Warning: GOOGLE_API_KEY not found in environment variables.")

# ---------------- TOOLS ----------------

def search_flights(origin: str, destination: str, depart_date: str):
    """
    Search for one-way flights between two cities.
    
    Args:
        origin: 3-letter IATA code for origin city (e.g., BOM, DEL, BLR, CCU).
        destination: 3-letter IATA code for destination city.
        depart_date: Date of departure in YYYY-MM-DD format.
    """
    print(f"\n[Tool] Searching flights: {origin} -> {destination} on {depart_date}")
    url = f"{JAVA_BACKEND_URL}/flights/search"
    payload = {
        "origin": origin,
        "destination": destination,
        "departDate": depart_date,
        "tripType": "ONEWAY",
        "adults": 1,
        "cabin": "ECONOMY"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        flights = response.json()
        
        # Sort by price and take top 5 to keep context manageable
        sorted_flights = sorted(flights, key=lambda x: float(x['price']))[:5]
        return sorted_flights
    except Exception as e:
        return f"Error searching flights: {str(e)}"

def book_flight(offer_id: str, depart_date: str, first_name: str, last_name: str, dob: str, traveller_class: str = "ECONOMY"):
    """
    Book a flight using an offer ID from a previous search.
    
    Args:
        offer_id: The unique Offer ID of the flight to book.
        depart_date: Departure date in YYYY-MM-DD format.
        first_name: Passenger's first name.
        last_name: Passenger's last name.
        dob: Passenger's date of birth in YYYY-MM-DD format.
        traveller_class: Class of travel (ECONOMY, BUSINESS, FIRST). Defaults to ECONOMY.
    """
    print(f"\n[Tool] Booking flight: Offer {offer_id} for {first_name} {last_name}")
    url = f"{JAVA_BACKEND_URL}/bookings/oneway"
    
    passenger = {
        "firstName": first_name,
        "lastName": last_name,
        "dob": dob,
        "travellerClass": traveller_class
    }
    
    payload = {
        "userId": 1,  # Hardcoded for this demo
        "offerId": offer_id,
        "tripType": "ONEWAY",
        "departDate": depart_date,
        "paymentMethod": "CARD",
        "passengers": [passenger]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return f"Error booking flight: {str(e)}"

# ---------------- AGENT SETUP ----------------

def run_chat_loop():
    print("✈️  Gemini Flight Agent (Powered by Native Google GenAI SDK)")
    print("---------------------------------------------------------")
    print("I can search and book flights directly. Type 'exit' to quit.\n")
    
    # Define the tools available to the model
    tools_list = [search_flights, book_flight]

    # Initialize the model with tools and system instruction
    model = genai.GenerativeModel(
        model_name='gemini-2.5-flash',
        tools=tools_list,
        system_instruction=f"""
        You are a helpful flight booking assistant capable of searching and booking flights.
        Today is {date.today()}.
        
        INSTRUCTIONS:
        1. CITY CODES: If the user provides city names, convert them to IATA codes (e.g., Mumbai=BOM, Delhi=DEL, Bangalore=BLR, Kolkata=CCU).
        2. SEARCHING: Always search before booking. Display the 'offerId' clearly in search results.
        3. BOOKING: To book, you need an 'offerId' and passenger details (Name, DOB). Ask for them if missing.
        4. CONFIRMATION: Show the booking reference after a successful booking.
        """
    )

    # Start a chat session with automatic function calling enabled
    chat = model.start_chat(enable_automatic_function_calling=True)
    
    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break
            
            # Send message to the model
            # The SDK handles the tool calling loop internally when enable_automatic_function_calling=True
            response = chat.send_message(user_input)
            
            # Print the text response from the model
            print(f"Agent: {response.text}")
                
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    run_chat_loop()
