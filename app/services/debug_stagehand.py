from __future__ import annotations

import os
from typing import Any

from stagehand import Stagehand, StagehandConfig


async def analyze_page_with_stagehand(url: str) -> dict[str, Any]:
    """
    Открывает страницу через Browserbase/Stagehand и возвращает краткое описание интерфейса.
    Структура ответа:
      {
        "success": bool,
        "url": str,
        "description": str | None,
        "error": str | None
      }
    """

    browserbase_api_key = os.getenv("BROWSERBASE_API_KEY")
    browserbase_project_id = os.getenv("BROWSERBASE_PROJECT_ID")
    model_api_key = os.getenv("MODEL_API_KEY")
    model_name = os.getenv("STAGEHAND_MODEL_NAME", "gpt-4o")

    if not browserbase_api_key or not browserbase_project_id or not model_api_key:
        missing = [
            name
            for name, value in (
                ("BROWSERBASE_API_KEY", browserbase_api_key),
                ("BROWSERBASE_PROJECT_ID", browserbase_project_id),
                ("MODEL_API_KEY", model_api_key),
            )
            if not value
        ]
        return {
            "success": False,
            "url": url,
            "description": None,
            "error": f"Missing required environment variables: {', '.join(missing)}",
        }

    config = StagehandConfig(
        env="BROWSERBASE",
        browserbase_api_key=browserbase_api_key,
        browserbase_project_id=browserbase_project_id,
        model_api_key=model_api_key,
        model=model_name,
    )

    stagehand = Stagehand(config=config)
    await stagehand.init()

    try:
        page = await stagehand.get_page()
        await page.goto(url)
        await page.wait_for_timeout(12000)

        description_prompt = (
            "Составь краткое структурированное описание интерфейса текущей страницы на русском языке. "
            "Укажи: 1) назначение и концепцию страницы; 2) ключевые элементы интерфейса (списки, карточки, формы, таблицы, карты и т.п.); "
            "3) навигацию и структуру; 4) основные действия пользователя; 5) особые состояния, уведомления или статусы. "
            "Держи ответ лаконичным, но информативным."
        )

        description = await page.extract(description_prompt)

        return {
            "success": True,
            "url": url,
            "description": str(description) if description is not None else None,
            "error": None,
        }
    except Exception as exc:  # pragma: no cover - внешняя интеграция
        return {
            "success": False,
            "url": url,
            "description": None,
            "error": str(exc),
        }
    finally:
        await stagehand.close()
