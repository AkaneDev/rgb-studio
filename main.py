import sys
import asyncio
import json
import websockets
import time
try:
    from cuesdk import CorsairSessionState, CorsairDevicePropertyId, CorsairDataType, CorsairDeviceType, CorsairError, CorsairLedColor, CUESDK
    from pynput.keyboard import Controller, Key
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTextEdit, QGroupBox, QFormLayout, QDialog,
                             QListWidget, QColorDialog, QDoubleSpinBox,
                             QComboBox, QMessageBox, QGridLayout)
from PyQt6.QtCore import pyqtSignal, QObject, QThread, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen

class AnimationPlayer(QThread):
    def __init__(self, animation_data, sdk=None, keysim=None):
        super().__init__()
        self.animation_data = animation_data
        self.sdk = sdk
        self.keysim = keysim
        self.running = True

    def run(self):
        if not self.sdk and not self.keysim:
            return
        
        try:
            # animations are list of frames: [{"leds": {"LED_ID": [R,G,B]}, "duration": 0.5}]
            for frame in self.animation_data:
                if not self.running:
                    break
                
                led_colors = []
                keysim_colors = {}
                for led_id_str, rgb in frame.get("leds", {}).items():
                    try:
                        led_id = int(led_id_str)
                        if self.sdk:
                            led_colors.append(CorsairLedColor(led_id, rgb[0], rgb[1], rgb[2]))
                        if self.keysim:
                            keysim_colors[led_id] = rgb
                    except:
                        continue
                
                if self.sdk and led_colors:
                    self.sdk.set_led_colors(led_colors)
                if self.keysim and keysim_colors:
                    self.keysim.update_keys(keysim_colors)
                
                time.sleep(frame.get("duration", 0.1))
        except Exception as e:
            print(f"Animation playback error: {e}")

    def stop(self):
        self.running = False

class KeySimWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KeySim - iCUE Virtual Keyboard")
        self.resize(1000, 300)
        self.key_colors = {} # {led_id: (R, G, B)}
        self.setup_layout()

    def setup_layout(self):
        self.main_layout = QVBoxLayout(self)
        self.grid = QGridLayout()
        self.grid.setSpacing(2)
        self.main_layout.addLayout(self.grid)
        
        # Approximate standard keyboard layout mapping to LED IDs (rough)
        # 1-22: Esc, F1-F12, etc.
        # 23-40: Number row
        # etc.
        # For simplicity, we'll create a 6x22 grid and map IDs sequentially
        self.key_buttons = {}
        for row in range(6):
            for col in range(22):
                led_id = row * 22 + col + 1
                btn = QLabel()
                btn.setFixedSize(40, 40)
                btn.setStyleSheet("background-color: black; border: 1px solid #333;")
                btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
                # Label with small text for ID
                btn.setText(str(led_id))
                btn.setStyleSheet(btn.styleSheet() + "color: #555; font-size: 8px;")
                self.grid.addWidget(btn, row, col)
                self.key_buttons[led_id] = btn

    def update_keys(self, led_colors):
        # led_colors: {led_id: [R, G, B]}
        for led_id, rgb in led_colors.items():
            if led_id in self.key_buttons:
                color_str = f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"
                self.key_buttons[led_id].setStyleSheet(f"background-color: {color_str}; border: 1px solid #333; color: white; font-size: 8px;")
        self.update()

