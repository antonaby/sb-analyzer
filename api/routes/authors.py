from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from api.deps import *
from api.models import AuthorDetails
from db.models import Author

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
  )


@router.get("/{author_id}")
async def get_author(author_id: UUID, author_repo: AuthorRepository = Depends(get_author_repo)) -> AuthorDetails:
  author = await author_repo.get_author_by_id(author_id)
  if not author:
    raise HTTPException(status_code=404, detail="Author not found")

  return _to_author_details(author)


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

  return _to_author_details(author)

