import asyncio
import threading
import sys
import queue
from datetime import date
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import google.generativeai as genai

# ---------------- CONFIG ----------------

# Path to the MCP server script
MCP_SERVER_SCRIPT = "server_mcp.py"

# ---------------- THREADED BRIDGE ----------------

class ThreadedMCPBridge:
    """
    Runs the Async MCP Client in a background thread 
    so that we can call it synchronously from the main thread.
    """
    def __init__(self, server_script_path: str):
        self.server_script_path = server_script_path
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.session: ClientSession | None = None
        self.ready_event = threading.Event()
        self.shutdown_event = None  # Created in _lifecycle

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._lifecycle())

    async def _lifecycle(self):
        """Manages the full lifecycle of the MCP connection."""
        self.shutdown_event = asyncio.Event()
        async with AsyncExitStack() as stack:
            print(f"🔌 Connecting to MCP Server: {self.server_script_path}...")
            
            server_params = StdioServerParameters(
                command=sys.executable,
                args=[self.server_script_path],
                env=None
            )

            stdio_transport = await stack.enter_async_context(stdio_client(server_params))
            self.stdio, self.write = stdio_transport
            
            self.session = await stack.enter_async_context(
                ClientSession(self.stdio, self.write)
            )
            
            await self.session.initialize()
            print("✅ Connected to MCP Server (Background Thread).")
            
            # Signal that we are ready
            self.ready_event.set()
            
            # Wait until shutdown is requested
            # We need to assign the event to the loop properly
            # Since this is running in 'self.loop', we can just use an asyncio.Event created in this loop
            # or use the one created in __init__ but we must be careful about loop binding.
            # Best practice: create event inside the loop or use threadsafe set.
            
            await self.shutdown_event.wait()
            
            print("🔌 Disconnecting MCP Server...")
            # Exiting the block will automatically close the stack (session + transport)

    def start(self):
        # We need to ensure the shutdown event is bound to the loop if we created it outside?
        # asyncio.Event() captures the *current* loop at creation. 
        # In __init__, there is no current loop usually, or it's the main thread's loop.
        # So we should create the event inside _lifecycle or bind it correctly.
        # TO FIX: We will create the event inside _lifecycle and expose a method to set it.
        self.thread.start()
        self.ready_event.wait() 

    def call_tool(self, tool_name: str, arguments: dict):
        """Thread-safe synchronous call to the async MCP tool."""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        future = asyncio.run_coroutine_threadsafe(
            self.session.call_tool(tool_name, arguments=arguments), 
            self.loop
        )
        
        try:
            result = future.result(timeout=15)
            if result.isError:
                return f"Error: {result.content}"
            return "\n".join([c.text for c in result.content if c.type == 'text'])
        except Exception as e:
            return f"Error executing tool {tool_name}: {str(e)}"

    def close(self):
        """Shuts down the background loop and MCP connection."""
        if self.loop.is_running():
            # Signal the lifecycle to exit
            self.loop.call_soon_threadsafe(self.shutdown_event.set)
            self.thread.join(timeout=3)


# Global Bridge Instance
BRIDGE = ThreadedMCPBridge(MCP_SERVER_SCRIPT)


# ---------------- TOOLS (SYNCHRONOUS) ----------------

# These functions are passed to Gemini. 
# They MUST be synchronous to work reliably with the standard send_message().

def search_flights(origin: str, destination: str, depart_date: str):
    """
    Search for one-way flights between two cities.
    
    Args:
        origin: 3-letter IATA code (e.g., BOM, DEL).
        destination: 3-letter IATA code.
        depart_date: YYYY-MM-DD format.
    """
    return BRIDGE.call_tool("search_flights", {
        "origin": origin,
        "destination": destination,
        "depart_date": depart_date
    })

def book_flight(offer_id: str, depart_date: str, first_name: str, last_name: str, dob: str, traveller_class: str = "ECONOMY"):
    """
    Book a flight using an offer ID.
    
    Args:
        offer_id: Offer ID from search results.
        depart_date: YYYY-MM-DD.
        first_name: Passenger first name.
        last_name: Passenger last name.
        dob: YYYY-MM-DD.
        traveller_class: ECONOMY, BUSINESS, or FIRST.
    """
    return BRIDGE.call_tool("book_flight_oneway", {
        "offer_id": offer_id,
        "depart_date": depart_date,
        "first_name": first_name,
        "last_name": last_name,
        "dob": dob,
        "traveller_class": traveller_class
    })

def get_my_bookings(user_id: int = 1):
    """Get all bookings for a user."""
    return BRIDGE.call_tool("get_my_bookings", {"user_id": user_id})


# ---------------- MAIN ----------------

def run_chat():
    # 1. Start Bridge
    BRIDGE.start()
    
    try:
        # 2. Setup Gemini
        tools_list = [search_flights, book_flight, get_my_bookings]
        
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            tools=tools_list,
            system_instruction=f"""
            You are a helpful flight booking assistant.
            Today is {date.today()}.
            
            Use the available tools to search and book flights. 
            When searching, convert city names to IATA codes (London=LHR, New York=JFK).
            """
        )

        chat = model.start_chat(enable_automatic_function_calling=True)

        print("\n✈️  Gemini + MCP Agent Ready! (Type 'exit' to quit)")
        print("---------------------------------------------------")

        while True:
            user_input = input("You: ")
            if user_input.lower() in ["exit", "quit"]:
                break
            
            # Standard synchronous call
            response = chat.send_message(user_input)
            print(f"Agent: {response.text}")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        BRIDGE.close()

if __name__ == "__main__":
    run_chat()