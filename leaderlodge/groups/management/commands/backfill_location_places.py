"""Interactive Places text-search backfill for group locations."""

from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q

from leaderlodge.groups.location_geo import (
    GEOCODE_SOURCE_BACKFILL_CONFIRMED,
    location_geo,
)
from leaderlodge.groups.location_place import set_location_place
from leaderlodge.groups.models import Group, Location
from leaderlodge.groups.places_client import (
    PlacesApiError,
    PlaceHit,
    search_places_text,
)
from leaderlodge.groups.sync_locations import resolve_group_by_name

HELP_TEXT = """
Commands:
  1-N     Assign result N (keep current location name)
  1a-Na   Assign result N and adopt Google place name
  /query  Search again with a new query (example: /Cafe 50s Venice CA)
  s       Skip this location (remembered in --skip-file if set)
  n       Skip without recording to skip-file
  q       Quit (progress already saved is kept)
  ?       Show this help
""".strip()


class Command(BaseCommand):
    help = (
        "Interactively geocode ungeocoded Locations via Places text search. "
        "You accept or reject each result (same idea as Map > Search > Assign)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--group",
            required=True,
            help="Group name whose location library will be updated.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max locations to process this session (0 = no limit).",
        )
        parser.add_argument(
            "--include-geocoded",
            action="store_true",
            help="Also offer already-geocoded locations (default: ungeocoded only).",
        )
        parser.add_argument(
            "--max-results",
            type=int,
            default=8,
            help="Places results to show per search (default 8).",
        )
        parser.add_argument(
            "--region-code",
            default="us",
            help="Places regionCode bias (default: us).",
        )
        parser.add_argument(
            "--skip-file",
            default="",
            help=(
                "JSON file of skipped location pks for resume "
                "(example: /tmp/manpearl_place_skips.json)."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Search and preview assigns without writing to the database.",
        )
        parser.add_argument(
            "--api-key",
            default="",
            help="Override Places API key (default: GOOGLE_PLACES_SERVER_API_KEY).",
        )

    def handle(self, *args, **options):
        api_key = self._resolve_api_key(options["api_key"])
        try:
            group = resolve_group_by_name(options["group"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        if not group.location_library_id:
            raise CommandError(f"Group {group.name!r} has no location library.")

        skip_path = (
            Path(options["skip_file"]).expanduser() if options["skip_file"] else None
        )
        skipped_pks = self._load_skips(skip_path)

        queryset = (
            Location.objects.filter(library=group.location_library)
            .annotate(game_count=Count("games"))
            .order_by("name", "pk")
        )
        if not options["include_geocoded"]:
            queryset = queryset.filter(Q(lat__isnull=True) | Q(lon__isnull=True))
        if skipped_pks:
            queryset = queryset.exclude(pk__in=skipped_pks)

        locations = list(queryset)
        if options["limit"] and options["limit"] > 0:
            locations = locations[: options["limit"]]

        if not locations:
            self.stdout.write(self.style.SUCCESS("Nothing to process."))
            return

        self.stdout.write(
            f"Group {group.name!r}: {len(locations)} location(s) to review "
            f"(dry_run={options['dry_run']})."
        )
        self.stdout.write(HELP_TEXT)
        self.stdout.write("")

        assigned = 0
        skipped = 0
        for index, location in enumerate(locations, start=1):
            action = self._process_one(
                location=location,
                index=index,
                total=len(locations),
                api_key=api_key,
                max_results=options["max_results"],
                region_code=options["region_code"],
                dry_run=options["dry_run"],
            )
            if action == "quit":
                self.stdout.write(self.style.WARNING("Quit requested."))
                break
            if action == "assign":
                assigned += 1
            elif action in {"skip", "skip_once"}:
                skipped += 1
                if action == "skip" and skip_path is not None:
                    skipped_pks.add(location.pk)
                    self._save_skips(skip_path, skipped_pks)

        self.stdout.write(
            self.style.SUCCESS(
                f"Session done: assigned={assigned}, skipped={skipped}, "
                f"remaining_in_queue={max(0, len(locations) - assigned - skipped)}"
            )
        )

    def _resolve_api_key(self, override: str) -> str:
        key = (
            override.strip()
            or getattr(settings, "GOOGLE_PLACES_SERVER_API_KEY", "")
            or getattr(settings, "GOOGLE_PLACES_API_KEY", "")
        )
        key = str(key or "").strip()
        if not key:
            raise CommandError(
                "No Places API key. Set GOOGLE_PLACES_SERVER_API_KEY "
                "(recommended for CLI) or pass --api-key. "
                "Browser-restricted GOOGLE_PLACES_API_KEY often fails from the server."
            )
        if (
            not override.strip()
            and not getattr(settings, "GOOGLE_PLACES_SERVER_API_KEY", "")
            and getattr(settings, "GOOGLE_PLACES_API_KEY", "")
        ):
            self.stdout.write(
                self.style.WARNING(
                    "Using GOOGLE_PLACES_API_KEY. If searches fail with REQUEST_DENIED, "
                    "create an IP-restricted GOOGLE_PLACES_SERVER_API_KEY instead."
                )
            )
        return key

    def _process_one(
        self,
        *,
        location: Location,
        index: int,
        total: int,
        api_key: str,
        max_results: int,
        region_code: str,
        dry_run: bool,
    ) -> str:
        pin = (
            "geocoded"
            if location.lat is not None and location.lon is not None
            else "no pin"
        )
        self.stdout.write("-" * 60)
        self.stdout.write(
            f"[{index}/{total}] {location.name!r} "
            f"(pk={location.pk}, games={location.game_count}, {pin})"
        )

        query = location.name
        while True:
            self.stdout.write(f"Search: {query!r}")
            try:
                hits = search_places_text(
                    api_key=api_key,
                    query=query,
                    max_result_count=max_results,
                    region_code=region_code,
                )
            except PlacesApiError as exc:
                self.stdout.write(self.style.ERROR(str(exc)))
                hits = []

            if not hits:
                self.stdout.write(self.style.WARNING("No results."))
            else:
                for i, hit in enumerate(hits, start=1):
                    self.stdout.write(f"  {i}. {hit.label()}")

            raw = input("Choose [1-N|1a-Na|/new query|s|n|q|?]: ").strip()
            if not raw:
                continue
            if raw == "?":
                self.stdout.write(HELP_TEXT)
                continue
            if raw.lower() == "q":
                return "quit"
            if raw.lower() == "s":
                self.stdout.write("Skipped (remembered).")
                return "skip"
            if raw.lower() == "n":
                self.stdout.write("Skipped (not remembered).")
                return "skip_once"
            if raw.startswith("/"):
                new_query = raw[1:].strip()
                if not new_query:
                    self.stdout.write("Enter a query after /.")
                    continue
                query = new_query
                continue

            adopt = False
            choice = raw.lower()
            if choice.endswith("a") and choice[:-1].isdigit():
                adopt = True
                choice = choice[:-1]
            if not choice.isdigit():
                self.stdout.write("Unrecognized command. Enter ? for help.")
                continue
            number = int(choice)
            if number < 1 or number > len(hits):
                self.stdout.write("Number out of range.")
                continue

            hit = hits[number - 1]
            self._assign(
                location=location,
                hit=hit,
                adopt_place_name=adopt,
                dry_run=dry_run,
            )
            return "assign"

    def _assign(
        self,
        *,
        location: Location,
        hit: PlaceHit,
        adopt_place_name: bool,
        dry_run: bool,
    ) -> None:
        geo = location_geo(
            lat=hit.lat,
            lon=hit.lon,
            city=hit.city,
            state=hit.state,
            country=hit.country,
            postal_code=hit.postal_code,
            street_address=hit.street_address,
            place_id=hit.place_id,
            geocode_source=GEOCODE_SOURCE_BACKFILL_CONFIRMED,
        )
        name_note = (
            f", rename to {hit.display_name!r}" if adopt_place_name else ", keep name"
        )
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Would assign {location.name!r} -> {hit.label()}{name_note}"
                )
            )
            return
        set_location_place(
            location=location,
            geo=geo,
            place_display_name=hit.display_name,
            adopt_place_name=adopt_place_name,
            force=True,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Assigned {location.name!r} -> {hit.label()}{name_note}"
            )
        )

    def _load_skips(self, path: Path | None) -> set[int]:
        if path is None or not path.is_file():
            return set()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Could not read skip file {path}: {exc}") from exc
        if isinstance(data, dict):
            raw = data.get("skipped_pks", [])
        else:
            raw = data
        try:
            return {int(pk) for pk in raw}
        except (TypeError, ValueError) as exc:
            raise CommandError(f"Invalid skip file format in {path}.") from exc

    def _save_skips(self, path: Path, skipped_pks: set[int]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"skipped_pks": sorted(skipped_pks)}
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
