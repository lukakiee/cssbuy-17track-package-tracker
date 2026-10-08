"""CSSBuy + 17TRACK terminal tracker.

Created by @lukakiee — TikTok / Instagram.

When launched, the program asks for a CSSBuy bearer token and 17TRACK API
token. They are used for the current run only and are never saved in this file.
Advanced users may instead set CSSBUY_TOKEN and TRACK17_TOKEN before running.

The CSSBuy getTrack endpoint needs *both* a CSSBuy SID and a shipment tracking
number.  This program deliberately asks for both, rather than making a request
with an empty `sn` field.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from getpass import getpass
from typing import Any

import requests


CSSBUY_URL = "https://www.cssbuy.com/api/v2/user/sendorder/getTrack"
TRACK17_BASE_URL = "https://api.17track.net/track/v2.4"
CONNECT_TIMEOUT_SECONDS = 10
READ_TIMEOUT_SECONDS = 30
CREATOR = "@lukakiee · TikTok / Instagram"

# Terminal styling
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
CYAN, GREEN, YELLOW, RED, WHITE, GRAY = (
    "\033[96m", "\033[92m", "\033[93m", "\033[91m", "\033[97m", "\033[90m"
)


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def divider(character: str = "─", width: int = 60) -> str:
    return character * width


def heading(text: str) -> None:
    print(f"{CYAN}╭{divider('─', 58)}╮{RESET}")
    print(f"{CYAN}│{RESET} {BOLD}{WHITE}{text.center(56)}{RESET} {CYAN}│{RESET}")
    print(f"{CYAN}╰{divider('─', 58)}╯{RESET}")
    print(f"{GRAY}                 Created by {CREATOR}{RESET}")


def section(text: str) -> None:
    fill = max(1, 52 - len(text))
    print(f"\n{CYAN}┌─ {BOLD}{WHITE}{text}{RESET} {CYAN}{divider('─', fill)}┐{RESET}")


def end_section() -> None:
    print(f"{CYAN}└{divider('─', 58)}┘{RESET}")


def success(text: str) -> None:
    print(f"  {GREEN}✓{RESET} {text}")


def error(text: str) -> None:
    print(f"  {RED}✕{RESET} {text}")


def info(text: str) -> None:
    print(f"  {CYAN}•{RESET} {text}")


def loading(text: str) -> None:
    print(f"  {YELLOW}⠋{RESET} {text}")


def friendly_time(value: Any, short: bool = False) -> str:
    if not value:
        return "Unknown"
    text = str(value)
    for candidate in (text.replace("Z", "+00:00"), text):
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed.strftime("%d %b · %H:%M" if short else "%d %b %Y · %H:%M")
        except ValueError:
            pass
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            parsed = datetime.strptime(text, pattern)
            return parsed.strftime("%d %b · %H:%M" if short else "%d %b %Y · %H:%M")
        except ValueError:
            pass
    return text


def require_tokens() -> tuple[str, str] | None:
    cssbuy_token = os.getenv("CSSBUY_TOKEN", "").strip()
    track17_token = os.getenv("TRACK17_TOKEN", "").strip()
    if cssbuy_token and track17_token:
        return cssbuy_token, track17_token

    print("\n  Paste your replacement API tokens below.")
    print(f"  {GRAY}They are used only for this run and are not saved in the script.{RESET}\n")
    try:
        cssbuy_token = getpass("  CSSBuy token › ").strip()
        track17_token = getpass("  17TRACK token › ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if cssbuy_token and track17_token:
        return cssbuy_token, track17_token
    error("Both tokens are required.")
    return None


def cssbuy_headers(token: str) -> dict[str, str]:
    # These headers and multipart form fields mirror the proven CSSBuy request.
    return {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
        "Lang": "en",
        "Tojson": "true",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
        ),
    }


def get_cssbuy_history(sid: str, tracking_number: str, token: str) -> tuple[dict[str, Any] | None, str | None]:
    """Return CSSBuy tracking data using the endpoint's required multipart form."""
    files = {"sid": (None, sid), "sn": (None, tracking_number), "lang": (None, "en")}
    try:
        print(f"    {DIM}→ Sending request...{RESET}")
        response = requests.post(
            CSSBUY_URL,
            headers=cssbuy_headers(token),
            files=files,
            timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
        )
        print(f"    {DIM}→ Response received: HTTP {response.status_code}{RESET}")
        if response.status_code != 200:
            return None, f"CSSBuy returned HTTP {response.status_code}."

        payload = response.json()
        if payload.get("code") not in (0, "0", None):
            return None, str(payload.get("msg") or "CSSBuy rejected the request.")

        data = payload.get("data", {})
        shipments = data.get("data", []) if isinstance(data, dict) else []
        if isinstance(shipments, dict):
            shipments = [shipments]
        if not shipments:
            return None, "No CSSBuy tracking record was found for that SID and tracking number."
        return shipments[0], None
    except requests.exceptions.ConnectTimeout:
        return None, "Connection to CSSBuy timed out."
    except requests.exceptions.ReadTimeout:
        return None, "CSSBuy took too long to respond."
    except requests.exceptions.ConnectionError:
        return None, "Could not connect to CSSBuy. Check your internet connection and try again."
    except requests.exceptions.RequestException as exc:
        return None, f"CSSBuy request error: {exc}"
    except ValueError:
        return None, "CSSBuy returned invalid JSON."


