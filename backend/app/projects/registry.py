from fastapi import APIRouter
from .astronomy.project import project as astronomy
from .library.project import project as library

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
def list_projects():
    return [{"id": p["id"], "name": p["name"], "path": "/projects/" + p["id"]} for p in (astronomy(), library())]
