import inspect
import itertools
import os
import sys
import threading
import time
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional, List

from invoke import task, Context

DAEMON_DIR: str = "daemon"
DEFAULT_PREFIX: str = "/usr/local"
OSPFMDR_CHECKOUT: str = "63f07596268873aeff86f252cbc27901369ad50a"
REDHAT_LIKE = {
    "redhat",
    "fedora",
}
DEBIAN_LIKE = {
    "ubuntu",
    "debian",
}
SUDOP: str = "sudo -E env PATH=$PATH"
VENV_PATH: str = "/opt/core/venv"
VENV_PYTHON: str = f"{VENV_PATH}/bin/python"
ACTIVATE_VENV: str = f". {VENV_PATH}/bin/activate"
HOME_PATH: str = f"{Path.home()}"


class Progress:
    cycles = itertools.cycle(["-", "/", "|", "\\"])

    def __init__(self, verbose: bool) -> None:
        self.verbose: bool = verbose
        self.thread: Optional[threading.Thread] = None
        self.running: bool = False

    @contextmanager
    def start(self, message: str) -> None:
        if not self.verbose:
            print(f"{message} ... ", end="")
            self.running = True
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()
        yield
        self.stop()

    def run(self) -> None:
        while self.running:
            sys.stdout.write(next(self.cycles))
            sys.stdout.flush()
            sys.stdout.write("\b")
            time.sleep(0.1)

    def stop(self) -> None:
        if not self.verbose:
            print("done")
        if self.thread:
            self.running = False
            self.thread.join()
            self.thread = None


class OsName(Enum):
    UBUNTU = "ubuntu"
    CENTOS = "centos"
    UNKNOWN = "unknown"

    @classmethod
    def get(cls, name: str) -> "OsName":
        try:
            return OsName(name)
        except ValueError:
            return OsName.UNKNOWN


class OsLike(Enum):
    DEBIAN = "debian"
    REDHAT = "rhel"

    @classmethod
    def get(cls, values: List[str]) -> Optional["OsLike"]:
        for value in values:
            if value in DEBIAN_LIKE:
                return OsLike.DEBIAN
            elif value in REDHAT_LIKE:
                return OsLike.REDHAT
        return None


class OsInfo:
    def __init__(self, name: OsName, like: OsLike, version: float) -> None:
        self.name: OsName = name
        self.like: OsLike = like
        self.version: float = version

    @classmethod
    def get(cls, name: str, like: List[str], version: Optional[str]) -> "OsInfo":
        os_name = OsName.get(name)
        os_like = OsLike.get(like)
        if not os_like:
            like = " ".join(like)
            print(f"unsupported os install type({like})")
            print("trying using the -i option to specify an install type")
            sys.exit(1)
        if version:
            try:
                version = float(version)
            except ValueError:
                print(f"os version is not a float: {version}")
                sys.exit(1)
        return OsInfo(os_name, os_like, version)


def get_env_python() -> str:
    return os.environ.get("PYTHON", "python3")


def get_env_python_dep() -> str:
    return os.environ.get("PYTHON_DEP", "python3")


def get_pytest(c: Context) -> str:
    with c.cd(DAEMON_DIR):
        venv = c.run("poetry env info -p", hide=True).stdout.strip()
        return os.path.join(venv, "bin", "pytest")


def get_os(install_type: Optional[str]) -> OsInfo:
    if install_type:
        name_value = OsName.UNKNOWN.value
        like_value = install_type
        version_value = None
    else:
        d = {}
        with open("/etc/os-release", "r") as f:
            for line in f.readlines():
                line = line.strip()
                if not line:
                    continue
                key, value = line.split("=")
                d[key] = value.strip("\"")
        name_value = d["ID"]
        like_value = d.get("ID_LIKE", "")
        version_value = d["VERSION_ID"]
    return OsInfo.get(name_value, like_value.split(), version_value)


def check_existing_core(c: Context, hide: bool) -> None:
    if c.run("python -c \"import core\"", warn=True, hide=hide):
        raise SystemError("existing python core installation detected, please remove")
    python_bin = get_env_python()
    if c.run(f"{python_bin} -c \"import core\"", warn=True, hide=hide):
        raise SystemError(
            f"existing {python_bin} core installation detected, please remove"
        )
    if c.run("which core-daemon", warn=True, hide=hide):
        raise SystemError("core scripts found, please remove old installation")


