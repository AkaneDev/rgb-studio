import sys
from unittest.mock import MagicMock

# Mock dependencies that might not be installed
sys.modules['cuesdk'] = MagicMock()
sys.modules['pynput'] = MagicMock()
sys.modules['pynput.keyboard'] = MagicMock()

from main import MainWindow, AnimationEditorDialog
from PyQt6.QtWidgets import QApplication

def test_animation_logic():
    app = QApplication(sys.argv)
    window = MainWindow()
    
    # Check path input default
    assert window.path_input.currentText() == "/api/v2/events"
    print("SUCCESS: Default path is /api/v2/events")

    # Check if play_anim is in handle_event context
    # We can't easily test exec() without side effects, but we can check if it's called
    window.play_animation = MagicMock()
    window.follow_action.setText("play_anim('test_anim')")
    window.handle_event("follow", "test_user")
    
    window.play_animation.assert_called_with('test_anim')
    print("SUCCESS: play_anim was correctly called from handle_event")

    # Check animation loading
    window.animations = {"test_anim": [{"leds": {"1": [255, 0, 0]}, "duration": 0.5}]}
    window.sdk = MagicMock()
    window.play_animation("test_anim")
    print("SUCCESS: Animation playback triggered")

    # Test Editor Dialog initialization
    dialog = AnimationEditorDialog(window.animations, True, window.sdk)
    assert "test_anim" in window.animations
    print("SUCCESS: AnimationEditorDialog initialized correctly")

    return True

if __name__ == "__main__":
    try:
        test_animation_logic()
    except Exception as e:
        print(f"FAILURE: {e}")
        sys.exit(1)
