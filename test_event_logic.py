import sys
import asyncio
import json
import websockets

async def mock_mixitup_server(host='localhost', port=8911):
    print(f"Starting mock MixItUp server on {host}:{port}...")
    async def handler(websocket, path):
        print(f"Client connected to path: {path}")
        if path != "/api/v2/events":
            print(f"WARNING: Unexpected path {path}")
        try:
            # Send a few mock events
            events = [
                {"Type": "Follow", "User": {"Username": "MockFollower"}},
                {"Type": "Subscription", "User": {"Username": "MockSubscriber"}},
                {"Type": "Resubscription", "User": {"Username": "MockResubscriber"}},
                {"Type": "ChatMessage", "User": {"Username": "IgnoredUser"}} # Should be ignored
            ]
            for event in events:
                await asyncio.sleep(2)
                print(f"Sending event: {event['Type']}")
                await websocket.send(json.dumps(event))
            
            await asyncio.sleep(2)
            print("Mock events finished.")
        except websockets.exceptions.ConnectionClosed:
            print("Client disconnected")

    async with websockets.serve(handler, host, port):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    try:
        asyncio.run(mock_mixitup_server())
    except KeyboardInterrupt:
        pass
