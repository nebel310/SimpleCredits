from 




router = APIRouter(
    prefix="/admin",
    tags=["Администрирование"],
    dependencies=[Depends(require_admin)]
)