"""Read-only scan of every GET endpoint in the official Talk OpenAPI spec,
to find out what the configured KTALK_API_KEY can actually reach.

Calls every GET path with placeholder path params (real ones where we know
them: a real room name / conference id, if set via env). Never calls a
non-GET method, so nothing here can create, modify or delete anything.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv

load_dotenv()

from ktalk_mcp_apikey.client import client_from_env  # noqa: E402

FAKE = "00000000-0000-0000-0000-000000000000"
KNOWN_ROOM = os.environ.get("PROBE_ROOM_NAME", "aith-run-257")
KNOWN_CONF = os.environ.get("PROBE_CONFERENCE_KEY", "A6oq1CfPcLYTeEnNieTP")

PATH_PARAM_VALUES = {
    "roomName": KNOWN_ROOM,
    "recordingKey": KNOWN_CONF,
    "conferenceKey": KNOWN_CONF,
    "userKey": FAKE,
    "userRef": FAKE,
    "email": "probe@example.com",
    "eventId": FAKE,
    "kioskId": FAKE,
    "surveyId": FAKE,
    "roleId": "user",
    "calendarServerId": FAKE,
    "taskKey": FAKE,
    "webhookKey": FAKE,
    "key": FAKE,
    "defaultRoleType": "user",
    "summarizationType": "shortSummary",
    "qualityName": "900p",
}

# GET paths from talk.public.api-api-2.json, trimmed of the "/api" prefix
# the client already adds via base_url.
GET_PATHS = [
    "/domain/applications",
    "/domain/applications/access-info",
    "/recordings/{recordingKey}/summary",
    "/EmailCalendar/{email}",
    "/EmailCalendar/{email}/{eventId}/recurrence",
    "/DeepFakeDetector/conference/{conferenceKey}/report",
    "/DeepFakeDetector/conference/{conferenceKey}/task/{taskKey}/file",
    "/DeepFakeDetector/conference/{conferenceKey}/tasks/files",
    "/DeepFakeDetector/statistic",
    "/Domain/recordings",
    "/Domain/recordings/v2",
    "/Domain/recordings/{recordingKey}/participants",
    "/Domain/recordings/{recordingKey}",
    "/recordings/{recordingKey}/transcript",
    "/recordings/{recordingKey}/summary/{summarizationType}",
    "/recordings/v2/{recordingKey}/summary",
    "/Kiosk",
    "/Kiosk/search",
    "/Kiosk/{kioskId}",
    "/Kiosk/news",
    "/Kiosk/screensavers/domain",
    "/Kiosk/wallpapers/domain",
    "/Rooms/{roomName}",
    "/domain/surveys",
    "/domain/surveys/{surveyId}",
    "/AuditLog",
    "/ClientsTelemetry",
    "/ClientsTelemetry/v2",
    "/ConferenceReports/{conferenceKey}/messages",
    "/ConferenceReports/{conferenceKey}/questions",
    "/ConferenceReports/{conferenceKey}/participants",
    "/ConferenceReports/{conferenceKey}/activities",
    "/ConferencesHistory/{conferenceKey}",
    "/ConferencesHistory/v2/{conferenceKey}",
    "/domain/conferencesHistory",
    "/RoomReport/statistics",
    "/RoomReport/{roomName}/statistics/report",
    "/Users",
    "/Users/scan",
    "/Users/{userKey}",
    "/Users/{userKey}/roles",
    "/permissions",
    "/roles",
    "/roles/{roleId}",
    "/roles/default",
    "/roles/defaults/{defaultRoleType}",
    "/roles/defaults",
    "/Domain/statistics",
    "/Domain/statisticsTotal",
    "/domain/stats/online",
    "/domain/stats/kiosks/online",
    "/domain/stats/conferences/online",
    "/domain/stats/streams/online",
    "/domain/stats/recordings/online",
    "/domain/stats/recordings/totalSize",
    "/domain/stats/kiosks",
    "/domain/stats/recordings",
    "/domain/stats/whiteboards",
    "/domain/stats/deepfakeDetections",
    "/domain/stats/tariffExpirationDate",
    "/domain/stats/conferences",
    "/Calendar/servers",
    "/Calendar/servers/{calendarServerId}",
]

# Required query params some GETs demand -- fill with harmless placeholders
# so a 400 (bad request) doesn't masquerade as a 403 (no scope).
REQUIRED_QUERY = {
    "/EmailCalendar/{email}": {"start": "2026-01-01T00:00:00Z"},
    "/RoomReport/statistics": {"from": "2026-01-01T00:00:00Z"},
    "/RoomReport/{roomName}/statistics/report": {"from": "2026-01-01T00:00:00Z"},
}


def fill(path: str) -> str:
    for name, val in PATH_PARAM_VALUES.items():
        path = path.replace("{" + name + "}", val)
    return path


async def main():
    c = client_from_env()
    results = []
    for raw_path in GET_PATHS:
        path = fill(raw_path)
        params = REQUIRED_QUERY.get(raw_path)
        try:
            await c.request("GET", path, params=params)
            results.append((raw_path, "OK (200)"))
        except Exception as e:  # noqa: BLE001
            status = getattr(e, "status", None)
            results.append((raw_path, f"{status or 'ERR'}"))

    ok = [r for r in results if r[1].startswith("OK")]
    forbidden = [r for r in results if r[1] == "403"]
    other = [r for r in results if r not in ok and r not in forbidden]

    print(f"\n=== Accessible ({len(ok)}) ===")
    for p, s in ok:
        print(f"  {s:10s} {p}")
    print(f"\n=== Forbidden / no scope (403) ({len(forbidden)}) ===")
    for p, s in forbidden:
        print(f"  {s:10s} {p}")
    print(f"\n=== Other (404/400/etc — key accepted, different reason) ({len(other)}) ===")
    for p, s in other:
        print(f"  {s:10s} {p}")


if __name__ == "__main__":
    asyncio.run(main())
