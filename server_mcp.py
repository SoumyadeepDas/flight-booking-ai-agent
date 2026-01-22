from fastmcp import FastMCP
import requests
from typing import List, Optional

# Initialize the MCP Server
mcp = FastMCP("Flight Booking MCP Server")

# Configuration
JAVA_BASE_URL = "http://localhost:8080/api/v1"

# ---------------- Utility ----------------

def post_request(path: str, payload: dict) -> dict:
    """Helper to send POST requests to the Java backend."""
    try:
        response = requests.post(f"{JAVA_BASE_URL}{path}", json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def get_request(path: str) -> dict:
    """Helper to send GET requests to the Java backend."""
    try:
        response = requests.get(f"{JAVA_BASE_URL}{path}", timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

# ---------------- Tools ----------------

@mcp.tool()
def search_flights(origin: str, destination: str, depart_date: str) -> List[dict]:
    """
    Search for one-way flights between two cities.
    
    Args:
        origin: 3-letter IATA code for origin city (e.g., BOM, DEL).
        destination: 3-letter IATA code for destination city.
        depart_date: Date of departure in YYYY-MM-DD format.
    """
    payload = {
        "origin": origin,
        "destination": destination,
        "departDate": depart_date,
        "tripType": "ONEWAY",
        "adults": 1,
        "cabin": "ECONOMY"
    }
    # We call the backend search endpoint
    # Note: The original server.py had logic to sort/limit. 
    # We can keep that logic here or let the agent handle it.
    # For now, let's return the raw list so the model sees all options.
    return post_request("/flights/search", payload)

@mcp.tool()
def book_flight_oneway(offer_id: str, depart_date: str, first_name: str, last_name: str, dob: str, traveller_class: str = "ECONOMY") -> dict:
    """
    Book a one-way flight using an offer ID.
    
    Args:
        offer_id: The unique Offer ID from search results.
        depart_date: Departure date (YYYY-MM-DD).
        first_name: Passenger first name.
        last_name: Passenger last name.
        dob: Passenger DOB (YYYY-MM-DD).
        traveller_class: ECONOMY, BUSINESS, or FIRST.
    """
    passenger = {
        "firstName": first_name,
        "lastName": last_name,
        "dob": dob,
        "travellerClass": traveller_class
    }
    
    payload = {
        "userId": 1, # Hardcoded for demo parity with old server
        "offerId": offer_id,
        "tripType": "ONEWAY",
        "departDate": depart_date,
        "paymentMethod": "CARD",
        "passengers": [passenger]
    }
    
    return post_request("/bookings/oneway", payload)

@mcp.tool()
def get_my_bookings(user_id: int = 1) -> dict:
    """
    Get all bookings for a specific user.
    
    Args:
        user_id: The numeric ID of the user. Defaults to 1.
    """
    return get_request(f"/bookings/user/{user_id}")

@mcp.tool()
def get_booking_details(booking_reference: str) -> dict:
    """
    Get details of a specific booking by its reference code.
    
    Args:
        booking_reference: The alpha-numeric booking reference (e.g., BOOK123).
    """
    return get_request(f"/bookings/reference/{booking_reference}")

if __name__ == "__main__":
    # This runs the MCP server on stdio (standard input/output) by default
    # which is the standard way MCP clients communicate with servers.
    mcp.run()
