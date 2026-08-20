import socket
import subprocess
import time

def is_time_synchronized():
    try:
        result = subprocess.run(
            [
                "timedatectl",
                "show",
                "--property=NTPSynchronized",
                "--value",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and result.stdout.strip() == "yes"
    except (OSError, subprocess.SubprocessError):
        return False
    
def is_spotify_reachable():
    try:
        socket.getaddrinfo(
            "api.spotify.com",
            443,
            type=socket.SOCK_STREAM,
        )
        return True
    except OSError:
        return False
    

def wait_until_ready():
    while True:
        time_ready = is_time_synchronized()
        spotify_ready = is_spotify_reachable()

        if time_ready and spotify_ready:
            print("[STARTUP] Network and system time are ready", flush=True)
            return

        print(
            f"[STARTUP] Waiting: "
            f"time_synced={time_ready}, "
            f"spotify_dns={spotify_ready}",
            flush=True,
        )
        time.sleep(2)


if __name__ == "__main__":
    wait_until_ready()