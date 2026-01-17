import argparse
from typing import List, Tuple

from app.core.database import get_session_local
from app.models.comic import Comic
from app.models.master_data import Style, Genre

import core


def _map_comic_values(db, comic: Comic) -> Tuple[str, List[str]]:
    style_value = str(comic.style or "").strip()
    genre_values = comic.genre if isinstance(comic.genre, list) else []

    style_name = None
    if style_value.isdigit() and style_value not in core.COMIC_STYLES:
        style_row = db.query(Style).filter(Style.id == int(style_value)).first()
        style_name = style_row.name if style_row else None
    else:
        style_name = style_value or None

    genre_names: List[str] = []
    numeric_genres = [int(g) for g in genre_values if str(g).isdigit()]
    if numeric_genres:
        genre_rows = db.query(Genre).filter(Genre.id.in_(numeric_genres)).all()
        genre_names = [g.name for g in genre_rows]
    else:
        genre_names = [str(g) for g in genre_values]

    mapped_style_id = core.map_style_id(style_value, style_name)
    mapped_genres = core.map_nuance_ids(
        nuance_ids=[str(g) for g in genre_values],
        nuance_names=genre_names,
    )

    return mapped_style_id, mapped_genres


def migrate(dry_run: bool = True, batch_size: int = 200) -> None:
    session = get_session_local()()
    try:
        comics = session.query(Comic).all()
        updated = 0

        for idx, comic in enumerate(comics, start=1):
            mapped_style_id, mapped_genres = _map_comic_values(session, comic)

            style_changed = str(comic.style or "") != mapped_style_id
            genre_changed = comic.genre != mapped_genres

            if style_changed or genre_changed:
                updated += 1
                if not dry_run:
                    comic.style = mapped_style_id
                    comic.genre = mapped_genres

            if not dry_run and idx % batch_size == 0:
                session.commit()

        if not dry_run:
            session.commit()

        mode = "DRY-RUN" if dry_run else "COMMITTED"
        print(f"[{mode}] Scanned {len(comics)} comics, updated {updated}.")
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill comic.style and comic.genre to core-mapped IDs",
    )
    parser.add_argument("--commit", action="store_true", help="Apply changes to database")
    parser.add_argument("--batch-size", type=int, default=200, help="Commit batch size")
    args = parser.parse_args()

    migrate(dry_run=not args.commit, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
