"""
Daemon worker wrapper for detached agent processes.
Runs an agent CLI command as a detached subprocess and records its exit code to an exit code file.
"""
import sys
import subprocess
from pathlib import Path


def main():
    if len(sys.argv) < 3:
        sys.stderr.write("Usage: daemon_worker.py <exit_code_file> <cmd> [args...]\n")
        sys.exit(1)

    exit_code_file = Path(sys.argv[1])
    cmd = sys.argv[2:]

    try:
        # Run command synchronously; stdout and stderr are inherited from this wrapper process
        res = subprocess.run(cmd)
        return_code = res.returncode
    except Exception as e:
        sys.stderr.write(f"Error executing agent CLI command: {e}\n")
        return_code = 1

    try:
        exit_code_file.parent.mkdir(parents=True, exist_ok=True)
        exit_code_file.write_text(str(return_code), encoding="utf-8")
    except Exception as e:
        sys.stderr.write(f"Error writing exit code file {exit_code_file}: {e}\n")

    sys.exit(return_code)


if __name__ == "__main__":
    main()
