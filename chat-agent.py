import requests

TOOL_SERVER_URL = "http://127.0.0.1:3333/tools"

def call_tool(tool_name: str, args: dict):
    response = requests.post(
        f"{TOOL_SERVER_URL}/{tool_name}",
        json={"args": args},
        timeout=10
    )
    return response.json()

def ask(prompt):
    return input(prompt).strip()

def main():
    print("✈️ Welcome to Flight Booking Assistant\n")

    # Step 1: Collect details
    origin = ask("Enter origin airport code (e.g. DEL): ")
    destination = ask("Enter destination airport code (e.g. BLR): ")
    depart_date = ask("Enter departure date (YYYY-MM-DD): ")

    print("\nSearching flights...\n")

    # Step 2: Search flights
    flights = call_tool(
        "search_flights",
        {
            "origin": origin,
            "destination": destination,
            "departDate": depart_date,
            "tripType": "ONEWAY",
            "adults": 1,
            "cabin": "ECONOMY"
        }
    )

    if not flights:
        print("❌ No flights found")
        return

    # Step 3: Pick cheapest flight
    cheapest = min(flights, key=lambda f: float(f["price"]))

    print("✅ Cheapest flight found:")
    print(f"   Offer ID : {cheapest['offerId']}")
    print(f"   Price    : {cheapest['price']} {cheapest['currency']}")
    print(f"   Route    : {cheapest['origin']} → {cheapest['destination']}\n")

    # Step 4: Confirm booking
    confirm = ask("Do you want to book this flight? (yes/no): ").lower()
    if confirm != "yes":
        print("Booking cancelled.")
        return

    print("\nBooking flight...\n")

    # Step 5: Book flight
    booking = call_tool(
        "create_oneway_booking",
        {
            "userId": 1,
            "offerId": cheapest["offerId"],
            "tripType": "ONEWAY",
            "departDate": depart_date,
            "paymentMethod": "CARD",
            "passengers": [
                {
                    "firstName": "Soumyadeep",
                    "lastName": "Das",
                    "dob": "1999-05-14",
                    "travellerClass": "ECONOMY"
                }
            ]
        }
    )

    print("🎉 Booking Successful!")
    print(f"Booking Reference: {booking.get('bookingReference')}")
    print(f"Booking ID       : {booking.get('id')}")

if __name__ == "__main__":
    main()