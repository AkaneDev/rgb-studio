# MixItUp v2 Event Trigger GUI

A Python GUI application that allows you to trigger custom Python code when someone follows, subscribes, or resubscribes via the MixItUp v2 Developer API.

## Requirements

- Python 3.7+
- [MixItUp App](https://mixitupapp.com/) installed and running.
- [Corsair iCUE](https://www.corsair.com/icue) (optional, for keyboard lighting).
- Developer API enabled in MixItUp (Services -> Developer API -> Connect).
- SDK enabled in iCUE settings (Settings -> Software and Games -> Enable SDK).
- Dependencies: `websockets`, `PyQt6`, `python-dotenv`, `aiohttp`, `cuesdk`, `pynput`

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
2. Ensure MixItUp is running and the Developer API (v2) is enabled.
3. (Optional) Ensure iCUE is running and the SDK is enabled. Click **Connect iCUE** in the app.
4. Enter the **IP Address** (usually `localhost`) and **Port** (default is `8911`) for MixItUp. 
   - Select or enter the **Base Path**. Default is `/api/v2/events`.
   - If you get a **404 error**, try `/api/v1/events` or `/events`. 
   - Ensure the Developer API is enabled in MixItUp (Services -> Developer API -> Connect).
5. Define the Python code you want to run for each event in the "Event Actions" section.
   - You can use the variable `{user}` in your code to refer to the user who triggered the event.
   - You can use `sdk` to control iCUE (e.g., `sdk.set_led_colors(...)`).
   - You can use `kb` and `Key` to simulate keyboard presses (e.g., `kb.press(Key.space); kb.release(Key.space)`).
   - You can use `play_anim("animation_name")` to trigger a custom keyboard animation.
   - Example: `print(f"{user} just followed!"); play_anim("welcome_blink")`
6. Create **Custom Events** or use the **Webhook Server**:
   - The app hosts a Webhook server (default `http://localhost:8080/`).
   - You can send a POST request to this URL from MixItUp (using a "Web Request" action) with a JSON body like: `{"event": "my_custom_event", "user": "$username"}`.
   - In the "Custom Events" section of the GUI, add an event named `my_custom_event` and define its Python code.
7. Create animations using the **Animation Editor**:
   - Click the "Animation Editor" button.
   - Add a new animation and add frames to it.
   - For each frame, set the duration and the color for the LEDs.
8. Click **Start Listening**.

## How it works

- The app connects to MixItUp's **Developer API WebSocket**.
- It listens for event notifications pushed by MixItUp.
- It also hosts an HTTP Webhook server to receive custom events via POST requests.
- If the default `/api/v2/events` path returns a 404, the user can switch to `/api/v1/events` or `/events` via the GUI.
- When a Follow, Subscription, or Resubscription event occurs, the app executes the custom Python code provided in the GUI using `exec()`.
- Animations are stored in `animations.json` and played in separate threads when triggered.
- Logs are displayed in the application window to help you debug and track events.
