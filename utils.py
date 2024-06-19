import pathlib, subprocess, os, signal,\
sys, pathlib, logging, shutil, stat, json, traceback
from logging.handlers import RotatingFileHandler

def to_strict_bool(value):
  if not isinstance(value, str):
    raise TypeError("Input value must be a string")
  return value.lower() == "true"

class Utils:
    logging_configured = False
    def __init__(self, log_lvl=10):
        self.root = pathlib.Path(__file__).parent.resolve()
        self.webui_sh_fp = self.root.parent
        self.icon = self.root / "icon" / "icon.png"
        self.tooltip = "WebUI Server"
        self.webui_pid_fp =  "/tmp/webui.pid"
        self.tray_pid_fp = "/tmp/webui_tray.pid"
        self.webui_lock_fp = "webui.lock"
        self.log_fp = self.root.parent / "webui.log"
        if not Utils.logging_configured:
            self.log = logging.getLogger(__name__)
            logging.basicConfig(level=log_lvl, format='%(asctime)s - %(levelname)s - %(message)s',
                                datefmt='%m/%d/%Y %I:%M:%S %p', filemode="a", filename=self.log_fp)
            self.log.addHandler(logging.StreamHandler())
            self.log.addHandler(RotatingFileHandler(self.root / self.log_fp, maxBytes=500000, backupCount=2))
            Utils.logging_configured = True

    def get_log_file_path(self, log):
        for handler in self.log.handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                return handler.baseFilename
        return None

    def run_command_with_logging(self, command:str, log:logging):
        log_file_path = self.get_log_file_path(log)
        requires_sudo = command.split(" ")[0].strip() == 'sudo'

        try:
            if log_file_path:
                with open(log_file_path, "a") as log_file:
                    stream_handler = None
                    for handler in log.handlers:
                        if isinstance(handler, logging.StreamHandler):
                            stream_handler = handler
                            log.removeHandler(handler)
                            break
                    if requires_sudo:
                        command = command.split(" ")
                        proc = subprocess.Popen(command, stdout=log_file, stderr=subprocess.PIPE)
                        stdout, stderr = proc.communicate()  # Wait for the command to complete
                        result = proc.returncode
                    else:
                        completed_process = subprocess.run(command, stdout=log_file, stderr=subprocess.PIPE, shell=True)
                        result = completed_process.returncode
                    if stream_handler:
                        log.addHandler(stream_handler)
                    if isinstance(command, list):
                        cmd = " ".join(command)
                    else:
                        cmd = command
                    log.info(f"Running command: {cmd}")
                    if result != 0:
                        log.error(f"Command failed with return code {result}")
                        log.error(stderr.decode('utf-8') if requires_sudo else completed_process.stderr.decode('utf-8'))
                    else:
                        log.info(f"Command executed successfully.")
            else:
                log.warning("RotatingFileHandler not found for logging. Output will go to the console.")
                if requires_sudo:
                    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                    stdout, stderr = proc.communicate()  # Wait for the command to complete
                    result = proc.returncode
                else:
                    completed_process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                    result = completed_process.returncode
                if isinstance(command, list):
                    cmd = " ".join(command)
                else:
                    cmd = command
                log.info(f"Running command: {cmd}")
                if result != 0:
                    log.error(f"Command failed with return code {result}")
                    log.error(stderr.decode('utf-8') if requires_sudo else completed_process.stderr.decode('utf-8'))
                else:
                    log.info(f"Command executed successfully: {stdout.decode('utf-8') if requires_sudo else completed_process.stdout.decode('utf-8')}")
        except Exception as e:
            if isinstance(command, list):
                cmd = " ".join(command)
            else:
                cmd = command
            log.error(f"An unknown error occurred while running command {cmd}: {str(e)}\n{traceback.format_exc()}")
        return result

    def get_conda_conda_path(self):
        try:
            conda_prefix = os.environ.get("CONDA_PREFIX")
            if conda_prefix:
                conda_path = os.path.join(conda_prefix, "bin", "conda")
            if os.path.isfile(conda_path):
                return conda_path

            output = subprocess.check_output(["conda", "info", "--json"]).decode("utf-8")
            info = json.loads(output)
            return info.get("conda_prefix") + "/bin/conda"
        except (subprocess.CalledProcessError, KeyError):
            return None

    def get_conda_activate_path(self):
        try:
            conda_prefix = os.environ.get("CONDA_PREFIX")
            if conda_prefix:
                activate_path = os.path.join(conda_prefix, "bin", "activate")
                if os.path.isfile(activate_path):
                    return activate_path

            output = subprocess.check_output(["conda", "info", "--json"]).decode("utf-8")
            info = json.loads(output)
            return info.get("conda_prefix") + "/bin/activate"
        except (subprocess.CalledProcessError, KeyError):
            return None
        
    def detect_conda_environment(self):
        conda_env = os.environ.get("CONDA_DEFAULT_ENV")
        if conda_env:
            return conda_env
        else:
            return None

    def detect_desktop_environment(self):
        try:
            de_info = subprocess.check_output(["xprop", "-root", "_NET_SUPPORTED"], text=True)
            if "KDE" in de_info:
                de = "KDE"
            else:
                de = "GNOME"
        except subprocess.CalledProcessError:
            de = "GNOME"
        return de

    def detect_gpu_type(self):
        try:
            subprocess.check_output(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], universal_newlines=True)
            return "NVIDIA"
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        rocm_smi_path = "/opt/rocm/bin/rocm-smi"  

        if shutil.which(self, rocm_smi_path):
            try:
                subprocess.check_output([rocm_smi_path, "--showid"], universal_newlines=True)
                return "AMD"
            except subprocess.CalledProcessError:
                pass
        return None

    def linux_commands_by_distro(self):
        if os.path.exists("/etc/debian_version"):
            return ["sudo apt install wget git python3 python3-venv libgl1 libglib2.0-0", "wget -P .. -q https://raw.githubusercontent.com/AUTOMATIC1111/stable-diffusion-webui/master/webui.sh"]
        elif os.path.exists("/etc/redhat-release") or os.path.exists("/etc/centos-release") or os.path.exists("/etc/fedora-release"):
            return ["sudo dnf install wget git python3 gperftools-libs libglvnd-glx", "wget -P .. -q https://raw.githubusercontent.com/AUTOMATIC1111/stable-diffusion-webui/master/webui.sh"] 
        elif os.path.exists("/etc/SuSE-release") or os.path.exists("/etc/os-release"):
            with open("/etc/os-release", "r") as f:
                if "opensuse" in f.read().lower():
                    return ["sudo zypper install wget git python3 libtcmalloc4 libglvnd", "wget -P .. -q https://raw.githubusercontent.com/AUTOMATIC1111/stable-diffusion-webui/master/webui.sh"]
        elif os.path.exists("/etc/arch-release"):
            return ["sudo pacman -S wget git python3", "wget -P .. -q https://raw.githubusercontent.com/AUTOMATIC1111/stable-diffusion-webui/master/webui.sh"]
        else:
            return None

    def terminal_divider(self, char="#"):
        print(char * os.get_terminal_size().columns)
        print(char * os.get_terminal_size().columns)
        
    def is_conda_installed(self):
        try:
            subprocess.run(['conda', '--version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
        
    def is_conda_environment_AUTO1111_present(self):
        try:
            result = subprocess.run(['conda', 'env', 'list'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output = result.stdout.decode('utf-8')
            env_list = [line.split()[0] for line in output.splitlines() if line and not line.startswith('#')]
            if "AUTO1111" in env_list:
                return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
        
    def append_and_cleanup_log(self):
        with open(self.root / "<Logger utils (DEBUG)>", "r") as f:
            lines = f.readlines()
            for line in lines:
                with open(self.webui_sh_fp / "webui.log", "a") as f:
                    if len(line.strip()) > 2:
                        if "%" in line.strip()[1:3] and line.strip()[0] != 1:
                            continue
                    f.writelines(line.strip() + "\n")
                   
        
        pathlib.Path(self.root / "<Logger utils (DEBUG)>").unlink()
        
class Setup(Utils):
    def __init__(self, log_lvl=10):
        super().__init__(log_lvl)
        self.conda_env = self.detect_conda_environment()

    def run_prerequisites(self):
        commands = self.linux_commands_by_distro()
        if self.is_conda_installed():
            if not self.is_conda_environment_AUTO1111_present():
                commands.insert(0, "conda create --name AUTO1111 python=3.10.6 -y")
                commands.insert(0, "conda clean --all -y")
                commands.insert(0, "pip cache purge")
            else:
                commands.insert(0, "conda clean --all -y")
                commands.insert(0, "pip cache purge")
        else:
            self.log.critical("Conda is not installed. Please setup anaconda3, or miniconda, and try again.")
            raise Exception("Conda is not installed. Please setup anaconda3, or miniconda, and try again.")
        for command in commands:
            try:
                result = self.run_command_with_logging(command, self.log)
            except Exception as e:
                self.log.error(f"An unknown error occurred while running command {' '.join(command)}: {str(e)}\n{traceback.format_exc()}")
        return result
    
    def webui_sh_first_run_conda(self):
        webui_sh_path = pathlib.Path(self.root.parent, "webui.sh")
        webui_sh_path.chmod(webui_sh_path.stat().st_mode | stat.S_IEXEC)
        activate_path = self.get_conda_activate_path()

        installs = [
            f"conda run -n AUTO1111 pip install -r requirements.txt",
            f"source {activate_path} AUTO1111 && exec bash -c '\"../webui.sh\" 2>&1 | tee \"{self.log}\"'"
        ]

        self.terminal_divider()
        print("Wait for webui.sh to finish installing, and the browser page to load. Then cntrl+c to close the webui.sh terminal.")
        self.terminal_divider()
        for install in installs:
            if install.endswith(f"\",,/webui.sh\" 2>&1 | tee \"{self.log}\"'"):
                if os.environ.get("DESKTOP_SESSION") == "gnome":
                    terminal = ['gnome-terminal', '--', 'bash', '-c']
                elif os.environ.get("DESKTOP_SESSION") in ["kde", "plasma"]:
                    terminal = ['konsole', '-e', 'bash', '-c']
                else:
                    terminal = ['xterm', '-hold', '-e', 'bash', '-c']
                command = terminal + [install]
            else:
                command = ["bash", "-c", install]
            proc = subprocess.Popen(command)
            proc_status = proc.wait()
            if proc_status == 0 and install != installs[0]:
                self.append_and_cleanup_log()
        self.terminal_divider("+")
        errors = input("Where there any errors that you need to fix when running webui.sh?\n###Y/N:")
        self.terminal_divider()
        if errors.lower() == "y":
            print("\n")
            print("If you need to start this script again, it's advised to delete the following folder\
and bash script:\n'stable-diffusion-webui'\n'webui.sh'\
\nMake sure you also remove the environment 'AUTO1111' if necessary.\
you can do this by running 'conda env remove AUTO1111'")
            self.terminal_divider()
        if errors.lower() == "n":
            self.log.info("WebUI.sh has been succesfully installed. Now moving creating symlinks for easier file management.")
            
    #pyenv version still under development.      
    def webui_sh_first_run_pyenv(self):
        venv_path = self.root / "webui-desktop-app" / "AUTO1111"  # Set this to your actual venv path
        venv_name = "AUTO1111"
        script_path = "../webui.sh"

        # Create and activate the virtual environment
        activate_path = os.path.join(venv_path, venv_name, "bin", "activate")
        create_env_command = f"python -m venv {os.path.join(venv_path, venv_name)}"
        activate_env_command = f"source {activate_path}"

        subprocess.run(create_env_command, shell=True)
        activate_env_proc = subprocess.Popen(f"source {activate_path} && pip install -r requirements.txt", shell=True)
        activate_env_proc.wait()

        # Commands to run webui.sh
        commands = [
            f"{activate_env_command} && exec bash -c '{script_path} | tee -a {self.log}'"
        ]

        # Execute commands in a new terminal
        for command in commands:
            if command.endswith(f"'{script_path} | tee -a {self.log}'"):
                if os.environ.get("DESKTOP_SESSION") == "gnome":
                    terminal = ['gnome-terminal', '--', 'bash', '-c']
                elif os.environ.get("DESKTOP_SESSION") in ["kde", "plasma"]:
                    terminal = ['konsole', '-e', 'bash', '-c']
                else:
                    terminal = ['xterm', '-hold', '-e', 'bash', '-c']
                command = terminal + [command]
            else:
                command = ["bash", "-c", command]

            proc = subprocess.Popen(command)
            proc.wait()
        ## Printout logic needed to guide users.
        ## logging and appending to log file needed.
        #symlinks are next
    # Under development. May be scrapped.
    def create_systemd_entry(self, script_path, systemd_path):
        if self.conda_env:
            exec_command = f'source activate {self.conda_env} && python3 {script_path}'
        else:
            exec_command = f'python3 {script_path}'
        
        systemd_entry_content = f"""
[Unit]
Description=WebUI Server
After=network.target

[Service]
Type=simple
User={os.environ["USER"]}
WorkingDirectory={self.root}
ExecStart=/bin/bash -lc "{exec_command}"
Restart=on-failure

[Install]
WantedBy=multi-user.target
"""
        with open(systemd_path, 'w') as f:
            f.write(systemd_entry_content.strip())

    def create_desktop_entry(self, wrapper_path, icon_path, desktop_file_path):
        desktop_environment = self.detect_desktop_environment()
        desktop_entry_content = f"""
[Desktop Entry]
Categories={desktop_environment};Utilities;
Name=WebUI Server
Comment[en_US]=Launch WebUI Server
Exec={wrapper_path}
Icon={icon_path}
Terminal=false
Type=Application
StartupNotify=true
"""
        if desktop_environment == "KDE":
            desktop_entry_content += """
X-KDE-Env=VAR1=value1;VAR2=value2;  # Customize these if needed
"""

        with open(desktop_file_path, 'w') as f:
            f.write(desktop_entry_content.strip())

    def add_desktop_file_to_kde(self, desktop_file_path):
        subprocess.run(["kbuildsycoca5", "--noincremental"], check=True, cwd=str(pathlib.Path(desktop_file_path).parent))

    def create_wrapper_file(self, script_file, wrapper_file_path):
        conda_active_path = self.get_conda_activate_path()
        wrapper_content = f"""
#!/bin/bash
echo "$(date) - WebUI Server started" >> /tmp/webui_server.log
source {conda_active_path}
conda activate {self.conda_env}
cd {self.root}
python3 {script_file} >> /tmp/webui_server.log 2>&1
"""
        with open(wrapper_file_path, "w") as f:
            f.write(wrapper_content.strip())

    def main(self):
        app_name = "webui-server"
        desktop_file = f"{app_name}.desktop"
        icon_file = "icon.png"
        script_file = "webui_server.py"

        home_dir = pathlib.Path.home()
        app_dir = home_dir / ".local" / "share" / "applications"
        icon_dir = home_dir / ".local" / "share" / "icons"

        app_dir.mkdir(parents=True, exist_ok=True)
        icon_dir.mkdir(parents=True, exist_ok=True)

        script_dir = self.root 
        wrapper_path = app_dir / "webui-server-wrapper.sh"
        icon_file_src = script_dir / "icon" / icon_file

        desktop_file_dst = app_dir / desktop_file
        icon_file_dst = icon_dir / icon_file
        wrapper_file_dst = app_dir / "webui-server-wrapper.sh"

        self.create_desktop_entry(wrapper_path, icon_file_dst, desktop_file_dst)
        self.add_desktop_file_to_kde(desktop_file_dst)
        self.create_wrapper_file(script_file, wrapper_file_dst)

        shutil.copy(icon_file_src, icon_file_dst)

        desktop_file_dst.chmod(desktop_file_dst.stat().st_mode | stat.S_IEXEC)
        desktop_file_dst.chmod(wrapper_file_dst.stat().st_mode | stat.S_IEXEC)

        self.log.info(f"Installed {desktop_file} to {app_dir}")
        self.log.info(f"Installed {icon_file} to {icon_dir}")
