import sys
import asyncio
import json
import time
import aiohttp
from aiohttp import web
try:
    from cuesdk import CorsairSessionState, CorsairDevicePropertyId, CorsairDataType, CorsairDeviceType, CorsairError, CorsairLedColor, CUESDK
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

class CodeExecutor(QThread):
    log_signal = pyqtSignal(str)
    
    def __init__(self, code, context):
        super().__init__()
        self.code = code
        self.context = context

    def run(self):
        try:
            exec(self.code, self.context)
            self.log_signal.emit(f"Executed action successfully")
        except Exception as e:
            self.log_signal.emit(f"Action Execution Error: {str(e)}")

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

class WebhookWorker(QObject):
    log_signal = pyqtSignal(str)
    event_signal = pyqtSignal(str, str) # event_type, user_name
    finished_signal = pyqtSignal()

    def __init__(self, host="0.0.0.0", port=8080):
        super().__init__()
        self.host = host
        self.port = port
        self.running = False
        self.runner = None

    async def handle_post(self, request):
        try:
            # Try to get event_type from URL path first
            event_type = request.match_info.get('event_type')
            user_name = "Unknown"

            # Check if it's a JSON request
            if request.content_type == 'application/json':
                try:
                    data = await request.json()
                    if not event_type:
                        event_type = data.get("event")
                    user_name = data.get("user", "Unknown")
                except:
                    pass
            
            # If still no event_type, check for form data
            if not event_type and request.content_type == 'application/x-www-form-urlencoded':
                try:
                    data = await request.post()
                    event_type = data.get("event")
                    user_name = data.get("user", "Unknown")
                except:
                    pass

            # If still no user_name, maybe it's just plain text in the body?
            if user_name == "Unknown":
                try:
                    text = await request.text()
                    if text:
                        user_name = text.strip()
                except:
                    pass

            if not event_type:
                event_type = "custom_event"

            self.log_signal.emit(f"Webhook Received: {event_type} from {user_name}")
            self.event_signal.emit(event_type, user_name)
            return web.Response(text="OK")
        except Exception as e:
            self.log_signal.emit(f"Webhook Error: {str(e)}")
            return web.Response(text=f"Error: {str(e)}", status=400)

    async def run_server(self):
        self.running = True
        app = web.Application()
        # Support both root POST and specific event POST
        app.router.add_post("/", self.handle_post)
        app.router.add_post("/event/{event_type}", self.handle_post)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        self.log_signal.emit(f"Starting Webhook Server on http://{self.host}:{self.port}/")
        try:
            await site.start()
            while self.running:
                await asyncio.sleep(1)
        except Exception as e:
            self.log_signal.emit(f"Server Error: {str(e)}")
        finally:
            await self.runner.cleanup()
            self.running = False
            self.finished_signal.emit()

    def run_server_sync(self):
        asyncio.run(self.run_server())

    def stop(self):
        self.running = False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RGB Studio - Webhook Event Trigger")
        self.resize(800, 600)
        
        self.sdk = None

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Webhook Server Group (Moved up as it's now primary)
        webhook_group = QGroupBox("Webhook Server Configuration")
        webhook_layout = QFormLayout()
        self.webhook_host = QLineEdit("0.0.0.0")
        self.webhook_port = QLineEdit("8080")
        webhook_layout.addRow("Host (0.0.0.0 for all):", self.webhook_host)
        webhook_layout.addRow("Port:", self.webhook_port)
        webhook_group.setLayout(webhook_layout)
        layout.addWidget(webhook_group)

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
        action_group = QGroupBox("Standard Event Actions (Python Code)")
        action_layout = QFormLayout()
        self.follow_action = QLineEdit("play_anim('test'); print(f'{user} followed!')")
        self.sub_action = QLineEdit("play_anim('test'); print(f'{user} subscribed!')")
        self.resub_action = QLineEdit("play_anim('test'); print(f'{user} resubscribed!')")
        
        action_layout.addRow("Follow Action:", self.follow_action)
        action_layout.addRow("Sub Action:", self.sub_action)
        action_layout.addRow("Resub Action:", self.resub_action)
        action_group.setLayout(action_layout)
        layout.addWidget(action_group)
        
        # Control Buttons
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Server")
        self.start_btn.clicked.connect(self.start_listening)
        self.stop_btn = QPushButton("Stop Server")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_listening)
        self.anim_btn = QPushButton("Animation Editor")
        self.anim_btn.clicked.connect(self.open_animation_editor)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.anim_btn)
        layout.addLayout(btn_layout)
        
        # Custom Events Group
        custom_group = QGroupBox("Custom Events (URL: /event/{name})")
        custom_layout = QVBoxLayout()
        self.custom_events_list = QListWidget()
        self.custom_events = self.load_custom_events()
        for ev_name in self.custom_events:
            self.custom_events_list.addItem(ev_name)
        self.custom_events_list.currentRowChanged.connect(self.load_custom_event_code)
        
        custom_layout.addWidget(QLabel("Event Name:"))
        self.custom_event_name = QLineEdit()
        custom_layout.addWidget(self.custom_event_name)
        custom_layout.addWidget(QLabel("Action (Python Code):"))
        self.custom_event_code = QTextEdit()
        self.custom_event_code.setPlaceholderText("print(f'Custom event {user}!')")
        custom_layout.addWidget(self.custom_event_code)
        
        custom_btn_layout = QHBoxLayout()
        save_custom_btn = QPushButton("Save/Add Custom Event")
        save_custom_btn.clicked.connect(self.save_custom_event)
        del_custom_btn = QPushButton("Delete Custom Event")
        del_custom_btn.clicked.connect(self.delete_custom_event)
        custom_btn_layout.addWidget(save_custom_btn)
        custom_btn_layout.addWidget(del_custom_btn)
        custom_layout.addLayout(custom_btn_layout)
        
        custom_group.setLayout(custom_layout)
        layout.addWidget(custom_group)
        
        # Log Window
        self.log_window = QTextEdit()
        self.log_window.setReadOnly(True)
        layout.addWidget(QLabel("Logs:"))
        layout.addWidget(self.log_window)
        
        self.worker = None
        self.worker_thread = None
        self.animations = self.load_animations()
        self.active_players = []
        self.active_executors = []
        
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

    def load_custom_events(self):
        try:
            with open("custom_events.json", "r") as f:
                return json.load(f)
        except:
            return {}

    def save_custom_event(self):
        name = self.custom_event_name.text().strip()
        code = self.custom_event_code.toPlainText()
        if name:
            self.custom_events[name] = code
            if not self.custom_events_list.findItems(name, Qt.MatchFlag.MatchExactly):
                self.custom_events_list.addItem(name)
            try:
                with open("custom_events.json", "w") as f:
                    json.dump(self.custom_events, f)
                self.log(f"Saved custom event: {name}")
            except Exception as e:
                self.log(f"Error saving custom events: {e}")

    def delete_custom_event(self):
        curr = self.custom_events_list.currentItem()
        if curr:
            name = curr.text()
            if name in self.custom_events:
                del self.custom_events[name]
                self.custom_events_list.takeItem(self.custom_events_list.row(curr))
                try:
                    with open("custom_events.json", "w") as f:
                        json.dump(self.custom_events, f)
                    self.log(f"Deleted custom event: {name}")
                except Exception as e:
                    self.log(f"Error saving custom events: {e}")

    def load_custom_event_code(self, row):
        if row < 0: return
        name = self.custom_events_list.item(row).text()
        self.custom_event_name.setText(name)
        self.custom_event_code.setText(self.custom_events.get(name, ""))

    def handle_event(self, event_type, user_name):
        action_map = {
            "follow": self.follow_action.text(),
            "sub": self.sub_action.text(),
            "resub": self.resub_action.text()
        }
        # Check standard events first, then custom events
        code = action_map.get(event_type)
        if not code:
            code = self.custom_events.get(event_type)
        
        if code:
            # Provide 'user', 'sdk' and 'play_anim' to the exec context
            exec_globals = {
                "user": user_name,
                "sdk": self.sdk,
                "play_anim": self.play_animation
            }
            
            executor = CodeExecutor(code, exec_globals)
            executor.log_signal.connect(lambda msg: self.log(f"[{event_type}] {msg}"))
            executor.finished.connect(lambda: self.active_executors.remove(executor) if executor in self.active_executors else None)
            self.active_executors.append(executor)
            executor.start()
            self.log(f"Starting execution for {event_type} event...")

    def start_listening(self):
        # Webhook Server Start
        w_host = self.webhook_host.text()
        try:
            w_port = int(self.webhook_port.text())
        except ValueError:
            self.log("Error: Invalid port number.")
            return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self.webhook_worker = WebhookWorker(w_host, w_port)
        self.webhook_thread = QThread()
        self.webhook_worker.moveToThread(self.webhook_thread)
        self.webhook_worker.log_signal.connect(self.log)
        self.webhook_worker.event_signal.connect(self.handle_event)
        self.webhook_worker.finished_signal.connect(self.on_worker_finished)
        self.webhook_thread.started.connect(self.webhook_worker.run_server_sync)
        self.webhook_thread.start()

    def stop_listening(self):
        if hasattr(self, 'webhook_worker') and self.webhook_worker:
            self.webhook_worker.stop()
        self.stop_btn.setEnabled(False)

    def on_worker_finished(self):
        self.log("Server stopped.")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if hasattr(self, 'webhook_thread') and self.webhook_thread:
            self.webhook_thread.quit()
            self.webhook_thread.wait()
            self.webhook_thread = None # Clean up

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
