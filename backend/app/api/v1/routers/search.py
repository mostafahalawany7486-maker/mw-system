from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.services.search_service import SearchService
from app.models.user import User

router = APIRouter(prefix="/search", tags=["Global Search"])


@router.get("")
def global_search(q: str = Query("", min_length=0), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Executive Dashboard Phase 3 — Global Search. No permission gate
    beyond being logged in: every category here already has its own
    permission-gated detail page, so search only ever surfaces a
    pointer (id + label + link), never the underlying record's data
    directly."""
    return SearchService(db).search(q)
