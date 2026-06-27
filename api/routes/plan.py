from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from api.ORM.models_sqlalchemy import Cuenta, Plan
from ..DAO.database import get_db
from api.DTO.models import MiPlanResponse, CambiarPlanRequest, PlanResponse

router = APIRouter()



@router.get("/MiPlan", response_model=MiPlanResponse)
def obtener_mi_plan(idcuenta: str = Query(...), db: Session = Depends(get_db)):
    cuenta = db.query(Cuenta).filter_by(IDCUENTA=idcuenta).first()

    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    
    plan = cuenta.PLAN_REL
    if not plan:
        raise HTTPException(status_code=404, detail="La cuenta no tiene un plan asociado")

    return MiPlanResponse(
        idplan=plan.IDPLAN,
        nombreplan=plan.NOMBREPLAN,
        comision=plan.COMISION,
        limitedominios=plan.LIMITEDOMINIOS
        
    )

@router.put("/CambiarPlan")
def cambiar_plan(data: CambiarPlanRequest, db: Session = Depends(get_db)):
    cuenta = db.query(Cuenta).filter_by(IDCUENTA=data.idcuenta).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    
    plan = db.query(Plan).filter_by(IDPLAN=data.idplan).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    cuenta.IDPLAN = data.idplan
    db.commit()
    db.refresh(cuenta)

    return {
        "message": f"Plan actualizado exitosamente para la cuenta {data.idcuenta}",
        "nuevo_plan": plan.NOMBREPLAN
    }

@router.get("/Planes", response_model=PlanResponse)
def obtener_plan(idplan: str = Query(...), db: Session = Depends(get_db)):
    plan = db.query(Plan).filter_by(IDPLAN=idplan).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    return PlanResponse(
        idplan=plan.IDPLAN,
        nombreplan=plan.NOMBREPLAN,
        comision=float(plan.COMISION),
        limitedominios=plan.LIMITEDOMINIOS
    )