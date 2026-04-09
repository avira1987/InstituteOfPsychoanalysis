"""دانلود گزارش‌های مدیریتی — CSV / XLSX / PDF."""

from typing import Literal

import jdatetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_role
from app.database import get_db
from app.models.operational_models import User
from app.services import reports_service as rs
from app.services.reports_formatters import export_report

router = APIRouter(prefix="/api/reports", tags=["reports"])

ReportUser = Depends(
    require_role(
        "admin",
        "staff",
        "deputy_education",
        "monitoring_committee_officer",
        "finance",
    )
)


def _filename(prefix: str, shamsi_year: int, shamsi_month: int, ext: str) -> str:
    return f"{prefix}_{shamsi_year}_{shamsi_month:02d}.{ext}"


def _dispatch(rows: list, fmt: str, default_title: str, current_user: User) -> tuple[bytes, str, str]:
    name = (current_user.full_name_fa or current_user.username or "").strip()
    try:
        return export_report(
            rows,
            fmt,
            document_title=default_title,
            recipient_display_name=name,
        )  # type: ignore[arg-type]
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/shamsi-today")
async def shamsi_today(_: User = ReportUser):
    now = jdatetime.datetime.now()
    return {"year": now.year, "month": now.month, "day": now.day}


@router.get("/monthly/1-violations")
async def report1_violations(
    shamsi_year: int = Query(..., ge=1300, le=1500),
    shamsi_month: int = Query(..., ge=1, le=12),
    export_format: Literal["csv", "xlsx", "pdf"] = Query("pdf", alias="format"),
    include_sample_data: bool = Query(
        False,
        description="در صورت true، رکوردهای مربوط به دانشجویان نمونه آموزشی/بارگذاری تست هم در گزارش می‌آیند.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportUser,
):
    rows = await rs.build_report1_rows(
        db, shamsi_year, shamsi_month, include_sample_data=include_sample_data
    )
    data, mime, ext = _dispatch(rows, export_format, "گزارش ماهانه تخلف", current_user)
    fn = _filename("report1_violations", shamsi_year, shamsi_month, ext)
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{fn}"'},
    )


@router.get("/monthly/2-debt")
async def report2_debt(
    shamsi_year: int = Query(..., ge=1300, le=1500),
    shamsi_month: int = Query(..., ge=1, le=12),
    export_format: Literal["csv", "xlsx", "pdf"] = Query("pdf", alias="format"),
    include_sample_data: bool = Query(
        False,
        description="در صورت true، رکوردهای مربوط به دانشجویان نمونه آموزشی/بارگذاری تست هم در گزارش می‌آیند.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportUser,
):
    rows = await rs.build_report2_rows(
        db, shamsi_year, shamsi_month, include_sample_data=include_sample_data
    )
    data, mime, ext = _dispatch(rows, export_format, "گزارش ماهانه بدهکاری", current_user)
    fn = _filename("report2_debt", shamsi_year, shamsi_month, ext)
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{fn}"'},
    )


@router.get("/monthly/3-dropout")
async def report3_dropout(
    shamsi_year: int = Query(..., ge=1300, le=1500),
    shamsi_month: int = Query(..., ge=1, le=12),
    export_format: Literal["csv", "xlsx", "pdf"] = Query("pdf", alias="format"),
    include_sample_data: bool = Query(
        False,
        description="در صورت true، رکوردهای مربوط به دانشجویان نمونه آموزشی/بارگذاری تست هم در گزارش می‌آیند.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportUser,
):
    rows = await rs.build_report3_rows(
        db, shamsi_year, shamsi_month, include_sample_data=include_sample_data
    )
    data, mime, ext = _dispatch(rows, export_format, "گزارش ماهانه ریزش و انصراف", current_user)
    fn = _filename("report3_dropout", shamsi_year, shamsi_month, ext)
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{fn}"'},
    )


@router.get("/monthly/4-sla-delays")
async def report4_sla(
    shamsi_year: int = Query(..., ge=1300, le=1500),
    shamsi_month: int = Query(..., ge=1, le=12),
    export_format: Literal["csv", "xlsx", "pdf"] = Query("pdf", alias="format"),
    include_sample_data: bool = Query(
        False,
        description="در صورت true، رکوردهای مربوط به دانشجویان نمونه آموزشی/بارگذاری تست هم در گزارش می‌آیند.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportUser,
):
    rows = await rs.build_report4_rows(
        db, shamsi_year, shamsi_month, include_sample_data=include_sample_data
    )
    data, mime, ext = _dispatch(rows, export_format, "گزارش ماهانه تأخیر (نقض مهلت)", current_user)
    fn = _filename("report4_sla_delays", shamsi_year, shamsi_month, ext)
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{fn}"'},
    )


@router.get("/monthly/5-cancellations")
async def report5_cancellations(
    shamsi_year: int = Query(..., ge=1300, le=1500),
    shamsi_month: int = Query(..., ge=1, le=12),
    export_format: Literal["csv", "xlsx", "pdf"] = Query("pdf", alias="format"),
    include_sample_data: bool = Query(
        False,
        description="در صورت true، رکوردهای مربوط به دانشجویان نمونه آموزشی/بارگذاری تست هم در گزارش می‌آیند.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportUser,
):
    rows = await rs.build_report5_rows(
        db, shamsi_year, shamsi_month, include_sample_data=include_sample_data
    )
    data, mime, ext = _dispatch(rows, export_format, "گزارش کنسلی و غیبت", current_user)
    fn = _filename("report5_cancellations", shamsi_year, shamsi_month, ext)
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{fn}"'},
    )
