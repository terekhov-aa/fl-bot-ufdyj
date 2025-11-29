from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import engine, get_session

router = APIRouter(prefix="/api/debug", tags=["debug"])


@router.get("/db-info")
def get_db_info(
    write_check: bool = Query(False, description="Perform a writable check against the database."),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    settings = get_settings()

    env_info = {
        "DATABASE_URL_env": os.getenv("DATABASE_URL"),
        "settings_database_url": settings.database_url,
        "sqlalchemy_engine_url": str(engine.url),
    }

    info: dict[str, Any] = {"env": env_info}

    try:
        db_runtime_info: dict[str, Any] = {}

        current_db_row = (
            session.execute(text("SELECT current_database() AS db, current_user AS user"))
            .mappings()
            .first()
        )
        if current_db_row:
            db_runtime_info["current_database"] = current_db_row.get("db")
            db_runtime_info["current_user"] = current_db_row.get("user")

        db_runtime_info["data_directory"] = session.execute(text("SHOW data_directory")).scalar_one_or_none()
        db_runtime_info["server_version"] = session.execute(text("SHOW server_version")).scalar_one_or_none()

        try:
            orders_count = session.execute(text("SELECT COUNT(*) FROM orders")).scalar_one()
            db_runtime_info["orders_count"] = orders_count
        except Exception:
            db_runtime_info["orders_count"] = None

        info["db_runtime_info"] = db_runtime_info

        debug_marker_info: dict[str, Any] = {"enabled": bool(write_check), "last_entries": []}
        if write_check:
            session.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS debug_marker ("
                    "id serial primary key, "
                    "note text, "
                    "created_at timestamptz default now()"
                    ")"
                )
            )
            session.execute(
                text("INSERT INTO debug_marker (note) VALUES (:note)"),
                {"note": "ping from /api/debug/db-info"},
            )
            debug_marker_info["last_entries"] = (
                session.execute(
                    text(
                        "SELECT id, note, created_at FROM debug_marker "
                        "ORDER BY created_at DESC LIMIT 5"
                    )
                )
                .mappings()
                .all()
            )
        else:
            debug_marker_info["message"] = "Set write_check=1 to insert a marker"

        info["debug_marker"] = debug_marker_info

        return info
    except Exception as exc:  # pragma: no cover - diagnostic endpoint
        raise HTTPException(status_code=503, detail={"db_error": str(exc)}) from exc
