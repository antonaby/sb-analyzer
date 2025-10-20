from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from api.deps import *
from api.models import AuthorDetails, AuthorVideoDetails
from db.models import Author, AnnotationKind, MetaSource, Video

router = APIRouter(
  prefix="/authors",
  tags=["authors"],
)


def _to_author_details(author: Author) -> AuthorDetails:
  return AuthorDetails(
    id=author.id,
    url=author.url,
    source=author.source,
    verified=author.verified,
    followers=author.followers,
    total_videos=author.total_videos,
    is_reviewed=author.is_reviewed,
    created_at=author.created_at,
    updated_at=author.updated_at,
    videos=[]
  )


def _to_video_details(video: Video) -> AuthorVideoDetails:
  title = "no title"
  label = "no label"
  synopsis = "no synopsis"
  hashtags = []

  for annotation in video.annotations:
    if annotation.kind == AnnotationKind.label:
      label = annotation.value
    if annotation.kind == AnnotationKind.synopsis:
      synopsis = annotation.value

  for meta in video.video_meta:
    if meta.source == MetaSource.title:
      title = meta.value
    if meta.source == MetaSource.hashtag:
      hashtags.append(meta.value)

  return AuthorVideoDetails(
    video_id=video.id,
    url=video.url,
    source=video.source,
    title=title,
    uploaded_at=video.uploaded_at,
    likes=video.likes,
    views=video.views,
    comments=video.comments,
    hashtags=hashtags,
    label=label,
    synopsis=synopsis
  )


@router.get("/{author_id}")
async def get_author(
    author_id: UUID,
    max_videos: int = Query(20, description="Return N latest videos"),
    author_repo: AuthorRepository = Depends(get_author_repo),
    video_repo: VideoRepository = Depends(get_video_repo)
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

  author_details = _to_author_details(author)
  videos_details = [_to_video_details(v) for v in videos]
  author_details.videos = videos_details

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

  return _to_author_details(author)
