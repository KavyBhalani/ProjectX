import requests
import json
import asyncio
import websockets

# CHANGE THIS TO YOUR RENDER URL
BASE_URL = "https://projectx-r8rj.onrender.com"
# For websockets, replace https:// with wss://
WS_URL = BASE_URL.replace("https://", "wss://")

async def test_chat_api():
    print("=== 1. Creating a User ===")
    user_response = requests.post(
        f"{BASE_URL}/api/users",
        json={"username": "TestUser", "email": "test17@test.com"}
    )
    
    if user_response.status_code == 400:
        print("User already exists! Please change the email in the code if you want a new one.")
        return
        
    user_data = user_response.json()
    user_id = user_data["user_id"]
    print(f"✅ User Created! ID: {user_id}")

    print("\n=== 2. Creating a Companion ===")
    comp_response = requests.post(
        f"{BASE_URL}/api/users/{user_id}/companions",
        json={"name": "Emma", "gender": "female", "persona_type": "best friend"}
    )
    comp_data = comp_response.json()
    companion_id = comp_data["companion_id"]
    print(f"✅ Companion Created! ID: {companion_id}")

    print("\n=== 3. Testing the Real-time WebSocket Chat ===")
    websocket_url = f"{WS_URL}/ws/chat/{user_id}/{companion_id}"
    print(f"Connecting to {websocket_url}...")
    
    try:
        async with websockets.connect(websocket_url) as websocket:
            print("✅ Connected!")
            
            is_streaming = False
            
            async def listen():
                nonlocal is_streaming
                try:
                    while True:
                        response = await websocket.recv()
                        data = json.loads(response)
                        if data.get("type") == "token":
                            print(data.get("text", ""), end="", flush=True)
                            is_streaming = True
                        elif data.get("type") == "error":
                            print(f"\n[SERVER ERROR]: {data.get('text')}")
                except websockets.exceptions.ConnectionClosed:
                    print("\n[Connection closed by server]")

            listener_task = asyncio.create_task(listen())
            
            # Run the input loop
            await asyncio.sleep(0.5) 
            while True:
                user_msg = await asyncio.to_thread(input, "\n\nYou: ")
                if user_msg.lower() == 'quit':
                    break
                    
                print("Emma: ", end="", flush=True)
                await websocket.send(json.dumps({"type": "message", "text": user_msg}))
                
                # Give Emma a second to start replying, then wait until streaming finishes before prompting again
                await asyncio.sleep(1)
                while is_streaming:
                    is_streaming = False # Reset flag and wait to see if more tokens arrive
                    await asyncio.sleep(1)
                
            listener_task.cancel()

    except Exception as e:
        print(f"WebSocket error: {e}")

if __name__ == "__main__":
    asyncio.run(test_chat_api())
