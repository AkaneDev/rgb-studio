# MixItUp Event Trigger GUI

A Python GUI application that allows you to trigger custom Python code when someone follows, subscribes, or resubscribes via MixItUp.

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
2. Ensure MixItUp is running and the Developer API is enabled.
3. (Optional) Ensure iCUE is running and the SDK is enabled. Click **Connect iCUE** in the app.
4. Enter the **IP Address** (usually `localhost`) and **Port** (default is `8911`) for MixItUp.
5. Define the Python code you want to run for each event in the "Event Actions" section.
   - You can use the variable `{user}` in your code to refer to the user who triggered the event.
   - You can use `sdk` to control iCUE (e.g., `sdk.set_led_colors(...)`).
   - You can use `kb` and `Key` to simulate keyboard presses (e.g., `kb.press(Key.space); kb.release(Key.space)`).
   - You can use `play_anim("animation_name")` to trigger a custom keyboard animation.
   - Example: `print(f"{user} just followed!"); play_anim("welcome_blink")`
6. Create animations using the **Animation Editor**:
   - Click the "Animation Editor" button.
   - Add a new animation and add frames to it.
   - For each frame, set the duration and the color for the LEDs.
7. Click **Start Listening**.

## How it works

- The app connects to MixItUp's **Developer API WebSocket** (`ws://host:port/api/events`).
- It listens for event notifications pushed by MixItUp.
- When a Follow, Subscription, or Resubscription event occurs, the app executes the custom Python code provided in the GUI using `exec()`.
- Animations are stored in `animations.json` and played in separate threads when triggered.
- Logs are displayed in the application window to help you debug and track events.
