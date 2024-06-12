from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction,\
    QVBoxLayout, QLabel, QPushButton, QDialog
from PyQt5.QtGui import QIcon
from dotenv import load_dotenv, set_key
from utils import Utils, to_strict_bool, os, sys, signal, subprocess,\
    logging, traceback
import time

load_dotenv()
LOGLEVEL = int(os.environ["WEBUI_LOGLEVEL"])
HEADLESS = to_strict_bool(os.environ["WEBUI_HEADLESS"])
HIDDEN = to_strict_bool(os.environ["WEBUI_HIDDEN"])

class Runner(Utils):
    def __init__(self, log_lvl=10):
        super().__init__(log_lvl)

        # Check for existing instance
        if self.is_running():
            print("Another instance is already running.")
            self.show_instance_running_dialog()
            sys.exit(1)

        # Create lock file
        self.create_lockfile()

        # Register cleanup handler
        signal.signal(signal.SIGTERM, self.cleanup)
        signal.signal(signal.SIGINT, self.cleanup)

    def is_running(self):
        return os.path.exists(self.webui_lock_fp)

    def create_lockfile(self):
        with open(self.webui_lock_fp, 'w') as f:
            f.write(str(os.getpid()))

    def cleanup(self, signum=None, frame=None):
        try:
            os.remove(self.webui_lock_fp)
        except FileNotFoundError:
            pass
        QApplication.instance().quit()
        sys.exit(0)

    def launch_webui(self, hidden=True, headless=False):
        parent_dir = self.root.parent
        webui_script = parent_dir / "webui.sh"
        command = [str(webui_script)]

        if os.name == 'posix':
            if os.environ.get("DESKTOP_SESSION") == "gnome":
                terminal = ['gnome-terminal', '--']
            elif os.environ.get("DESKTOP_SESSION") in ["kde", "plasma"]:
                terminal = ['konsole', '-e']
            else:
                terminal = ['xterm', '-e']

            if headless:
                command.append("--nowebui")

            if hidden:
                log_file_path = None
                for handler in self.log.handlers:
                    if isinstance(handler, logging.handlers.RotatingFileHandler):
                        log_file_path = handler.baseFilename
                        break

                if log_file_path:
                    with open(log_file_path, "a") as log_file:
                        proc = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT, preexec_fn=os.setsid)
                else:
                    self.log.warning("RotatingFileHandler not found for logging. Output will go to the console.")
                    proc = subprocess.Popen(command, preexec_fn=os.setsid)
            else:
                full_command = terminal + command
                proc = subprocess.Popen(full_command)
        else:
            self.log.error("Windows support is not yet implemented.")
            sys.exit(1)

        return proc.pid

    def close(self, pid):
        if isinstance(pid, str):
            pid = int(pid)
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            self.log.info("WebUI terminated.")
        except ProcessLookupError:
            self.log.error("WebUI process not found.")
        except Exception as e:
            self.log.error(f"Error closing WebUI: {e}\n\n{traceback.format_exc()}")

    def save_pid(self, pid, pid_fp):
        with open(pid_fp, 'w') as f:
            f.write(str(pid))

    def load_pid(self, pid_fp):
        try:
            with open(pid_fp, 'r') as f:
                return int(f.read())
        except FileNotFoundError:
            self.log.error("No PID file found.")
            return None

    def create_tray_icon(self, icon_path):
        app = QApplication(sys.argv)
        tray = QSystemTrayIcon(QIcon(str(icon_path)), app)

        tray.setToolTip(self.tooltip)

        menu = QMenu()
        exit_action = QAction("Exit")
        exit_action.triggered.connect(self.on_exit)
        menu.addAction(exit_action)

        tray.setContextMenu(menu)
        tray.show()

        sys.exit(app.exec_())
    
    def show_instance_running_dialog(self):
        app = QApplication(sys.argv)
        
        dialog = QDialog()
        dialog.setWindowTitle("Error:")

        layout = QVBoxLayout()
        label = QLabel("Instance already running!")
        layout.addWidget(label)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)

        dialog.setLayout(layout)
        dialog.exec_()

    def on_exit(self):
        pid = self.load_pid(self.webui_pid_fp)
        if pid is not None:
            self.close(pid)
        self.cleanup()

if __name__ == "__main__":
    run = Runner(LOGLEVEL)
    # Path to your icon file
    icon_path = run.icon  # Or use "path/to/your/icon.ico"

    # Launch the WebUI
    webui_pid = run.launch_webui(hidden=HIDDEN, headless=HEADLESS)
    run.save_pid(webui_pid, run.webui_pid_fp)

    tray_pid = os.getpid()
    run.save_pid(tray_pid, run.tray_pid_fp)

    # Start the system tray icon
    run.create_tray_icon(icon_path)