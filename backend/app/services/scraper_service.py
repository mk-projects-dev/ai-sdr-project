from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import httpx
from anthropic import AsyncAnthropic
from bs4 import BeautifulSoup
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.database import async_session_factory
from app.models import Lead, LeadStatus

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

# Хосты агрегаторов и соцсетей — не считаем их «официальным сайтом» из поисковой выдачи.
AGGREGATOR_HOST_SNIPPETS = (
    "facebook.",
    "instagram.",
    "booking.",
    "tripadvisor.",
    "agoda.",
    "hotels.com",
    "linkedin.",
    "twitter.",
    "vk.com",
    "ok.ru",
    "youtube.",
    "youtu.be",
    "yelp.",
    "foursquare.",
    "tiktok.",
    "wa.me",
    "telegram.",
    "t.me/",
)

# Подстроки href или текста ссылки для страниц контактов / о нас (без учёта регистра).
_CONTACT_LINK_HINTS = (
    "contact",
    "about",
    "контакт",
    "зв'язок",
    "про нас",
    "feedback",
)


def _href_or_text_matches_contact_hints(href: str, link_text: str) -> bool:
    blob = f"{href} {link_text}".lower().replace("\u2019", "'").replace("`", "'")
    return any(hint in blob for hint in _CONTACT_LINK_HINTS)


# Подстроки в URL выдачи Bing — каталоги, соцсети, бронирование (агрессивный фильтр).
BANNED_DOMAINS = [
    "bing.com",
    "microsoft.com",
    "yahoo.com",
    "google.com",
    "booking.com",
    "tripadvisor.",
    "agoda.com",
    "expedia.com",
    "hotels.com",
    "airbnb.",
    "facebook.com",
    "instagram.com",
    "kyivhotels.net",
    "planetofhotels.com",
    "vlasne.ua",
    "dobovo.com",
    "hotels24.ua",
    "doba.ua",
    "2gis.",
    "youtube.com",
    "luxuryhotels",
    "tiktok.com",
    "linkedin.com",
    "twitter.com",
]

# Минимальный score `_score_url` для принятия URL после Yahoo fallback-поиска из Maps (Playwright).
_MAPS_FALLBACK_WEBSITE_SCORE_MIN = 0.25

# Таймауты HTTP при обходе сайтов (главная + страницы контактов).
FETCH_TIMEOUT = httpx.Timeout(18.0, connect=10.0)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class ParsedPlace:
    name: str
    rating: str
    website: Optional[str]
    maps_place_url: Optional[str]


def _normalize_maps_card_url(href: Optional[str]) -> Optional[str]:
    """Полная ссылка на карточку места в Google Maps (относительный href → абсолютный)."""
    if not href:
        return None
    h = href.strip()
    if not h:
        return None
    if h.startswith("/"):
        return f"https://www.google.com{h}"
    if h.startswith(("http://", "https://")):
        return h
    return None


def _parse_rating_float(rating: str) -> Optional[float]:
    s = (rating or "").replace(",", ".").strip()
    if not s or s == "—":
        return None
    try:
        return float(s)
    except ValueError:
        return None


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


def _host_is_aggregator_or_social(host: str) -> bool:
    h = host.lower()
    if not h:
        return True
    if h.startswith("www."):
        h = h[4:]
    if h == "t.co" or h.endswith(".t.co"):
        return True
    return any(snippet in h for snippet in AGGREGATOR_HOST_SNIPPETS)


def _unwrap_tracking_redirect_href(href: str) -> str:
    """Редиректы DDG (uddg), Bing (aclk / ck/a) и похожие."""
    h = (href or "").strip()
    if not h:
        return h
    low = h.lower()
    try:
        if "duckduckgo.com" in low and "uddg=" in low:
            q = parse_qs(urlparse(h).query)
            inner = (q.get("uddg") or [None])[0]
            if inner:
                return unquote(inner).strip()
        if "bing.com" in low and ("aclk" in low or "/ck/a" in low):
            q = parse_qs(urlparse(h).query)
            for key in ("u", "url"):
                inner = (q.get(key) or [None])[0]
                if inner:
                    decoded = unquote(inner).strip()
                    if decoded.startswith(("http://", "https://")):
                        return decoded
    except Exception:
        pass
    return h


def _url_contains_any_banned_domain(url: str) -> bool:
    low = (url or "").lower()
    return any(banned.lower() in low for banned in BANNED_DOMAINS)