def post_17track(path: str, token: str, packages: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = requests.post(
            f"{TRACK17_BASE_URL}/{path}",
            headers={"17token": token, "Content-Type": "application/json"},
            json=packages,
            timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
        )
        if response.status_code != 200:
            return None, f"17TRACK returned HTTP {response.status_code}."
        return response.json(), None
    except requests.exceptions.Timeout:
        return None, "17TRACK took too long to respond."
    except requests.exceptions.RequestException as exc:
        return None, f"17TRACK request error: {exc}"
    except ValueError:
        return None, "17TRACK returned invalid JSON."


def register_17track(number: str, token: str, carrier: int | None = None) -> tuple[dict[str, Any] | None, str | None]:
    package: dict[str, Any] = {"number": number, "lang": "en", "destination_country": "NL", "auto_detection": carrier is None}
    if carrier is not None:
        package["carrier"] = carrier
    return post_17track("register", token, [package])


def get_17track(number: str, token: str, carrier: int | None = None) -> tuple[dict[str, Any] | None, str | None]:
    package: dict[str, Any] = {"number": number}
    if carrier is not None:
        package["carrier"] = carrier
    return post_17track("gettrackinfo", token, [package])


def accepted_item(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    accepted = (payload or {}).get("data", {}).get("accepted", [])
    return accepted[0] if isinstance(accepted, list) and accepted else None


def rejection_message(payload: dict[str, Any] | None) -> str | None:
    rejected = (payload or {}).get("data", {}).get("rejected", [])
    if not rejected:
        return None
    first = rejected[0]
    if isinstance(first, dict):
        return str(first.get("error") or first.get("message") or first)
    return str(first)


def parse_17track(payload: dict[str, Any] | None) -> dict[str, Any]:
    item = accepted_item(payload) or {}
    track_info = item.get("track_info") or {}
    tracking = track_info.get("tracking") or {}
    providers = tracking.get("providers") or []
    provider_entry = providers[0] if providers else {}
    provider = provider_entry.get("provider") or {}
    latest_status = track_info.get("latest_status") or {}
    return {
        "carrier": provider.get("name") or provider.get("alias") or "Unknown",
        "carrier_id": item.get("carrier"),
        "status": latest_status.get("status") or "Unknown",
        "event": track_info.get("latest_event"),
        "sync": provider_entry.get("latest_sync_time"),
    }


def display_cssbuy(shipment: dict[str, Any], tracking_number: str) -> None:
    section("📦 CSSBUY")
    print(f"\n  {GRAY}TRACKING{RESET}      {BOLD}{WHITE}{shipment.get('sn') or tracking_number}{RESET}")
    print(f"  {GRAY}DESTINATION{RESET}   {shipment.get('country') or 'Unknown'}")
    events = shipment.get("track") or []
    if not events:
        print(f"\n  {GRAY}No CSSBuy tracking events available.{RESET}")
        end_section()
        return
    print(f"\n  {BOLD}{WHITE}HISTORY{RESET}\n  {GRAY}{divider('─', 48)}{RESET}")
    for event in events:
        if not isinstance(event, dict):
            continue
        timestamp = friendly_time(event.get("track_time"), short=True)
        description = event.get("track_content") or event.get("content") or "Tracking event available"
        print(f"  {CYAN}●{RESET} {GRAY}{timestamp:<15}{RESET} {description}")
    end_section()


def display_17track(payload: dict[str, Any] | None) -> None:
    result = parse_17track(payload)
    icons = {"NotFound": "⚪", "InTransit": "🟡", "Delivered": "🟢", "Exception": "🔴", "Expired": "⚪", "AvailableForPickup": "🟢"}
    section("🚚 17TRACK")
    print(f"\n  {GRAY}CARRIER{RESET}       {BOLD}{WHITE}{result['carrier']}{RESET}")
    print(f"  {GRAY}CARRIER ID{RESET}    {result['carrier_id'] or 'Unknown'}")
    print(f"  {GRAY}STATUS{RESET}        {icons.get(result['status'], '⚪')} {result['status']}")
    event = result["event"]
    if isinstance(event, dict):
        description = event.get("description") or event.get("stage") or event.get("status") or "Tracking event available"
        event_time = event.get("time") or event.get("date")
        location = event.get("location")
        print(f"\n  {BOLD}{WHITE}LATEST EVENT{RESET}\n  {GRAY}{divider('─', 48)}{RESET}")
        print(f"  {GREEN}●{RESET} {description}")
        if event_time:
            print(f"    {GRAY}{friendly_time(event_time)}{RESET}")
        if location:
            print(f"    📍 {location}")
    elif event:
        print(f"\n  {GREEN}●{RESET} {event}")
    else:
        print(f"\n  {GRAY}No 17TRACK events available yet.{RESET}")
    if result["sync"]:
        print(f"\n  {GRAY}LAST SYNC{RESET}      {friendly_time(result['sync'])}")
    end_section()


def track_package(sid: str, number: str, cssbuy_token: str, track17_token: str) -> None:
    clear_screen()
    heading("📦  PACKAGE TRACKER")
    print(f"\n  {GRAY}CSSBuy SID{RESET}    {BOLD}{WHITE}{sid}{RESET}")
    print(f"  {GRAY}TRACKING{RESET}      {BOLD}{WHITE}{number}{RESET}\n")
    loading("Connecting to CSSBuy...")
    shipment, problem = get_cssbuy_history(sid, number, cssbuy_token)
    if shipment is None:
        error(problem or "CSSBuy request failed.")
    else:
        success("CSSBuy connected")
        display_cssbuy(shipment, number)

    print()
    loading("Registering with 17TRACK...")
    registration, problem = register_17track(number, track17_token)
    if problem:
        error(problem)
        return
    rejected = rejection_message(registration)
    if rejected:
        # 17TRACK returns this as a rejection when a number has already been
        # registered. It is safe to continue directly to gettrackinfo.
        if "has been registered" in rejected.lower() or "don't need to repeat" in rejected.lower():
            success("Already registered with 17TRACK")
        else:
            error(f"17TRACK registration failed: {rejected}")
            return
    else:
        success("17TRACK connected")
    loading("Getting carrier and status...")
    tracking, problem = get_17track(number, track17_token)
    if problem:
        error(problem)
        return
    if not accepted_item(tracking):
        error(rejection_message(tracking) or "17TRACK did not return a tracking record yet.")
        return
    display_17track(tracking)
    print(f"\n{CYAN}              ✓ TRACKING COMPLETE{RESET}\n")


def main() -> None:
    clear_screen()
    heading("📦  PACKAGE TRACKER")
    tokens = require_tokens()
    if tokens is None:
        input("\nPress ENTER to exit...")
        return
    cssbuy_token, track17_token = tokens

    while True:
        clear_screen()
        heading("📦  PACKAGE TRACKER")
        print(f"\n  {CYAN}[1]{RESET} Track a package\n  {CYAN}[Q]{RESET} Quit\n")
        choice = input("  Select › ").strip().lower()
        if choice == "q":
            return
        if choice != "1":
            error("Invalid option.")
            time.sleep(1)
            continue
        print()
        sid = input("  CSSBuy SID › ").strip()
        number = input("  Parcel tracking number › ").strip()
        if not sid or not number:
            error("Both CSSBuy SID and parcel tracking number are required.")
            time.sleep(2)
            continue
        track_package(sid, number, cssbuy_token, track17_token)
        action = input("  [R] Refresh  [N] New package  [Q] Quit › ").strip().lower()
        if action == "q":
            return
        if action == "r":
            track_package(sid, number, cssbuy_token, track17_token)
            input("\nPress ENTER to continue...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTracker closed.")
        sys.exit(0)
