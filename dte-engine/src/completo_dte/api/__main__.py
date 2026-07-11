"""Arranque con `python -m completo_dte.api`."""

import os

import uvicorn

from .bootstrap import create_app_from_environment


def main() -> None:
    host = os.environ.get("DTE_HOST", "127.0.0.1")
    port = int(os.environ.get("DTE_PORT", "8080"))
    uvicorn.run(create_app_from_environment(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

