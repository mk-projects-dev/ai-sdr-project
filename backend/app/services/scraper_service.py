from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote_plus, urlparse
from uuid import UUID

import httpx
from anthropic import AsyncAnthropic
from bs4 import BeautifulSoup
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.database import async_session_factory
from app.models import Campaign, Lead, LeadStatus

logger = logging.getLogger(__name__)


def _use_default_playwright_browser_cache_if_sandbox_path() -> None:
    """Cursor и другие IDE задают PLAYWRIGHT_BROWSERS_PATH во временный sandbox-кatalog без установленного Chromium.
    Сбрасываем переменную — Playwright берёт браузеры из стандартного кеша пользователя (после `playwright install chromium`)."""
    raw = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if not raw:
        return
    lower = raw.lower()
    if "cursor-sandbox" in lower or "sandbox-cache" in lower:
        logger.info(
            "Сбрасываю PLAYWRIGHT_BROWSERS_PATH (был путь из sandbox: …%s), "
            "используется кеш по умолчанию",
            raw[-60:],
        )
        del os.environ["PLAYWRIGHT_BROWSERS_PATH"]


EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
)
RATING_RE = re.compile(r"(\d+[\.,]\d+)")
GOOGLE_HOST_FRAGMENTS = (
    "google.com",
    "gstatic.com",
    "googleusercontent.com",
    "schema.org",
    "goo.gl",
    "ggpht.com",
    "webcache.googleusercontent.com",
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class ParsedPlace:
    name: str
    rating: str
    website: Optional[str]


def _is_external_website(href: str) -> bool:
    if not href or not href.startswith("http"):
        return False
    try:
        host = urlparse(href).netloc.lower()
    except Exception:
        return False
    return not any(f in host for f in GOOGLE_HOST_FRAGMENTS)


def _clean_url(href: str) -> str:
    return href.split("?")[0].rstrip("/")


async def _dismiss_cookies(page) -> None:
    for name in (
        "Accept all",
        "I agree",
        "Tout accepter",
        "Согласен",
        "Принять все",
        "Alles accepteren",
    ):
        try:
            btn = page.get_by_role("button", name=re.compile(re.escape(name), re.I))
            if await btn.count() > 0:
                await btn.first.click(timeout=2000)
                return
        except (PlaywrightError, PlaywrightTimeout):
            continue


def _extract_rating_from_text(text: str) -> str:
    m = RATING_RE.search(text)
    if m:
        return m.group(1).replace(",", ".")
    return "—"


async def _parse_result_article(article) -> Optional[ParsedPlace]:
    name = ""
    try:
        link = article.locator('a[href*="/maps/place/"]').first
        if await link.count() > 0:
            t = (await link.inner_text() or "").strip()
            if t:
                name = t.splitlines()[0].strip()
    except PlaywrightError:
        pass
    if not name:
        raw = (await article.inner_text() or "").strip()
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if not lines:
            return None
        name = lines[0][:512]

    website: Optional[str] = None
    try:
        anchors = await article.locator("a[href]").all()
        for handle in anchors:
            href = await handle.get_attribute("href")
            if href and _is_external_website(href):
                website = _clean_url(href)
                break
    except PlaywrightError:
        pass

    text_block = (await article.inner_text() or "").strip()
    rating = _extract_rating_from_text(text_block)
    return ParsedPlace(name=name.strip()[:512], rating=rating, website=website)


async def scrape_google_maps_places(
    location: str, keyword: str, limit: int
) -> list[ParsedPlace]:
    """Загружает Google Maps, вводит поиск и забирает до `limit` карточек из боковой панели."""
    query = f"{keyword} {location}".strip()
    path = quote_plus(query)
    url = f"https://www.google.com/maps/search/{path}"
    results: list[ParsedPlace] = []
    seen: set[str] = set()
    max_scrolls = 25

    _use_default_playwright_browser_cache_if_sandbox_path()

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
        except Exception as e:
            hint = (
                "В venv выполните: `python -m playwright install chromium`. "
                "Если задан PLAYWRIGHT_BROWSERS_PATH (в т.ч. sandbox), для локального запуска сделайте `unset PLAYWRIGHT_BROWSERS_PATH`."
            )
            if "Executable doesn't exist" in str(e):
                hint += (
                    " Запускайте установку и сервер API из обычного терминала, не из изолированной среды без браузеров."
                )
            logger.error(
                "Playwright: не удалось запустить Chromium. %s Ошибка: %s",
                hint,
                e,
            )
            raise

        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=USER_AGENT,
            locale="ru-RU",
            timezone_id="Europe/Kiev",
        )
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_timeout(2000)
            await _dismiss_cookies(page)

            try:
                await page.wait_for_selector('div[role="feed"]', timeout=45000)
            except PlaywrightTimeout:
                logger.warning("Лента результатов Maps не появилась за отведённое время")
                return []

            for scroll_i in range(max_scrolls):
                if len(results) >= limit:
                    break
                articles = await page.locator(
                    'div[role="feed"] div[role="article"]'
                ).all()
                for article in articles:
                    if len(results) >= limit:
                        break
                    try:
                        place = await _parse_result_article(article)
                    except PlaywrightError as err:
                        logger.debug("skip article: %s", err)
                        continue
                    if place is None:
                        continue
                    key = place.name.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append(place)

                feed = page.locator('div[role="feed"]')
                try:
                    await feed.evaluate(
                        """(el) => { el.scrollTop = el.scrollHeight; }"""
                    )
                except PlaywrightError:
                    break
                await page.wait_for_timeout(1400)
                if scroll_i > 3 and len(articles) == 0:
                    break

        finally:
            await context.close()
            await browser.close()

    return results[:limit]


