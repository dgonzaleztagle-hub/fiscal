"""Levanta únicamente el entorno sintético local de Completo Fiscal."""

import uvicorn

from completo_dte.api.demo import create_demo_app


if __name__ == "__main__":
    uvicorn.run(create_demo_app(), host="127.0.0.1", port=8081, log_level="info")
