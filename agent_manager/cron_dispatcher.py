import sys
import asyncio
import logging

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from agent_manager.cron.scheduler import ProjectBacklogDispatcher

dispatcher = ProjectBacklogDispatcher()

__all__ = ["ProjectBacklogDispatcher", "dispatcher"]

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Autonomous Project Board Backlog Dispatcher")
    parser.add_argument("--run-now", action="store_true", help="Run once immediately and exit")
    parser.add_argument("--initial-delay", type=int, default=1440, help="Initial delay in seconds (default: 1440)")
    parser.add_argument("--interval", type=int, default=600, help="Recurring interval in seconds (default: 600)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if args.run_now:
        res = asyncio.run(dispatcher.check_and_dispatch())
        print("Result:", res)
    else:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(dispatcher.start(args.initial_delay, args.interval))
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            dispatcher.stop()
