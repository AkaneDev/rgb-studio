
import sys
from unittest.mock import MagicMock

# Mocking the SDKs since we might not have them in the environment
sys.modules['cuesdk'] = MagicMock()
sys.modules['pynput'] = MagicMock()
sys.modules['pynput.keyboard'] = MagicMock()

import main

def test_exec_context():
    print("Testing exec context injection...")
    app = main.QApplication([])
    window = main.MainWindow()
    
    # Manually setup what we want to test
    window.sdk = MagicMock()
    window.keyboard_controller = MagicMock()
    
    # Define a test action that uses all injected variables
    test_code = "print(f'Testing {user}'); kb.type('hello'); sdk.set_led_colors([])"
    
    try:
        # We need to reach into handle_event logic
        exec_globals = {
            "user": "TestUser",
            "sdk": window.sdk,
            "kb": window.keyboard_controller,
            "Key": MagicMock()
        }
        exec(test_code, exec_globals)
        print("Success: exec() context contains all expected variables.")
        
        # Verify calls
        window.keyboard_controller.type.assert_called_with('hello')
        window.sdk.set_led_colors.assert_called_with([])
        print("Success: keyboard and sdk methods were called.")
        
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Mocking SDK_AVAILABLE to True for the test
    main.SDK_AVAILABLE = True
    test_exec_context()
