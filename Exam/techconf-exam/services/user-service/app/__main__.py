"""Entry point: python -m app

Reads PORT from the environment (default 5001) and starts the Flask
development server. The acceptance suite injects PORT at launch time.
"""

import os
from app import create_app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    application = create_app()
    application.run(host="0.0.0.0", port=port)