def install_system(c: Context, os_info: OsInfo, hide: bool, no_python: bool) -> None:
    python_dep = get_env_python_dep()
    if os_info.like == OsLike.DEBIAN:
        c.run(
            "sudo apt install -y automake pkg-config gcc libev-dev nftables "
            f"iproute2 ethtool tk bash",
            hide=hide
        )
        if not no_python:
            c.run(f"sudo apt install -y {python_dep}-tk", hide=hide)
    elif os_info.like == OsLike.REDHAT:
        c.run(
            "sudo yum install -y automake pkgconf-pkg-config gcc gcc-c++ "
            f"libev-devel nftables iproute tk ethtool make bash",
            hide=hide,
        )
        if not no_python:
            c.run(
                f"sudo yum install -y {python_dep}-devel {python_dep}-tkinter ",
                hide=hide,
            )
        # centos 8+ does not support netem by default
        if os_info.name == OsName.CENTOS and os_info.version >= 8:
            c.run("sudo yum install -y kernel-modules-extra", hide=hide)
            if not c.run("sudo modprobe sch_netem", warn=True, hide=hide):
                print("\nERROR: you need to install the latest kernel")
                print("run the following, restart, and try again")
                print("sudo yum update")
                sys.exit(1)


def install_grpcio(c: Context, hide: bool) -> None:
    python_bin = get_env_python()
    c.run(
        f"{python_bin} -m pip install --user grpcio==1.49.1 grpcio-tools==1.49.1",
        hide=hide,
    )


def build_core(c: Context, hide: bool, prefix: str = DEFAULT_PREFIX) -> None:
    c.run("./bootstrap.sh", hide=hide)
    c.run(f"./configure --prefix={prefix}", hide=hide)
    c.run("make -j$(nproc)", hide=hide)


def install_core(c: Context, hide: bool) -> None:
    c.run("sudo make install", hide=hide)


def install_poetry(c: Context, dev: bool, local: bool, hide: bool) -> None:
    python_bin = get_env_python()
    if local:
        with c.cd(DAEMON_DIR):
            c.run("poetry build -f wheel", hide=hide)
        c.run(f"sudo {python_bin} -m pip install dist/*")
    else:
        args = "" if dev else "--only main"
        with c.cd(DAEMON_DIR):
            c.run("sudo mkdir -p /opt/core", hide=hide)
            c.run(f"sudo {python_bin} -m venv {VENV_PATH}")
            c.run(f"{ACTIVATE_VENV} && {SUDOP} poetry install {args}", hide=hide)
            if dev:
                c.run(f"{ACTIVATE_VENV} && poetry run pre-commit install", hide=hide)


def install_ospf_mdr(c: Context, os_info: OsInfo, hide: bool) -> None:
    if c.run("sudo which zebra", warn=True, hide=hide):
        print("\nquagga already installed, skipping ospf mdr")
        return
    if os_info.like == OsLike.DEBIAN:
        c.run("sudo apt install -y libtool gawk libreadline-dev git", hide=hide)
    elif os_info.like == OsLike.REDHAT:
        c.run("sudo yum install -y libtool gawk readline-devel git", hide=hide)
    ospf_dir = "../ospf-mdr"
    ospf_url = "https://github.com/USNavalResearchLaboratory/ospf-mdr.git"
    c.run(f"git clone {ospf_url} {ospf_dir}", hide=hide)
    with c.cd(ospf_dir):
        c.run(f"git checkout {OSPFMDR_CHECKOUT}", hide=hide)
        c.run("./bootstrap.sh", hide=hide)
        c.run(
            "./configure --disable-doc --enable-user=root --enable-group=root "
            "--with-cflags=-ggdb --sysconfdir=/usr/local/etc/quagga --enable-vtysh "
            "--localstatedir=/var/run/quagga",
            hide=hide
        )
        c.run("make -j$(nproc)", hide=hide)
        c.run("sudo make install", hide=hide)


