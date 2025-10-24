"""Add Topics

Revision ID: da9abe97c336
Revises: 929c1226709f
Create Date: 2025-10-24 14:16:31.061680

"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'da9abe97c336'
down_revision: Union[str, Sequence[str], None] = '929c1226709f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

topic_names = [
    "cats", "dogs", "birds", "wild animals", "sea life", "farm animals", "reptiles", "insects",
    "nature", "landscapes", "weather", "flowers", "cars", "motorcycles", "trucks", "racing",
    "trains", "airplanes", "boats", "machinery", "tech gadgets", "drones", "esports", "Dota 2",
    "Fortnite", "Minecraft", "Roblox", "FPS games", "strategy games", "simulation games",
    "mobile gaming", "retro games", "dancing", "hip hop", "pop music", "rock", "classical",
    "singing", "instruments", "live performances", "DJ / mixing", "music memes", "comedy",
    "fails", "pranks", "reactions", "animal memes", "relatable moments", "viral trends",
    "parody videos", "weird clips", "science", "history", "tech tutorials", "math tricks",
    "language learning", "psychology", "documentaries", "experiments", "explainers", "cooking",
    "baking", "street food", "recipes", "drinks & coffee", "fitness", "fashion", "skincare",
    "home hacks", "travel", "daily routines", "movie clips", "anime", "TV shows", "celebrity moments",
    "trailers", "fan edits", "cosplay", "voice acting", "drawing", "painting", "photography",
    "editing", "design", "DIY crafts", "animation", "3D art", "makeup art", "sports", "parkour",
    "stunts", "travel adventures", "mountains", "surfing", "skateboarding", "challenges", "fails",
    "friendship", "romance", "family", "kids", "kindness", "motivation", "inspiration", "life stories",
    "calm", "cozy", "aesthetic", "minimalism", "ambient music", "rain sounds", "study vibes", "night walks",
    "sunsets"
]


def upgrade() -> None:
    """Upgrade schema."""
    # Prepare insert statement
    topics_table = sa.table(
        'topics',
        sa.column('name', sa.String),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )
    # Generate insert data
    data = [
        {"id": sa.text("uuid_generate_v1mc()"), "name": name, "created_at": datetime.now(timezone.utc)}
        for name in topic_names
    ]
    op.bulk_insert(topics_table, data)


def downgrade() -> None:
    """Downgrade schema."""
    connection = op.get_bind()
    connection.execute(
        sa.text("DELETE FROM topics WHERE name = ANY(:names)"),
        {"names": topic_names}
    )
