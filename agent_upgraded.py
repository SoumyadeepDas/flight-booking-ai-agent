import os
import requests
import json
from datetime import date
from typing import List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import tool

# ---------------- CONFIG ----------------

# Direct connection to Java Backend (bypassing server.py)
JAVA_BACKEND_URL = "http://localhost:8080/api/v1"

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0
)

# ---------------- TOOLS ----------------

@tool
def search_flights(origin: str, destination: str, depart_date: str):
    """
    Search for one-way flights between two cities.
    
    Args:
        origin: 3-letter IATA code for origin city (e.g., BOM, DEL, BLR, CCU).
        destination: 3-letter IATA code for destination city.
        depart_date: Date of departure in YYYY-MM-DD format.
    """
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

@tool
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

# Bind tools to the model
tools = [search_flights, book_flight]
llm_with_tools = llm.bind_tools(tools)

def run_chat_loop():
    print("✈️  Gemini Flight Agent (Upgraded with Function Calling)")
    print("---------------------------------------------------------")
    print("I can search and book flights directly. Type 'exit' to quit.\n")
    
    system_message = SystemMessage(content=f"""
    You are a helpful flight booking assistant capable of searching and booking flights.
    Today is {date.today()}.
    
    INSTRUCTIONS:
    1. CITY CODES: If the user provides city names, convert them to IATA codes (e.g., Mumbai=BOM, Delhi=DEL, Bangalore=BLR, Kolkata=CCU).
    2. SEARCHING: Always search before booking. Display the 'offerId' clearly in search results.
    3. BOOKING: To book, you need an 'offerId' and passenger details (Name, DOB). Ask for them if missing.
    4. CONFIRMATION: Show the booking reference after a successful booking.
    """)
    
    # Initialize conversation history
    messages = [system_message]
    
    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break
            
            # Append user message
            messages.append(HumanMessage(content=user_input))
            
            # First LLM call (Decide what to do)
            response = llm_with_tools.invoke(messages)
            messages.append(response)
            
            # Check if the model wants to call tools
            if response.tool_calls:
                # Process all tool calls
                for tool_call in response.tool_calls:
                    print(f"🤖 Calling tool: {tool_call['name']}...")
                    
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    
                    # Execute the appropriate tool
                    if tool_name == "search_flights":
                        result = search_flights.invoke(tool_args)
                    elif tool_name == "book_flight":
                        result = book_flight.invoke(tool_args)
                    else:
                        result = "Error: Unknown tool"
                    
                    # Append tool result to history
                    messages.append(ToolMessage(
                        tool_call_id=tool_call["id"],
                        name=tool_name,
                        content=str(result)
                    ))
                
                # Second LLM call (Generate final response using tool outputs)
                final_response = llm_with_tools.invoke(messages)
                print(f"Agent: {final_response.content}")
                messages.append(final_response)
                
            else:
                # No tools needed, just a normal reply
                print(f"Agent: {response.content}")
                
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    run_chat_loop()
