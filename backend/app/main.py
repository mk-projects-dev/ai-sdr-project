from __future__ import annotations

import logging

from app.application import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = create_app(start_background_workers=True)
