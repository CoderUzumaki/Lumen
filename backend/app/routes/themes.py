"""Themes CRUD (DATA-04).

Endpoints per BUILD.md:
- POST   /api/themes           body: ThemeCreate  → ThemeRead
- GET    /api/themes           → list[ThemeRead]
- PUT    /api/themes/{id}      body: ThemeUpdate  → ThemeRead
- DELETE /api/themes/{id}      → 204

On create + update the route generates an embedding for `description` (via
`EmbeddingClient`, ING-07) and upserts a doc into the `themes` Chroma
collection keyed on the theme's UUID. `themes.embedding_id` stores that id
so downstream retrieval (relevance engine, chat) can look it up without a
separate lookup table. Delete removes the Chroma doc too.

Ownership: every route resolves `user_id` from `require_auth` and scopes
queries to the owner. Cross-user access returns 404, matching the leak-
nothing rule from DATA-03.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db_session
from app.db.models.theme import Theme
from app.db.vectorstore import VectorStore
from app.schemas.theme import ThemeCreate, ThemeRead, ThemeUpdate
from app.utils.auth import UserContext, require_auth
from app.utils.embeddings import EmbeddingClient

router = APIRouter(prefix="/api/themes", tags=["themes"])


# --- Dependencies (overridable in tests) ------------------------------------

_default_embed_client = EmbeddingClient()


def get_embed_client() -> EmbeddingClient:
    return _default_embed_client


def get_themes_vector_store() -> VectorStore:
    return VectorStore("themes")


# --- Helpers ----------------------------------------------------------------


async def _get_owned_theme(theme_id: UUID, user_id: UUID, db: AsyncSession) -> Theme:
    q = select(Theme).where(Theme.id == theme_id, Theme.user_id == user_id)
    obj = (await db.execute(q)).scalar_one_or_none()
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="theme not found"
        )
    return obj


async def _index_theme(
    theme: Theme,
    *,
    embed: EmbeddingClient,
    store: VectorStore,
) -> None:
    """Compute the embedding for `theme.description` and upsert into Chroma."""
    vectors = await embed.embed([theme.description])
    doc_id = str(theme.id)
    store.upsert(
        ids=[doc_id],
        embeddings=vectors,
        metadatas=[{"user_id": str(theme.user_id), "description": theme.description}],
        documents=[theme.description],
    )
    theme.embedding_id = doc_id


# --- Endpoints --------------------------------------------------------------


@router.post("", response_model=ThemeRead, status_code=status.HTTP_201_CREATED)
async def create_theme(
    body: ThemeCreate,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
    embed: EmbeddingClient = Depends(get_embed_client),
    store: VectorStore = Depends(get_themes_vector_store),
) -> Theme:
    theme = Theme(
        user_id=user.user_id,
        description=body.description,
        weight=body.weight,
    )
    db.add(theme)
    await db.flush()  # populate theme.id before we hand it to Chroma
    await _index_theme(theme, embed=embed, store=store)
    await db.commit()
    await db.refresh(theme)
    return theme


@router.get("", response_model=list[ThemeRead])
async def list_themes(
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> list[Theme]:
    q = select(Theme).where(Theme.user_id == user.user_id).order_by(Theme.created_at)
    return list((await db.execute(q)).scalars().all())


@router.put("/{theme_id}", response_model=ThemeRead)
async def update_theme(
    theme_id: UUID,
    body: ThemeUpdate,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
    embed: EmbeddingClient = Depends(get_embed_client),
    store: VectorStore = Depends(get_themes_vector_store),
) -> Theme:
    theme = await _get_owned_theme(theme_id, user.user_id, db)
    changes = body.model_dump(exclude_unset=True)
    description_changed = (
        "description" in changes and changes["description"] != theme.description
    )
    for field, value in changes.items():
        setattr(theme, field, value)
    if description_changed:
        await _index_theme(theme, embed=embed, store=store)
    await db.commit()
    await db.refresh(theme)
    return theme


@router.delete(
    "/{theme_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_theme(
    theme_id: UUID,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
    store: VectorStore = Depends(get_themes_vector_store),
) -> Response:
    theme = await _get_owned_theme(theme_id, user.user_id, db)
    doc_id = theme.embedding_id or str(theme.id)
    await db.delete(theme)
    await db.commit()
    try:
        store.delete(ids=[doc_id])
    except Exception:
        # A Chroma outage shouldn't cause DELETE to appear failed after the
        # DB commit already succeeded. Log-and-skip; a cleanup job can
        # reconcile orphan vectors later.
        import logging

        logging.getLogger(__name__).exception(
            "themes.delete: chroma cleanup failed for %s", doc_id
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
