import argparse
import uvicorn
from agent_manager.config import HOST, PORT

def main():
    parser = argparse.ArgumentParser(description="Agent Manager - Webhook Dispatcher & Live Control Plane")
    parser.add_argument("--host", default=HOST, help=f"Host to bind (default: {HOST})")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port to bind (default: {PORT})")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    print("=" * 60)
    print(" 🚀 AGENT MANAGER (Google Antigravity SDK)")
    print(f" 🌐 Dashboard & REST API : http://{args.host}:{args.port}")
    print(f" 🪝 GitHub Webhook URL   : http://{args.host}:{args.port}/api/webhooks/github")
    print(f" ⚡ WebSocket Stream     : ws://{args.host}:{args.port}/ws/agents")
    print("=" * 60)

    uvicorn.run("agent_manager.server:app", host=args.host, port=args.port, reload=args.reload)

if __name__ == "__main__":
    main()