def install_service(c, verbose=False, prefix=DEFAULT_PREFIX):
    """
    install systemd core service
    """
    hide = not verbose
    bin_dir = Path(prefix).joinpath("bin")
    systemd_dir = Path("/lib/systemd/system/")
    service_file = systemd_dir.joinpath("core-daemon.service")
    if systemd_dir.exists():
        service_data = inspect.cleandoc(f"""
            [Unit]
            Description=Common Open Research Emulator Service
            After=network.target

            [Service]
            Type=simple
            ExecStart={bin_dir}/core-daemon
            TasksMax=infinity

            [Install]
            WantedBy=multi-user.target
            """)
        temp = NamedTemporaryFile("w", delete=False)
        temp.write(service_data)
        temp.close()
        c.run(f"sudo cp {temp.name} {service_file}", hide=hide)
        c.run(f"sudo systemctl start core-daemon.service", hide=hide)
        c.run(f"sudo systemctl enable core-daemon.service", hide=hide)
    else:
        print(f"ERROR: systemd service path not found: {systemd_dir}")


def install_core_files(c, local=False, verbose=False, prefix=DEFAULT_PREFIX):
    """
    install core files (scripts, examples, and configuration)
    """
    hide = not verbose
    bin_dir = Path(prefix).joinpath("bin")
    # setup core python helper
    if not local:
        core_python = bin_dir.joinpath("core-python")
        temp = NamedTemporaryFile("w", delete=False)
        temp.writelines([
            "#!/bin/bash\n",
            f'exec "{VENV_PYTHON}" "$@"\n',
        ])
        temp.close()
        c.run(f"sudo cp {temp.name} {core_python}", hide=hide)
        c.run(f"sudo chmod 755 {core_python}", hide=hide)
        os.unlink(temp.name)
    # install core configuration file
    config_dir = "/etc/core"
    c.run(f"sudo mkdir -p {config_dir}", hide=hide)
    c.run(f"sudo cp -n package/etc/core.conf {config_dir}", hide=hide)
    c.run(f"sudo cp -n package/etc/logging.conf {config_dir}", hide=hide)
    # install examples
    examples_dir = f"{prefix}/share/core"
    c.run(f"sudo mkdir -p {examples_dir}", hide=hide)
    c.run(f"sudo cp -r package/examples {examples_dir}", hide=hide)


@task(
    help={
        "verbose": "enable verbose",
        "install-type": "used to force an install type, "
                        "can be one of the following (redhat, debian)",
        "no-python": "avoid installing python system dependencies",
    },
)
def build(
    c,
    verbose=False,
    install_type=None,
    no_python=False,
):
    print("setting up to build core packages")
    c.run("sudo -v", hide=True)
    p = Progress(verbose)
    hide = not verbose
    os_info = get_os(install_type)
    with p.start("installing system dependencies"):
        install_system(c, os_info, hide, no_python)
    with p.start("installing system grpcio-tools"):
        install_grpcio(c, hide)
    with p.start("building core"):
        build_core(c, hide)
    with p.start(f"building rpm/deb packages"):
        c.run("make fpm", hide=hide)

# Borjand: Included to create CORE GUI Launcher 
@task(
    help={
        "verbose": "enable verbose",
        "no-python": "avoid installing python system dependencies",
    },
)
def launcher(
    c,
    verbose=False,
    no_python=False,
):
    print("setting up to core launcher")
    p = Progress(verbose)
    hide = not verbose
    with p.start("creating core launcher"):
        create_launcher_gui(c, hide)

def create_launcher_gui(c, verbose=False, prefix=HOME_PATH):
    """
    Create core GUI launcher
    """
    hide = not verbose
    bin_dir = Path(VENV_PATH).joinpath("bin")
    usr_apps_dir = Path(prefix).joinpath(".local/share/applications")
    app_file_path = usr_apps_dir.joinpath("core-gui.desktop")
    icon_path = Path().resolve().joinpath("daemon/core/gui/data/icons/core-icon.png")
    if icon_path.exists():
        service_data = inspect.cleandoc(f"""
            [Desktop Entry]
            Name=Common Open Research Emulator
            Exec={bin_dir}/core-gui
            Type=Application
            Icon={icon_path}
            """)
        temp = NamedTemporaryFile("w", delete=False)
        temp.write(service_data)
        temp.close()
        c.run(f"sudo cp {temp.name} {app_file_path}", hide=hide)
        c.run(f"sudo chmod 644 {app_file_path}", hide=hide)
        result = c.run(f"gsettings get org.gnome.shell favorite-apps | sed s/.$//", hide="both")
        result = f'"{result.stdout}'
        add_fav = f", 'core-gui.desktop'"
        add_end = f']"'
        result = result.replace('\n', ' ').replace('\r', '') + add_fav + add_end
        c.run(f'gsettings set org.gnome.shell favorite-apps {result}', hide=hide)
    else:
        print(f"ERROR: icon not found for creating launcher: {icon_path}")


