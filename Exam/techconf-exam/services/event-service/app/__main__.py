"""Start event-service with ``python -m app``."""

from app import create_app
from app.config import load_settings


def main() -> None:
    settings = load_settings()
    application = create_app(settings=settings)
    application.run(host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
