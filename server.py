from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any
import requests

# ---------------- App ----------------

app = FastAPI(title="Flight Booking Tool Server")

JAVA_BASE_URL = "http://localhost:8080/api/v1"

# ---------------- Tool Registry ----------------

TOOLS = {}

def register_tool(name: str, description: str):
    def decorator(fn):
        TOOLS[name] = {
            "name": name,
            "description": description,
            "handler": fn
        }
        return fn
    return decorator


@app.get("/tools")
def list_tools():
    return {
        "tools": [
            {"name": t["name"], "description": t["description"]}
            for t in TOOLS.values()
        ]
    }


class ToolCall(BaseModel):
    args: Dict[str, Any] = {}


@app.post("/tools/{tool_name}")
def call_tool(tool_name: str, call: ToolCall):
    if tool_name not in TOOLS:
        return {"error": f"Tool '{tool_name}' not found"}

    return TOOLS[tool_name]["handler"](call.args)

# ---------------- Utility ----------------

def post(path: str, payload: dict):
    return requests.post(
        f"{JAVA_BASE_URL}{path}",
        json=payload,
        timeout=10
    ).json()


def get(path: str):
    return requests.get(
        f"{JAVA_BASE_URL}{path}",
        timeout=10
    ).json()

# ---------------- Tools ----------------

# ---- Health ----
@register_tool(
    name="ping",
    description="Health check tool"
)
def ping(_: dict):
    return {
        "status": "ok",
        "message": "Tool server is running"
    }

# ---- User Tools ----
@register_tool(
    name="create_user",
    description="Create a new user"
)
def create_user(args: dict):
    return post("/users", args)


@register_tool(
    name="get_user",
    description="Get user by ID"
)
def get_user(args: dict):
    return get(f"/users/{args['userId']}")

# ---- Flight Tools ----
@register_tool(
    name="search_flights",
    description="Search flights"
)
def search_flights(args: dict):
    return post("/flights/search", args)

# ---- Booking Tools ----
@register_tool(
    name="create_oneway_booking",
    description="Create a one-way booking"
)
def create_oneway_booking(args: dict):
    return post("/bookings/oneway", args)


@register_tool(
    name="create_roundtrip_booking",
    description="Create a round-trip booking"
)
def create_roundtrip_booking(args: dict):
    return post("/bookings/roundtrip", args)


@register_tool(
    name="get_booking_by_id",
    description="Get booking by booking ID"
)
def get_booking_by_id(args: dict):
    return get(f"/bookings/{args['bookingId']}")


@register_tool(
    name="get_bookings_by_user",
    description="Get all bookings for a user"
)
def get_bookings_by_user(args: dict):
    return get(f"/bookings/user/{args['userId']}")


@register_tool(
    name="get_booking_by_reference",
    description="Get booking by reference number"
)
def get_booking_by_reference(args: dict):
    return get(f"/bookings/reference/{args['reference']}")

# ---------------- Run ----------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=3333)