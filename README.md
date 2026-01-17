# Flight Booking AI Agent (MCP Architecture)

This project implements an AI-powered flight booking assistant
that communicates with a Java Spring Boot backend using an MCP-style
tool server.

## Architecture

User → AI Agent → MCP Tool Server → Java Backend

## Components

- ai_agent.py  
  - Conversational AI agent
  - Intent detection
  - Parameter extraction
  - Booking flow management

- mcp_server.py  
  - FastAPI tool server
  - Bridges AI agent with Java backend
  - Implements MCP-style tool registry

## Tech Stack

- Python
- FastAPI
- LangChain
- Ollama (LLM)
- Java Spring Boot (external service)

## Features

- Natural language flight search
- Cheapest flight selection
- Booking workflow
- Safe, deterministic backend calls

## How to Run

```bash
pip install -r requirements.txt
python mcp_server.py
python ai_agent.py