# RGB Studio - Webhook Event Trigger

A Python GUI application that triggers custom Python code and keyboard animations in response to HTTP POST requests (Webhooks).

## Requirements

- Python 3.7+
- [Corsair iCUE](https://www.corsair.com/icue) (optional, for keyboard lighting).
- SDK enabled in iCUE settings (Settings -> Software and Games -> Enable SDK).
- Dependencies: `PyQt6`, `aiohttp`, `cuesdk`, `pynput`

## Installation

1. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```bash
   python main.py
   ```
2. (Optional) Ensure iCUE is running and the SDK is enabled. Click **Connect iCUE** in the app.
3. Configure the **Webhook Server Configuration** (Host and Port). Default is `0.0.0.0:8080`.
4. Click **Start Server**.
5. Define actions for standard events (**Follow**, **Sub**, **Resub**) or create **Custom Events**.
6. Trigger events by sending a POST request to your server:
   - **Root URL**: `http://localhost:8080/`
     - Body (JSON): `{"event": "follow", "user": "JohnDoe"}`
     - Body (Form): `event=follow&user=JohnDoe`
   - **Specific Event URL**: `http://localhost:8080/event/follow`
     - Body (Plain Text): `JohnDoe` (will be treated as the username)
     - Body (JSON): `{"user": "JohnDoe"}`
7. Use the **Animation Editor** to create complex RGB patterns.
8. Use the **KeySim (Virtual Keyboard)** to preview animations without physical hardware.

## Available Variables in Python Actions

- `user`: The username extracted from the POST request.
- `sdk`: The Corsair iCUE SDK session (if connected).
- `kb`: `pynput.keyboard.Controller` for simulating key presses.
- `Key`: `pynput.keyboard.Key` constants.
- `play_anim(name)`: Function to trigger a saved animation.

## Example Action

```python
print(f"Welcome {user}!"); play_anim("RainbowWave"); kb.press(Key.f1); kb.release(Key.f1)
```

## How it works

- The app hosts an `aiohttp` server that listens for POST requests.
- When a request is received, it extracts the event type and username.
- It matches the event type against the defined "Standard Event Actions" or "Custom Events".
- It executes the corresponding Python code in a background thread to keep the GUI responsive.
- Animations are stored in `animations.json` and custom events in `custom_events.json`.