async def fetch_email_from_website(url: str) -> Optional[str]:
    """Грузит главную страницу сайта и ищет mailto: или email в тексте."""
    if not url:
        return None
    u = url.strip()
    if not u.startswith(("http://", "https://")):
        u = "https://" + u

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(20.0),
            headers=headers,
        ) as client:
            r = await client.get(u)
            r.raise_for_status()
    except (httpx.HTTPError, OSError) as e:
        logger.info("Не удалось загрузить сайт %s: %s", u, e)
        return None

    if "text/html" not in (r.headers.get("content-type") or ""):
        return None

    html = r.text
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select('a[href^="mailto:"]'):
        href = a.get("href") or ""
        m = re.search(r"mailto:([^?&]+)", href, re.I)
        if m:
            addr = m.group(1).strip()
            em = EMAIL_RE.search(addr)
            if em:
                return em.group(0).lower()
    for em in EMAIL_RE.finditer(soup.get_text(" ", strip=True)):
        return em.group(0).lower()
    return None


async def generate_pain_point(
    company: str, niche: str, rating: str
) -> str:
    """Короткая 'боль' для лида через Anthropic; при отсутствии ключа — эвристика."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return (
            f"В сегменте «{niche}» у «{company}» (рейтинг {rating}) "
            f"часто страдают рутинные процессы и отклик клиентов — "
            f"автоматизация аутрича могла бы снять нагрузку с команды."
        )
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    user = (
        f"Компания: {company}, Ниша: {niche}, Рейтинг: {rating}. "
        "Придумай 1 реалистичную проблему (боль) для этой компании, "
        "которую мы могли бы решить нашей услугой автоматизации. "
        "Ответь одним коротким предложением."
    )
    message = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=256,
        messages=[{"role": "user", "content": user}],
    )
    parts: list[str] = []
    for block in message.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    text = "".join(parts).strip()
    if not text:
        return (
            f"Рутинные операции и коммуникации в «{company}» "
            f"могли бы выиграть от автоматизации."
        )
    return text


async def run_maps_parser_job(
    campaign_id: UUID,
    location: str,
    keyword: str,
    limit: int,
) -> None:
    """Фоновая задача: Maps → боль (Claude) → email с сайта → Lead в БД."""
    logger.info(
        "Parser job: campaign_id=%s location=%r keyword=%r limit=%s",
        campaign_id,
        location,
        keyword,
        limit,
    )

    async with async_session_factory() as session:
        r = await session.execute(select(Campaign).where(Campaign.id == campaign_id))
        if r.scalar_one_or_none() is None:
            logger.error("Parser: campaign %s not found", campaign_id)
            return

    try:
        places = await scrape_google_maps_places(location, keyword, limit)
    except Exception:
        logger.exception("Parser: Google Maps scrape failed")
        return

    if not places:
        logger.warning("Parser: no places returned from Maps")
        return

    created = 0
    for place in places:
        pain = await generate_pain_point(
            place.name, keyword, place.rating
        )
        email: Optional[str] = None
        if place.website:
            email = await fetch_email_from_website(place.website)
        if not email:
            logger.info(
                "Parser: пропуск «%s» — email на сайте не найден (site=%s)",
                place.name,
                place.website,
            )
            continue

        async with async_session_factory() as session:
            lead = Lead(
                campaign_id=campaign_id,
                email=email,
                first_name=None,
                company_name=place.name,
                pain_point=pain,
                source="parser",
                status=LeadStatus.new,
            )
            session.add(lead)
            try:
                await session.commit()
                created += 1
            except IntegrityError:
                await session.rollback()
                logger.info("Parser: email %s уже в базе, пропуск", email)

    logger.info("Parser job finished: saved %s leads (attempted %s)", created, len(places))
