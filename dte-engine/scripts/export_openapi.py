"""Exporta el contrato OpenAPI sin abrir bases de datos ni leer secretos."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from completo_dte.api.app import create_app
from completo_dte.application import IssueBoletaService
from completo_dte.infrastructure import FolioLedger


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    # Las dependencias sólo se ejecutan al atender una solicitud. OpenAPI puede
    # generarse de manera pura, sin material tributario ni conexiones externas.
    app = create_app(
        issue_service=cast(IssueBoletaService, None),
        ledger=cast(FolioLedger, None),
        api_keys={"openapi-export-only": "synthetic-tenant"},
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
