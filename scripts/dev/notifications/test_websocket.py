"""
WebSocket Server Test Script
Run this inside the Docker container to test WebSocket functionality
"""

import asyncio
import websockets.client
import websockets.server
import logging
import json
import os
from datetime import datetime
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test WebSocket client
async def test_client():
    """Simple test client to connect to our WebSocket server"""
    token = "test_websocket_token_test"
    uri = f"ws://localhost:8000/api/v1/notifications/ws?token={token}"
    
    logger.info(f"Attempting to connect to WebSocket at {uri}")
    try:
        async with websockets.client.connect(uri) as websocket:
            logger.info("Connected to WebSocket server!")
            
            # Wait for welcome message
            logger.info("Waiting for welcome message...")
            try:
                welcome_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                welcome_data = json.loads(welcome_message)
                logger.info(f"Received welcome message: {welcome_data}")
                
                if welcome_data.get("type") == "connection_established":
                    logger.info(f"Successfully authenticated as user: {welcome_data.get('user_id')}")
                else:
                    logger.warning(f"Unexpected welcome message type: {welcome_data.get('type')}")
            except asyncio.TimeoutError:
                logger.error("Timed out waiting for welcome message")
                return
            except Exception as e:
                logger.error(f"Error receiving welcome message: {str(e)}")
                return
            
            # Send a ping message
            logger.info("Sending ping message...")
            ping_message = {
                "type": "ping",
                "client": "test_script",
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send(json.dumps(ping_message))
            logger.info(f"Sent ping message: {ping_message}")
            
            # Wait for pong response
            logger.info("Waiting for pong response...")
            try:
                pong_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                pong_data = json.loads(pong_message)
                logger.info(f"Received pong response: {pong_data}")
                
                if pong_data.get("type") == "pong":
                    logger.info("Ping/pong successful!")
                else:
                    logger.warning(f"Unexpected response to ping: {pong_data.get('type')}")
            except asyncio.TimeoutError:
                logger.error("Timed out waiting for pong response")
            except Exception as e:
                logger.error(f"Error receiving pong response: {str(e)}")
            
            logger.info("Test completed successfully!")
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
        logger.error(traceback.format_exc())

# Test WebSocket server (simple echo server for testing)
async def echo_server(websocket, path):
    """Simple echo WebSocket server for testing"""
    address = websocket.remote_address
    logger.info(f"Client connected from {address}")
    
    try:
        # Send welcome message
        await websocket.send(json.dumps({
            "type": "connection_established",
            "timestamp": datetime.now().isoformat()
        }))
        
        async for message in websocket:
            logger.info(f"Received message: {message}")
            message_data = json.loads(message)
            
            # Special handling for ping messages
            if isinstance(message_data, dict) and message_data.get("type") == "ping":
                await websocket.send(json.dumps({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat(),
                    "received_ping": message_data
                }))
                continue
                
            # Otherwise echo the message back
            await websocket.send(message)
    except Exception as e:
        logger.error(f"Error in WebSocket server: {str(e)}")
    finally:
        logger.info(f"Client disconnected from {address}")

async def start_test_server():
    """Start a test WebSocket server on port 8001 for testing"""
    server = await websockets.server.serve(echo_server, "0.0.0.0", 8001)
    logger.info("Test WebSocket server running on ws://0.0.0.0:8001")
    return server

async def main():
    """Run both server and client tests"""
    # First test connecting to our actual WebSocket server
    logger.info("Testing connection to actual WebSocket server...")
    await test_client()
    
    # Now start a test server and test connecting to it
    logger.info("Starting test WebSocket server...")
    server = await start_test_server()
    
    # Test connecting to the test server
    test_uri = "ws://localhost:8001"
    logger.info(f"Testing connection to test server at {test_uri}")
    try:
        async with websockets.client.connect(test_uri) as websocket:
            logger.info("Connected to test WebSocket server!")
            
            # Wait for welcome message
            welcome = await websocket.recv()
            logger.info(f"Received welcome from test server: {welcome}")
            
            # Send a ping message
            ping_message = json.dumps({
                "type": "ping",
                "message": "Hello from test client",
                "timestamp": datetime.now().isoformat()
            })
            await websocket.send(ping_message)
            logger.info(f"Sent ping message to test server: {ping_message}")
            
            # Wait for pong response
            pong = await websocket.recv()
            logger.info(f"Received pong from test server: {pong}")
            
            # Send another test message
            test_message = json.dumps({
                "type": "test",
                "message": "Hello test server",
                "timestamp": datetime.now().isoformat()
            })
            await websocket.send(test_message)
            logger.info(f"Sent test message: {test_message}")
            
            # Wait for echo response
            echo = await websocket.recv()
            logger.info(f"Received echo from test server: {echo}")
    except Exception as e:
        logger.error(f"Test server connection error: {str(e)}")
    
    # Keep the server running for a bit
    await asyncio.sleep(2)
    server.close()
    await server.wait_closed()
    logger.info("All tests completed")

if __name__ == "__main__":
    asyncio.run(main()) 