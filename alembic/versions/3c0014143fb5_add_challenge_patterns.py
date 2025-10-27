"""Add Challenge Patterns

Revision ID: 3c0014143fb5
Revises: 600261bb7f73
Create Date: 2025-10-27 10:52:07.551421

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c0014143fb5'
down_revision: Union[str, Sequence[str], None] = '600261bb7f73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


GROUP_NAME = "TikTok Challenge Patterns"
PATTERNS = [
    # 🐾 Objects / Animals
    ("Find a video with a [color/trait] [animal].", "e.g., white cat; tiny dog"),
    ("Find a video with a [color/size] [object].", "e.g., red car; giant pizza"),
    ("Find a video where an [animal] is [doing something].", "e.g., dog dancing; cat sleeping"),
    ("Find a video showing a [brand/product].", "e.g., Nike shoes; iPhone"),

    # 💃 People / Actions
    ("Find a video where someone is [verb+ing].", "e.g., painting; running"),
    ("Find a video where someone is [action1] and [action2].", "e.g., cooking and talking"),
    ("Find a video where [two people] are [interaction].", "e.g., hugging; arguing"),
    ("Find a video with a [group size] of people doing [activity].", "e.g., group of friends dancing"),

    # 😂 Emotion / Reaction
    ("Find a video that makes you feel [emotion].", "e.g., laugh; cry; cringe"),
    ("Find a video where someone looks [emotion].", "e.g., surprised; angry"),
    ("Find a video that gives [vibe/mood].", "e.g., good vibes; cozy energy"),
    ("Find a video that looks [authentic/fake/staged].", "e.g., prank gone wrong; overly dramatic"),

    # 🎵 Sound / Music
    ("Find a video using a song with the word [keyword].", "e.g., 'love'; 'party'"),
    ("Find a video that includes the sound of [thing].", "e.g., dog barking; car honking"),
    ("Find a video synced perfectly to the [beat/rhythm].", "e.g., transitions timed to music"),

    # 🌍 Setting / Context
    ("Find a video filmed in [place/type of location].", "e.g., beach; kitchen"),
    ("Find a video recorded during [time/weather].", "e.g., night; rain"),
    ("Find a video showing [famous place/landmark].", "e.g., Eiffel Tower; Times Square"),
    ("Find a video with a [color/style] background.", "e.g., neon lights; pink wall"),
    ("Find a video that includes [text element].", "e.g., captions; subtitles"),

    # 🎭 Visual / Style-Based
    ("Find a video with a strong [color/theme].", "e.g., all pink; black-and-white"),
    ("Find a video that uses a [filter/effect].", "e.g., sparkle filter; slow motion"),
    ("Find a video that transitions between [scene1] and [scene2].", "e.g., pajama → outfit change"),
    ("Find a video that uses [editing technique].", "e.g., jump cuts; teleport transitions"),
    ("Find a video that shows a [mirror/reflection/silhouette].", "e.g., mirror selfie"),

    # 🕹️ Trend / Meme / Culture
    ("Find a video following the [current TikTok trend].", "e.g., NPC trend"),
    ("Find a video referencing [movie/TV show].", "e.g., Barbie; Wednesday"),
    ("Find a video using the sound [viral sound/meme].", "e.g., 'It’s corn!'"),
    ("Find a video recreating a [viral challenge].", "e.g., bottle flip challenge"),
    ("Find a video referencing [celebrity/influencer].", "e.g., Taylor Swift; MrBeast"),

    # 🧍 People / Identity / Expression
    ("Find a video where someone wears a [costume/outfit].", "e.g., superhero costume"),
    ("Find a video showing someone’s [routine/habit].", "e.g., morning routine"),
    ("Find a video where someone celebrates [occasion].", "e.g., birthday; graduation"),
    ("Find a video where someone shows their [talent/skill].", "e.g., makeup art; juggling"),
    ("Find a video where someone gives [advice/tips].", "e.g., life hacks; skincare advice"),

    # 🧠 Story / Message / Emotion
    ("Find a video that tells a story about [topic].", "e.g., friendship; heartbreak"),
    ("Find a video with a [twist ending/surprise reveal].", "e.g., unexpected prank"),
    ("Find a video that shows a [relatable situation].", "e.g., 'POV: you’re late for work'"),
    ("Find a video that spreads [positive action/message].", "e.g., kindness; motivation"),
    ("Find a video that feels [nostalgic/vintage/retro].", "e.g., 2000s vibe; VHS effect"),
]


def _get_or_create_group_id(conn) -> str:
    # Try to find an existing group by name
    existing = conn.execute(
        sa.text(
            'SELECT id::text FROM challenge_pattern_group WHERE name = :name LIMIT 1'
        ),
        {"name": GROUP_NAME},
    ).scalar()
    if existing:
        return existing

    # Insert new group; rely on DB defaults for id/created_at/updated_at
    return conn.execute(
        sa.text(
            'INSERT INTO challenge_pattern_group (name, created_at, updated_at) VALUES (:name, now(), now()) RETURNING id::text'
        ),
        {"name": GROUP_NAME},
    ).scalar_one()


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    group_id = _get_or_create_group_id(conn)

    # Insert patterns that don't already exist for this group (by exact value match)
    # Build a temp table of incoming values to check against
    existing_values = set(
        row[0]
        for row in conn.execute(
            sa.text(
                "SELECT value FROM challenge_patterns WHERE group_id = :gid"
            ),
            {"gid": group_id},
        ).fetchall()
    )

    to_insert = [(v, ex) for (v, ex) in PATTERNS if v not in existing_values]
    if not to_insert:
        return

    conn.execute(
        sa.text(
            """
            INSERT INTO challenge_patterns (group_id, value, example, created_at, updated_at)
            VALUES (:group_id, :value, :example, now(), now())
            """
        ),
        [{"group_id": group_id, "value": v, "example": ex} for (v, ex) in to_insert],
    )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()

    # Delete only this group; FK has ON DELETE CASCADE so patterns go with it
    conn.execute(
        sa.text("DELETE FROM challenge_pattern_group WHERE name = :name"),
        {"name": GROUP_NAME},
    )
