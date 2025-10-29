from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.deps import *
from api.routes.common import to_video_shorts, VideoShort
from db.models import Author, AnnotationKind, MetaSource, VideoSource
from db.repositories.topics import TopicWithVideoCount

router = APIRouter(
  prefix="/authors",
  tags=["authors"],
)


class AuthorDetails(BaseModel):
  id: UUID
  url: str
  source: str
  verified: bool | None
  followers: int | None
  total_videos: int | None
  is_reviewed: bool
  created_at: datetime
  updated_at: datetime
  videos: list[VideoShort] | None = Field(None)
  topics: list[TopicWithVideoCount] | None = Field(None)


def to_author_details(author: Author) -> AuthorDetails:
  return AuthorDetails(
    id=author.id,
    url=author.url,
    source=author.source.value,
    verified=author.verified,
    followers=author.followers,
    total_videos=author.total_videos,
    is_reviewed=author.is_reviewed,
    created_at=author.created_at,
    updated_at=author.updated_at,
    videos=None,
    topics=None,
  )


class Authors(BaseModel):
  total: int
  authors: list[AuthorDetails]


@router.get("/", response_model_exclude_none=True)
async def get_authors(author_repo: AuthorRepository = Depends(get_author_repo)) -> Authors:
  authors = await author_repo.get_authors()

  return Authors(
    total=len(authors),
    authors=[to_author_details(a) for a in authors]
  )


@router.get("/{author_id}")
async def get_author(
    author_id: UUID,
    max_videos: int = Query(20, description="Return N latest videos"),
    author_repo: AuthorRepository = Depends(get_author_repo),
    video_repo: VideoRepository = Depends(get_video_repo),
    topic_repo: TopicRepository = Depends(get_topic_repo),
) -> AuthorDetails:
  author = await author_repo.get_author_by_id(author_id)
  if not author:
    raise HTTPException(status_code=404, detail="Author not found")

  videos = await video_repo.get_videos_by_author(
    author.id,
    load_annotations=True,
    annotations_to_load=[AnnotationKind.label, AnnotationKind.synopsis],
    load_meta=True,
    meta_to_load=[MetaSource.title, MetaSource.hashtag],
    max_videos=max_videos
  )

  topics = await topic_repo.get_total_videos_per_topic(author.id)

  author_details = to_author_details(author)
  author_details.videos = to_video_shorts(list(videos))
  author_details.topics = topics

  return author_details


@router.patch("/{author_id}")
async def patch_author(
    author_id: UUID,
    reviewed: bool | None = Query(None, description="Set Author reviewed status"),
    author_repo: AuthorRepository = Depends(get_author_repo)
) -> AuthorDetails:
  if reviewed is None:
    raise HTTPException(status_code=404, detail="Author reviewed is required")

  author = await author_repo.set_author_reviewed_status(author_id, reviewed)
  if not author:
    raise HTTPException(status_code=404, detail="Author not found")

  await author_repo.commit()

  return to_author_details(author)