def _clean_for_match(text: str) -> str:
    """Оставляет только буквы и цифры, переводит в нижний регистр для сравнения."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _score_url(company_name: str, url: str) -> float:
    """Считает процент совпадения между названием компании и корнем домена."""
    try:
        netloc = urlparse(url).netloc.lower()
        netloc = netloc.replace("www.", "")
        parts = netloc.split(".")

        # Извлекаем корневой домен, игнорируя сабдомены и двойные зоны (типа .com.ua)
        if len(parts) >= 3 and parts[-2] in [
            "co",
            "com",
            "org",
            "net",
            "gov",
            "edu",
            "in",
        ]:
            main_domain = parts[-3]
        elif len(parts) >= 2:
            main_domain = parts[-2]
        else:
            main_domain = parts[0]

        clean_name = _clean_for_match(company_name)
        clean_domain = _clean_for_match(main_domain)

        if not clean_name:
            return 0.0

        return SequenceMatcher(None, clean_name, clean_domain).ratio()
    except Exception:
        return 0.0


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
    maps_place_url: Optional[str] = None
    name = ""
    try:
        link = article.locator('a[href*="/maps/place/"]').first
        if await link.count() > 0:
            href_attr = await link.get_attribute("href")
            maps_place_url = _normalize_maps_card_url(href_attr)
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
    return ParsedPlace(
        name=name.strip()[:512],
        rating=rating,
        website=website,
        maps_place_url=maps_place_url,
    )


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
                    if not place.website:
                        search_page = await context.new_page()
                        try:
                            q = quote_plus(
                                f"{place.name} {location} official website"
                            )
                            yahoo_search_url = (
                                f"https://search.yahoo.com/search?p={q}"
                            )

                            await search_page.goto(
                                yahoo_search_url,
                                wait_until="domcontentloaded",
                                timeout=15000,
                            )
                            await search_page.wait_for_timeout(
                                2000
                            )  # Даем JS отрендерить ссылки

                            raw_links = await search_page.evaluate(
                                "() => Array.from(document.querySelectorAll('a')).map(a => a.href)"
                            )
                            links = (
                                raw_links if isinstance(raw_links, list) else []
                            )

                            best_url = None
                            best_score = 0.0

                            for raw_link in links:
                                link = (raw_link or "").strip()
                                if not link.lower().startswith("http"):
                                    continue

                                resolved = _unwrap_tracking_redirect_href(
                                    link
                                ).strip()
                                if not resolved.lower().startswith("http"):
                                    resolved = link

                                lower_link = resolved.lower()
                                if (
                                    _url_contains_any_banned_domain(resolved)
                                    or "yahoo.com" in lower_link
                                ):
                                    continue

                                cleaned = _clean_url(resolved)
                                score = _score_url(place.name, cleaned)
                                if score > best_score:
                                    best_score = score
                                    best_url = cleaned

                            if (
                                best_url
                                and best_score >= _MAPS_FALLBACK_WEBSITE_SCORE_MIN
                            ):
                                place.website = best_url
                                logger.info(
                                    "Найден сайт через Yahoo: %s (score: %.2f) для %s",
                                    best_url,
                                    best_score,
                                    place.name,
                                )
                            else:
                                logger.info(
                                    "Yahoo не нашел сайт для %s. Лучший score: %.2f. Всего ссылок: %d",
                                    place.name,
                                    best_score,
                                    len(links),
                                )

                        except Exception as e:
                            logger.warning(
                                "Ошибка при поиске сайта Yahoo для %s: %s",
                                place.name,
                                e,
                            )
                        finally:
                            await search_page.close()

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


def _same_site_host(page_host: str, link_host: str) -> bool:
    """Совпадение сайта с учётом www."""

    def norm(h: str) -> str:
        h = h.lower()
        return h[4:] if h.startswith("www.") else h

    return norm(page_host) == norm(link_host)


def _extract_email_from_soup(soup: BeautifulSoup) -> Optional[str]:
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


def _collect_contact_page_urls(
    page_url: str, soup: BeautifulSoup, max_pages: int = 3
) -> list[str]:
    try:
        page_host = urlparse(page_url).netloc
    except Exception:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        href_raw = (a.get("href") or "").strip()
        if not href_raw or href_raw.startswith("#"):
            continue
        low_h = href_raw.lower()
        if low_h.startswith(("javascript:", "mailto:", "tel:")):
            continue
        text = (a.get_text() or "").strip()
        if not _href_or_text_matches_contact_hints(href_raw, text):
            continue
        full = urljoin(page_url, href_raw)
        full = full.split("#")[0]
        try:
            link_host = urlparse(full).netloc
        except Exception:
            continue
        if not _same_site_host(page_host, link_host):
            continue
        path_low = urlparse(full).path.lower()
        if any(
            path_low.endswith(ext)
            for ext in (
                ".pdf",
                ".jpg",
                ".jpeg",
                ".png",
                ".gif",
                ".webp",
                ".zip",
                ".css",
                ".js",
            )
        ):
            continue
        if full not in seen:
            seen.add(full)
            out.append(full)
        if len(out) >= max_pages:
            break
    return out


async def fetch_email_from_website(url: str) -> Optional[str]:
    """Главная: mailto + EMAIL_RE в тексте; иначе до 3 внутренних страниц по подсказкам в href/тексте ссылки."""
    if not url:
        return None
    u = url.strip()
    if not u.startswith(("http://", "https://")):
        u = "https://" + u

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=FETCH_TIMEOUT,
        headers=headers,
    ) as client:
        try:
            r = await client.get(u)
            r.raise_for_status()
        except httpx.RequestError as e:
            logger.info("Не удалось загрузить главную %s: %s", u, e)
            return None
        except OSError as e:
            logger.info("Не удалось загрузить главную %s: %s", u, e)
            return None

        ct = r.headers.get("content-type") or ""
        if "text/html" not in ct:
            return None

        base_url = str(r.url)
        soup = BeautifulSoup(r.text, "html.parser")
        email = _extract_email_from_soup(soup)
        if email:
            return email

        contact_urls = _collect_contact_page_urls(base_url, soup, max_pages=3)
        for contact_url in contact_urls:
            try:
                r2 = await client.get(contact_url)
                r2.raise_for_status()
            except httpx.RequestError as err:
                logger.debug(
                    "Страница контактов недоступна %s: %s",
                    contact_url[:256],
                    err,
                )
                continue
            except OSError as err:
                logger.debug(
                    "Страница контактов недоступна %s: %s",
                    contact_url[:256],
                    err,
                )
                continue
            except httpx.HTTPStatusError as err:
                logger.debug(
                    "Страница контактов %s: %s",
                    contact_url[:256],
                    err,
                )
                continue

            ct2 = r2.headers.get("content-type") or ""
            if "text/html" not in ct2:
                continue
            try:
                soup2 = BeautifulSoup(r2.text, "html.parser")
                email = _extract_email_from_soup(soup2)
            except Exception as err:
                logger.debug(
                    "Ошибка разбора страницы контактов %s: %s",
                    contact_url[:256],
                    err,
                )
                continue
            if email:
                logger.info(
                    "Email найден на странице контактов: %s",
                    contact_url,
                )
                return email

        return None


async def generate_pain_point(
    company: str, niche: str, rating: str
) -> str:
    """Короткая «боль» для лида через Anthropic; при отсутствии ключа — эвристика по рейтингу."""
    settings = get_settings()
    r = _parse_rating_float(rating)

    def fallback_pain() -> str:
        if r is not None and r < 4.0:
            return (
                f"У «{company}» в нише «{niche}» (рейтинг {rating}) заметны провалы в сервисе "
                f"и работе с негативом — теряются повторные визиты и репутация в отзывах."
            )
        if r is not None and r > 4.5:
            return (
                f"«{company}» в «{niche}» при рейтинге {rating} перегружена потоком записей "
                f"и ручными напоминаниями — растут очереди и срывы слотов."
            )
        return (
            f"«{company}» в нише «{niche}» (рейтинг {rating}) тратит время на ручную координацию "
            f"записей и напоминаний вместо роста без потери качества сервиса."
        )

    if not settings.anthropic_api_key:
        return fallback_pain()

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    user = (
        f"Ниша: {niche}. Компания: {company}. Рейтинг (Google Maps): {rating}.\n\n"
        "Проанализируй нишу и рейтинг. Если рейтинг ниже 4.0, сфокусируйся на проблемах сервиса "
        "и обработке жалоб. Если рейтинг выше 4.5, сфокусируйся на масштабировании и автоматизации "
        "записи для загруженных клиник (или аналогичном потоке клиентов в этой нише).\n"
        "Предложи ОДНУ конкретную, правдоподобную проблему, опираясь на эти данные. "
        "Избегай общих фраз про «аутрич» или холодные письма. "
        "Ответ — одно короткое предложение."
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
        return fallback_pain()
    return text


async def run_maps_parser_job(
    location: str,
    keyword: str,
    limit: int,
) -> int:
    """Фоновая задача: Maps → боль (Claude) → email с сайта → Lead в БД (без кампании).

    Возвращает число сохранённых новых лидов (0, если нечего сохранить или ошибки до сохранения).
    """
    logger.info(
        "Parser job: location=%r keyword=%r limit=%s",
        location,
        keyword,
        limit,
    )

    try:
        places = await scrape_google_maps_places(location, keyword, limit)
    except Exception:
        logger.exception("Parser: Google Maps scrape failed")
        return 0

    if not places:
        logger.warning("Parser: no places returned from Maps")
        return 0

    created = 0
    for place in places:
        pain = await generate_pain_point(
            place.name, keyword, place.rating
        )
        website = (place.website or "").strip() or None

        email: Optional[str] = None
        if website:
            email = await fetch_email_from_website(website)

        if not email:
            logger.info(
                "Parser: пропуск «%s» — email не найден (site Maps/search=%s)",
                place.name,
                website,
            )
            continue

        async with async_session_factory() as session:
            lead = Lead(
                campaign_id=None,
                email=email,
                company_name=place.name,
                pain_point=pain,
                website_url=website,
                maps_url=place.maps_place_url,
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
    return created