class AnimationEditorDialog(QDialog):
    def __init__(self, animations, sdk_available, sdk=None):
        super().__init__()
        self.setWindowTitle("Animation Frame Editor")
        self.resize(1200, 600)
        self.animations = animations # {name: [frames]}
        self.sdk_available = sdk_available
        self.sdk = sdk
        self.selected_leds = set()
        
        main_layout = QVBoxLayout(self)
        top_layout = QHBoxLayout()
        main_layout.addLayout(top_layout)
        
        # Left side: Animation list
        left_layout = QVBoxLayout()
        self.anim_list = QListWidget()
        self.anim_list.addItems(self.animations.keys())
        self.anim_list.currentRowChanged.connect(self.load_animation)
        
        anim_btns = QHBoxLayout()
        add_anim_btn = QPushButton("Add")
        add_anim_btn.clicked.connect(self.add_animation)
        del_anim_btn = QPushButton("Delete")
        del_anim_btn.clicked.connect(self.delete_animation)
        anim_btns.addWidget(add_anim_btn)
        anim_btns.addWidget(del_anim_btn)
        
        left_layout.addWidget(QLabel("Animations:"))
        left_layout.addWidget(self.anim_list)
        left_layout.addLayout(anim_btns)
        top_layout.addLayout(left_layout)
        
        # Middle side: Frame list
        mid_layout = QVBoxLayout()
        self.frame_list = QListWidget()
        self.frame_list.currentRowChanged.connect(self.load_frame)
        
        frame_btns = QHBoxLayout()
        add_frame_btn = QPushButton("Add Frame")
        add_frame_btn.clicked.connect(self.add_frame)
        del_frame_btn = QPushButton("Del Frame")
        del_frame_btn.clicked.connect(self.delete_frame)
        frame_btns.addWidget(add_frame_btn)
        frame_btns.addWidget(del_frame_btn)
        
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.01, 10.0)
        self.duration_spin.setSingleStep(0.1)
        self.duration_spin.setValue(0.1)
        self.duration_spin.valueChanged.connect(self.update_frame_duration)
        
        mid_layout.addWidget(QLabel("Frames:"))
        mid_layout.addWidget(self.frame_list)
        mid_layout.addLayout(frame_btns)
        mid_layout.addWidget(QLabel("Frame Duration (s):"))
        mid_layout.addWidget(self.duration_spin)
        top_layout.addLayout(mid_layout)

        # Right side: Visual Keyboard for selection
        kb_layout = QVBoxLayout()
        kb_layout.addWidget(QLabel("Per-Key Selection (Click to select/deselect):"))
        self.kb_grid = QGridLayout()
        self.kb_grid.setSpacing(2)
        self.key_buttons = {}
        for row in range(6):
            for col in range(22):
                led_id = row * 22 + col + 1
                btn = QPushButton(str(led_id))
                btn.setFixedSize(30, 30)
                btn.setCheckable(True)
                btn.setStyleSheet("background-color: #222; color: #888; font-size: 7px;")
                btn.clicked.connect(lambda checked, lid=led_id: self.toggle_led_selection(lid, checked))
                self.kb_grid.addWidget(btn, row, col)
                self.key_buttons[led_id] = btn
        
        kb_layout.addLayout(self.kb_grid)
        
        sel_btns = QHBoxLayout()
        self.color_btn = QPushButton("Set Color for Selected")
        self.color_btn.clicked.connect(self.set_selected_color)
        self.all_color_btn = QPushButton("Set Color for All Keys")
        self.all_color_btn.clicked.connect(self.set_all_color)
        self.clear_sel_btn = QPushButton("Clear Selection")
        self.clear_sel_btn.clicked.connect(self.clear_selection)
        sel_btns.addWidget(self.color_btn)
        sel_btns.addWidget(self.all_color_btn)
        sel_btns.addWidget(self.clear_sel_btn)
        kb_layout.addLayout(sel_btns)
        
        self.test_btn = QPushButton("Test Animation")
        self.test_btn.clicked.connect(self.test_animation)
        kb_layout.addWidget(self.test_btn)
        
        top_layout.addLayout(kb_layout)

    def load_animation(self, row):
        self.frame_list.clear()
        if row < 0: return
        name = self.anim_list.item(row).text()
        frames = self.animations.get(name, [])
        for i in range(len(frames)):
            self.frame_list.addItem(f"Frame {i+1}")
        if frames:
            self.frame_list.setCurrentRow(0)

    def add_animation(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Animation", "Enter animation name:")
        if ok and name:
            if name not in self.animations:
                self.animations[name] = []
                self.anim_list.addItem(name)
                self.anim_list.setCurrentRow(self.anim_list.count() - 1)
            else:
                QMessageBox.warning(self, "Warning", "Animation already exists.")

    def delete_animation(self):
        curr = self.anim_list.currentItem()
        if curr:
            name = curr.text()
            del self.animations[name]
            self.anim_list.takeItem(self.anim_list.row(curr))
            self.frame_list.clear()

    def add_frame(self):
        curr_anim = self.anim_list.currentItem()
        if not curr_anim:
            QMessageBox.warning(self, "Warning", "Select an animation first.")
            return
        name = curr_anim.text()
        new_frame = {"leds": {}, "duration": 0.1}
        self.animations[name].append(new_frame)
        self.frame_list.addItem(f"Frame {len(self.animations[name])}")
        self.frame_list.setCurrentRow(self.frame_list.count() - 1)

    def delete_frame(self):
        curr_anim = self.anim_list.currentItem()
        curr_frame_idx = self.frame_list.currentRow()
        if curr_anim and curr_frame_idx >= 0:
            name = curr_anim.text()
            self.animations[name].pop(curr_frame_idx)
            self.load_animation(self.anim_list.currentRow())

    def toggle_led_selection(self, led_id, checked):
        if checked:
            self.selected_leds.add(led_id)
            self.key_buttons[led_id].setStyleSheet("background-color: #444; color: white; border: 1px solid cyan; font-size: 7px;")
        else:
            self.selected_leds.discard(led_id)
            # Restore color if it has one in current frame
            self.refresh_kb_visual()

    def clear_selection(self):
        self.selected_leds.clear()
        for lid, btn in self.key_buttons.items():
            btn.setChecked(False)
        self.refresh_kb_visual()

    def refresh_kb_visual(self):
        curr_anim = self.anim_list.currentItem()
        curr_frame_idx = self.frame_list.currentRow()
        led_data = {}
        if curr_anim and curr_frame_idx >= 0:
            name = curr_anim.text()
            led_data = self.animations[name][curr_frame_idx].get("leds", {})
        
        for lid, btn in self.key_buttons.items():
            lid_str = str(lid)
            if lid in self.selected_leds:
                btn.setStyleSheet("background-color: #444; color: white; border: 1px solid cyan; font-size: 7px;")
            elif lid_str in led_data:
                rgb = led_data[lid_str]
                btn.setStyleSheet(f"background-color: rgb({rgb[0]},{rgb[1]},{rgb[2]}); color: white; font-size: 7px;")
            else:
                btn.setStyleSheet("background-color: #222; color: #888; font-size: 7px;")

    def set_selected_color(self):
        if not self.selected_leds:
            QMessageBox.warning(self, "Warning", "No keys selected.")
            return
        
        curr_anim = self.anim_list.currentItem()
        curr_frame_idx = self.frame_list.currentRow()
        if not (curr_anim and curr_frame_idx >= 0): return
        
        color = QColorDialog.getColor()
        if color.isValid():
            name = curr_anim.text()
            rgb = [color.red(), color.green(), color.blue()]
            led_data = self.animations[name][curr_frame_idx].get("leds", {})
            for lid in self.selected_leds:
                led_data[str(lid)] = rgb
            self.animations[name][curr_frame_idx]["leds"] = led_data
            self.clear_selection()

    def set_all_color(self):
        curr_anim = self.anim_list.currentItem()
        curr_frame_idx = self.frame_list.currentRow()
        if not (curr_anim and curr_frame_idx >= 0): return
        
        color = QColorDialog.getColor()
        if color.isValid():
            name = curr_anim.text()
            rgb = [color.red(), color.green(), color.blue()]
            led_data = {str(lid): rgb for lid in self.key_buttons.keys()}
            self.animations[name][curr_frame_idx]["leds"] = led_data
            self.refresh_kb_visual()

    def load_frame(self, row):
        if row < 0: return
        curr_anim = self.anim_list.currentItem()
        if not curr_anim: return
        name = curr_anim.text()
        frame = self.animations[name][row]
        self.duration_spin.setValue(frame.get("duration", 0.1))
        self.selected_leds.clear()
        self.refresh_kb_visual()

    def update_frame_duration(self, val):
        curr_anim = self.anim_list.currentItem()
        curr_frame_idx = self.frame_list.currentRow()
        if curr_anim and curr_frame_idx >= 0:
            name = curr_anim.text()
            self.animations[name][curr_frame_idx]["duration"] = val

    def set_frame_color(self):
        curr_anim = self.anim_list.currentItem()
        curr_frame_idx = self.frame_list.currentRow()
        if not (curr_anim and curr_frame_idx >= 0): return
        
        color = QColorDialog.getColor()
        if color.isValid():
            name = curr_anim.text()
            # In this simplified version, we'll try to apply this color to ALL LEDs if possible
            # Or just store it as a special "all" key for now.
            # Realistically we should have a list of LED IDs.
            # Let's get LED IDs if SDK is available.
            led_ids = []
            if self.sdk:
                try:
                    devices = self.sdk.get_devices()
                    for dev in devices:
                        if dev.type == CorsairDeviceType.Keyboard:
                            positions = self.sdk.get_led_positions(dev.device_id)
                            led_ids.extend([p.led_id for p in positions])
                except:
                    pass
            
            # If no SDK or no IDs found, use some common keyboard IDs as fallback or just empty
            if not led_ids:
                # Fallback to some common Corsair LED IDs if we can't detect
                led_ids = list(range(1, 150)) # Rough range for keyboard LEDs

            rgb = [color.red(), color.green(), color.blue()]
            led_data = {str(lid): rgb for lid in led_ids}
            self.animations[name][curr_frame_idx]["leds"] = led_data
            QMessageBox.information(self, "Success", f"Set color for {len(led_ids)} LEDs in this frame.")

    def test_animation(self):
        curr_anim = self.anim_list.currentItem()
        if not curr_anim: return
        name = curr_anim.text()
        
        # Try to use parent's keysim if available, or just SDK
        parent = self.parent()
        keysim = getattr(parent, 'keysim_window', None)
        
        if not self.sdk and not (keysim and keysim.isVisible()):
            QMessageBox.warning(self, "Warning", "Neither iCUE SDK nor KeySim window is active. Cannot test.")
            return
        
        self.player = AnimationPlayer(self.animations[name], sdk=self.sdk, keysim=keysim)
        self.player.start()

class MixItUpWorker(QObject):
    log_signal = pyqtSignal(str)
    event_signal = pyqtSignal(str, str) # event_type, user_name
    finished_signal = pyqtSignal()
    
    def __init__(self, host, port, path="/api/v2/events"):
        super().__init__()
        self.host = host
        self.port = port
        self.path = path
        self.running = False

    async def run_mixitup(self):
        uri = f"ws://{self.host}:{self.port}{self.path}"
        self.log_signal.emit(f"Connecting to MixItUp at {uri}...")
        try:
            async with websockets.connect(uri) as websocket:
                self.log_signal.emit("Connected to MixItUp!")
                self.running = True
                while self.running:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)
                        
                        # Expected format based on typical MixItUp Event Notifications
                        # Usually it contains "Event" or "Type" and "User" details
                        event_type_raw = data.get("Type", data.get("Event", "unknown")).lower()
                        
                        # Map MixItUp events to our internal types
                        if "follow" in event_type_raw:
                            event_type = "follow"
                        elif "subscription" in event_type_raw:
                            event_type = "sub"
                        elif "resubscription" in event_type_raw:
                            event_type = "resub"
                        else:
                            event_type = event_type_raw

                        # Try to find user name in common locations
                        user_name = "Unknown"
                        user_data = data.get("User", {})
                        if isinstance(user_data, dict):
                            user_name = user_data.get("Username", user_data.get("DisplayName", "Unknown"))
                        elif isinstance(user_data, str):
                            user_name = user_data
                        
                        if event_type in ["follow", "sub", "resub"]:
                            self.log_signal.emit(f"Event Received: {event_type} from {user_name}")
                            self.event_signal.emit(event_type, user_name)
                        else:
                            self.log_signal.emit(f"Ignored Event: {event_type_raw}")

                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        self.log_signal.emit(f"Message Error: {str(e)}")
                        break
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg:
                self.log_signal.emit(f"Connection Error (404): The path '{self.path}' was not found. Please check if the Developer API is enabled in MixItUp and try a different path (like /api/v1/events).")
            else:
                self.log_signal.emit(f"MixItUp Connection Error: {error_msg}")
        finally:
            self.running = False
            self.finished_signal.emit()

    def stop(self):
        self.running = False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MixItUp v2 Event Trigger GUI")
        self.resize(800, 600)
        
        self.sdk = None
        self.keyboard_controller = None
        if SDK_AVAILABLE:
            try:
                self.keyboard_controller = Controller()
            except Exception as e:
                print(f"Failed to initialize pynput: {e}")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # MixItUp Connection Group
        conn_group = QGroupBox("MixItUp v2 Connection")
        conn_layout = QFormLayout()
        self.host_input = QLineEdit("localhost")
        self.port_input = QLineEdit("8911")
        
        conn_layout.addRow("IP Address / Host:", self.host_input)
        conn_layout.addRow("Port:", self.port_input)
        
        self.path_input = QComboBox()
        self.path_input.setEditable(True)
        self.path_input.addItems(["/api/v2/events", "/api/v1/events", "/api/events", "/events"])
        conn_layout.addRow("Base Path:", self.path_input)
        
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

        # iCUE SDK Group
        icue_group = QGroupBox("Corsair iCUE Integration")
        icue_layout = QHBoxLayout()
        self.icue_status_label = QLabel("Status: Not Connected")
        self.icue_connect_btn = QPushButton("Connect iCUE")
        self.icue_connect_btn.clicked.connect(self.connect_icue)
        self.icue_connect_btn.setEnabled(SDK_AVAILABLE)
        if not SDK_AVAILABLE:
            self.icue_status_label.setText("Status: SDK Not Installed (pip install cuesdk pynput)")
        
        icue_layout.addWidget(self.icue_status_label)
        icue_layout.addWidget(self.icue_connect_btn)
        icue_group.setLayout(icue_layout)
        layout.addWidget(icue_group)
        
        # Actions Group
        action_group = QGroupBox("Event Actions (Python Code)")
        action_layout = QFormLayout()
        self.follow_action = QLineEdit("print(f'{user} followed!')")
        self.sub_action = QLineEdit("print(f'{user} subscribed!')")
        self.resub_action = QLineEdit("print(f'{user} resubscribed!')")
        
        action_layout.addRow("Follow Action:", self.follow_action)
        action_layout.addRow("Sub Action:", self.sub_action)
        action_layout.addRow("Resub Action:", self.resub_action)
        action_group.setLayout(action_layout)
        layout.addWidget(action_group)
        
        # Control Buttons
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Listening")
        self.start_btn.clicked.connect(self.start_listening)
        self.stop_btn = QPushButton("Stop Listening")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_listening)
        self.anim_btn = QPushButton("Animation Editor")
        self.anim_btn.clicked.connect(self.open_animation_editor)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.anim_btn)
        layout.addLayout(btn_layout)
        
        # Log Window
        self.log_window = QTextEdit()
        self.log_window.setReadOnly(True)
        layout.addWidget(QLabel("Logs:"))
        layout.addWidget(self.log_window)
        
        self.worker = None
        self.worker_thread = None
        self.animations = self.load_animations()
        self.active_players = []
        
        self.keysim_window = KeySimWindow()
        self.keysim_btn = QPushButton("Show KeySim (Virtual Keyboard)")
        self.keysim_btn.clicked.connect(self.keysim_window.show)
        btn_layout.addWidget(self.keysim_btn)

    def load_animations(self):
        try:
            with open("animations.json", "r") as f:
                return json.load(f)
        except:
            return {}

    def save_animations(self):
        try:
            with open("animations.json", "w") as f:
                json.dump(self.animations, f)
        except Exception as e:
            self.log(f"Error saving animations: {e}")

    def open_animation_editor(self):
        dialog = AnimationEditorDialog(self.animations, SDK_AVAILABLE, self.sdk)
        dialog.exec()
        self.save_animations()

    def play_animation(self, name):
        if name in self.animations:
            # Play on SDK if connected, and always play on KeySim if it exists
            player = AnimationPlayer(self.animations[name], sdk=self.sdk, keysim=self.keysim_window)
            player.finished.connect(lambda: self.active_players.remove(player) if player in self.active_players else None)
            self.active_players.append(player)
            player.start()
            self.log(f"Playing animation: {name}")
        else:
            self.log(f"Animation '{name}' not found.")

    def connect_icue(self):
        if not SDK_AVAILABLE:
            return
        try:
            self.sdk = CUESDK()
            # Perform a basic check to see if we can connect
            details = self.sdk.get_session_details()
            if details.state == CorsairSessionState.Connected:
                self.log("Connected to iCUE SDK!")
                self.icue_status_label.setText("Status: Connected")
                self.icue_connect_btn.setEnabled(False)
            else:
                self.log(f"iCUE Session State: {details.state}. Ensure SDK is enabled in iCUE settings.")
                self.icue_status_label.setText(f"Status: {details.state}")
        except Exception as e:
            self.log(f"iCUE Connection Error: {str(e)}")
            self.icue_status_label.setText("Status: Error")

    def log(self, message):
        self.log_window.append(message)

    def handle_event(self, event_type, user_name):
        action_map = {
            "follow": self.follow_action.text(),
            "sub": self.sub_action.text(),
            "resub": self.resub_action.text()
        }
        code = action_map.get(event_type)
        if code:
            try:
                # Provide 'user', 'sdk', 'kb' and 'play_anim' to the exec context
                exec_globals = {
                    "user": user_name,
                    "sdk": self.sdk,
                    "kb": self.keyboard_controller,
                    "Key": Key if SDK_AVAILABLE else None,
                    "play_anim": self.play_animation
                }
                exec(code, exec_globals)
                self.log(f"Executed action for {event_type}")
            except Exception as e:
                self.log(f"Action Error ({event_type}): {str(e)}")

    def start_listening(self):
        host = self.host_input.text()
        port = self.port_input.text()
        path = self.path_input.currentText()
        
        if not host or not port or not path:
            self.log("Error: Please fill in connection details.")
            return
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        self.worker = MixItUpWorker(host, port, path)
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)
        
        self.worker.log_signal.connect(self.log)
        self.worker.event_signal.connect(self.handle_event)
        self.worker.finished_signal.connect(self.on_worker_finished)
        
        self.worker_thread.started.connect(lambda: asyncio.run(self.worker.run_mixitup()))
        self.worker_thread.start()

    def stop_listening(self):
        if self.worker:
            self.worker.stop()
        self.stop_btn.setEnabled(False)

    def on_worker_finished(self):
        self.log("Worker finished.")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
