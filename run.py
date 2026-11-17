import os

from app import app
from app.scheduler import start_scheduler

if __name__ == "__main__":
    debug = True
    # With the auto-reloader on, Flask starts two processes; only the one that actually serves
    # requests has WERKZEUG_RUN_MAIN set, so start the scheduler there and nowhere else.
    if not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_scheduler(app)
    app.run(host="0.0.0.0", port=5000, debug=debug)