@task(
    help={
        "dev": "install development mode",
        "verbose": "enable verbose",
        "local": "determines if core will install to local system, default is False",
        "prefix": f"prefix where scripts are installed, default is {DEFAULT_PREFIX}",
        "install-type": "used to force an install type, "
                        "can be one of the following (redhat, debian)",
        "ospf": "disable ospf installation",
        "no-python": "avoid installing python system dependencies",
    },
)
def install(
    c,
    dev=False,
    verbose=False,
    local=False,
    prefix=DEFAULT_PREFIX,
    install_type=None,
    ospf=True,
    no_python=False,
):
    """
    install core, poetry, scripts, service, and ospf mdr
    """
    python_bin = get_env_python()
    venv_path = None if local else VENV_PATH
    print(
        f"installing core using python({python_bin}) venv({venv_path}) prefix({prefix})"
    )
    c.run("sudo -v", hide=True)
    p = Progress(verbose)
    hide = not verbose
    os_info = get_os(install_type)
    if not c["run"]["dry"]:
        with p.start("checking for old installations"):
            check_existing_core(c, hide)
    with p.start("installing system dependencies"):
        install_system(c, os_info, hide, no_python)
    with p.start("installing system grpcio-tools"):
        install_grpcio(c, hide)
    with p.start("building core"):
        build_core(c, hide, prefix)
    with p.start("installing vnoded/vcmd"):
        install_core(c, hide)
    with p.start(f"installing core"):
        install_poetry(c, dev, local, hide)
    with p.start("installing scripts, examples, and configuration"):
        install_core_files(c, local, hide, prefix)
    with p.start("installing systemd service"):
        install_service(c, hide, venv_path)
    with p.start("creating core gui launcher"):
        create_launcher_gui(c, hide)
    if ospf:
        with p.start("installing ospf mdr"):
            install_ospf_mdr(c, os_info, hide)
    print("\ninstall complete!")


@task(
    help={
        "emane-version": "version of emane install",
        "verbose": "enable verbose",
        "install-type": "used to force an install type, "
                        "can be one of the following (redhat, debian)",
    },
)
def install_emane(c, emane_version, verbose=False, install_type=None):
    """
    install emane python bindings into the core virtual environment
    """
    c.run("sudo -v", hide=True)
    p = Progress(verbose)
    hide = not verbose
    os_info = get_os(install_type)
    python_dep = get_env_python_dep()
    with p.start("installing system dependencies"):
        if os_info.like == OsLike.DEBIAN:
            c.run(
                "sudo apt install -y gcc g++ automake libtool libxml2-dev "
                "libprotobuf-dev libpcap-dev libpcre3-dev uuid-dev pkg-config "
                f"protobuf-compiler git {python_dep}-protobuf {python_dep}-setuptools",
                hide=hide,
            )
        elif os_info.like == OsLike.REDHAT:
            if os_info.name == OsName.CENTOS and os_info.version >= 8:
                c.run("sudo yum config-manager --set-enabled PowerTools", hide=hide)
            c.run(
                "sudo yum install -y autoconf automake git libtool libxml2-devel "
                "libpcap-devel pcre-devel libuuid-devel make gcc-c++ protobuf-compiler "
                f"protobuf-devel {python_dep}-setuptools",
                hide=hide,
            )
    emane_dir = "../emane"
    emane_python_dir = Path(emane_dir).joinpath("src/python")
    emane_url = "https://github.com/adjacentlink/emane.git"
    with p.start("cloning emane"):
        c.run(f"git clone {emane_url} {emane_dir}", hide=hide)
    with p.start("setup emane"):
        python_bin = get_env_python()
        with c.cd(emane_dir):
            c.run(f"git checkout {emane_version}", hide=hide)
            c.run("./autogen.sh", hide=hide)
            c.run(f"PYTHON={python_bin} ./configure --prefix=/usr", hide=hide)
    with p.start("build emane python bindings"):
        with c.cd(str(emane_python_dir)):
            c.run("make -j$(nproc)", hide=hide)
    with p.start("installing emane python bindings for core virtual environment"):
        with c.cd(DAEMON_DIR):
            c.run(
                f"poetry run pip install {emane_python_dir.absolute()}", hide=hide
            )


