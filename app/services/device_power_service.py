import subprocess


def restart_device():
    subprocess.run(
        ["systemctl", "reboot"],
        check=True,
        timeout=10,
    )


def shutdown_device():
    subprocess.run(
        ["systemctl", "poweroff"],
        check=True,
        timeout=10,
    )
