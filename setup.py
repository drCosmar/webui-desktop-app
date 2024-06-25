from utils import Setup, os
from dotenv import load_dotenv, set_key
load_dotenv()

setup = Setup()

def create_symlinks(setup:Setup):
    setup.root.parent / "stablility-diffusion-"
    
LOGLEVEL = int(os.environ["WEBUI_LOGLEVEL"])
HEADLESS = os.environ["WEBUI_HEADLESS"]

if __name__ == "__main__":
    setup.run_prerequisites()
    from dotenv import load_dotenv
    load_dotenv()
    if not bool(os.environ["WEBUI_INSTALLATION_SUCCESS"]):
        cont = setup.webui_sh_first_run_conda()
        set_key(".env", "WEBUI_INSTALLATION_SUCCESS", "True")
    if cont:
        setup.main()
    if not cont:
        print("Conda first run failed, please check logs and try again.")