@task(
    help={
        "dev": "uninstall development mode",
        "verbose": "enable verbose",
        "local": "determines if core was installed local to system, default is False",
        "prefix": f"prefix where scripts are installed, default is {DEFAULT_PREFIX}",
    },
)
def uninstall(
    c,
    dev=False,
    verbose=False,
    local=False,
    prefix=DEFAULT_PREFIX,
):
    """
    uninstall core, scripts, service, virtual environment, and clean build directory
    """
    python_bin = get_env_python()
    venv_path = None if local else VENV_PATH
    print(
        f"uninstalling core using python({python_bin}) "
        f"venv({venv_path}) prefix({prefix})"
    )
    hide = not verbose
    p = Progress(verbose)
    c.run("sudo -v", hide=True)
    with p.start("uninstalling core"):
        c.run("sudo make uninstall", hide=hide)
    with p.start("cleaning build directory"):
        c.run("make clean", hide=hide)
        c.run("./bootstrap.sh clean", hide=hide)
    with p.start(f"uninstalling core"):
        if local:
            python_bin = get_env_python()
            c.run(f"sudo {python_bin} -m pip uninstall -y core", hide=hide)
        else:
            if Path(VENV_PYTHON).is_file():
                with c.cd(DAEMON_DIR):
                    if dev:
                        c.run(f"{ACTIVATE_VENV} && poetry run pre-commit uninstall", hide=hide)
                    c.run(f"sudo {VENV_PYTHON} -m pip uninstall -y core", hide=hide)
    # remove installed files
    bin_dir = Path(prefix).joinpath("bin")
    with p.start("uninstalling examples"):
        examples_dir = Path(prefix).joinpath("share/core")
        c.run(f"sudo rm -rf {examples_dir}")
    # remove core-python symlink
    if not local:
        core_python = bin_dir.joinpath("core-python")
        c.run(f"sudo rm -f {core_python}", hide=hide)
    # remove service
    systemd_dir = Path("/lib/systemd/system/")
    service_name = "core-daemon.service"
    service_file = systemd_dir.joinpath(service_name)
    if service_file.exists():
        with p.start(f"uninstalling service {service_file}"):
            c.run(f"sudo systemctl disable {service_name}", hide=hide)
            c.run(f"sudo rm -f {service_file}", hide=hide)


@task(
    help={
        "dev": "reinstall development mode",
        "verbose": "enable verbose",
        "local": "determines if core will install to local system, default is False",
        "prefix": f"prefix where scripts are installed, default is {DEFAULT_PREFIX}",
        "branch": "branch to install latest code from, default is current branch",
        "install-type": "used to force an install type, "
                        "can be one of the following (redhat, debian)",
    },
)
def reinstall(
    c,
    dev=False,
    verbose=False,
    local=False,
    prefix=DEFAULT_PREFIX,
    branch=None,
    install_type=None
):
    """
    run the uninstall task, get latest from specified branch, and run install task
    """
    uninstall(c, dev, verbose, local, prefix)
    hide = not verbose
    p = Progress(verbose)
    with p.start("pulling latest code"):
        current = c.run("git rev-parse --abbrev-ref HEAD", hide=hide).stdout.strip()
        if branch and branch != current:
            c.run(f"git checkout {branch}")
        else:
            branch = current
        c.run("git pull", hide=hide)
        if not Path("tasks.py").exists():
            raise FileNotFoundError(f"missing tasks.py on branch: {branch}")
    install(c, dev, verbose, local, prefix, install_type)


@task
def test(c):
    """
    run core tests
    """
    pytest = get_pytest(c)
    with c.cd(DAEMON_DIR):
        c.run(f"sudo {pytest} -v --lf -x tests", pty=True)


@task
def test_mock(c):
    """
    run core tests using mock to avoid running as sudo
    """
    with c.cd(DAEMON_DIR):
        c.run("poetry run pytest -v --mock --lf -x tests", pty=True)


@task
def test_emane(c):
    """
    run core emane tests
    """
    pytest = get_pytest(c)
    with c.cd(DAEMON_DIR):
        c.run(f"sudo {pytest} -v --lf -x tests/emane", pty=True)


