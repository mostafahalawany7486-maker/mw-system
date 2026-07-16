from fastapi import APIRouter
from app.api.v1.routers import auth, users, roles, organization, dashboard, system, owners

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
api_router.include_router(organization.router)
api_router.include_router(dashboard.router)
api_router.include_router(system.router)
api_router.include_router(owners.router)
