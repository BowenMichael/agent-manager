import argparse
import sys
import uvicorn
from agent_manager.config import HOST, PORT

def main():
    parser = argparse.ArgumentParser(description="Agent Manager - Webhook Dispatcher & Live Control Plane")
    parser.add_argument("--host", default=HOST, help=f"Host to bind (default: {HOST})")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port to bind (default: {PORT})")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    banner = (
        "============================================================\n"
        " [*] AGENT MANAGER (Google Antigravity SDK)\n"
        f" [*] Dashboard & REST API : http://{args.host}:{args.port}\n"
        f" [*] GitHub Webhook URL   : http://{args.host}:{args.port}/api/webhooks/github\n"
        f" [*] WebSocket Stream     : ws://{args.host}:{args.port}/ws/agents\n"
        "============================================================"
    )
    try:
        print(banner)
    except UnicodeEncodeError:
        print("AGENT MANAGER running on http://{}:{}".format(args.host, args.port))

    uvicorn.run("agent_manager.server:app", host=args.host, port=args.port, reload=args.reload)

if __name__ == "__main__":
    main()
