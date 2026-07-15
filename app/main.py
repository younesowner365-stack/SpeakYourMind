import io
import json
import os
import secrets
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openpyxl import Workbook
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
QUESTIONS_PATH = BASE_DIR / "data" / "questions.json"
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not DATABASE_URL:
    raise RuntimeError("La variable d'environnement DATABASE_URL est absente.")
if not ADMIN_PASSWORD:
    raise RuntimeError("La variable d'environnement ADMIN_PASSWORD est absente.")

app = FastAPI(title="Speak Your Mind")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
security = HTTPBasic()

with QUESTIONS_PATH.open(encoding="utf-8") as file:
    QUESTIONS = json.load(file)

QUESTION_BY_ID = {question["id"]: question for question in QUESTIONS}


def get_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    username_ok = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    password_ok = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects.",
            headers={"WWW-Authenticate": 'Basic realm="SpeakYourMind Admin"'},
        )
    return credentials.username


def init_db() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS submissions (
                    id BIGSERIAL PRIMARY KEY,
                    submitted_at TIMESTAMPTZ NOT NULL,
                    is_test BOOLEAN NOT NULL DEFAULT FALSE
                )
                """
            )
            cursor.execute(
                """
                ALTER TABLE submissions
                ADD COLUMN IF NOT EXISTS is_test BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS answers (
                    id BIGSERIAL PRIMARY KEY,
                    submission_id BIGINT NOT NULL
                        REFERENCES submissions(id)
                        ON DELETE CASCADE,
                    question_id INTEGER NOT NULL,
                    answer_text TEXT,
                    score INTEGER CHECK (score BETWEEN 1 AND 5),
                    comment TEXT
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_answers_submission ON answers(submission_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_answers_question ON answers(question_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_submissions_is_test ON submissions(is_test)"
            )


init_db()


class AnswerPayload(BaseModel):
    question_id: int
    score: int | None = Field(default=None, ge=1, le=5)
    answer_text: str | None = None
    comment: str | None = None


class SubmissionPayload(BaseModel):
    answers: list[AnswerPayload]
    is_test: bool = False


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"total_questions": len(QUESTIONS)},
    )


@app.get("/survey", response_class=HTMLResponse)
async def survey(request: Request, test: bool = Query(default=False)):
    return templates.TemplateResponse(
        request=request,
        name="survey.html",
        context={"questions": QUESTIONS, "is_test": test},
    )


@app.get("/thanks", response_class=HTMLResponse)
async def thanks(request: Request, test: bool = Query(default=False)):
    return templates.TemplateResponse(
        request=request,
        name="thanks.html",
        context={"is_test": test},
    )


@app.post("/api/submit")
async def submit(payload: SubmissionPayload):
    if not payload.answers:
        return JSONResponse({"detail": "Aucune réponse reçue."}, status_code=400)

    for answer in payload.answers:
        question = QUESTION_BY_ID.get(answer.question_id)
        if question is None:
            return JSONResponse(
                {"detail": f"La question {answer.question_id} n'existe pas."},
                status_code=400,
            )
        if question["type"] == "likert" and answer.score is None:
            return JSONResponse(
                {"detail": f"Une note est requise pour la question {answer.question_id}."},
                status_code=400,
            )

    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO submissions (submitted_at, is_test)
                    VALUES (%s, %s)
                    RETURNING id
                    """,
                    (datetime.now(timezone.utc), payload.is_test),
                )
                submission_id = cursor.fetchone()["id"]

                for answer in payload.answers:
                    cursor.execute(
                        """
                        INSERT INTO answers (
                            submission_id, question_id, answer_text, score, comment
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            submission_id,
                            answer.question_id,
                            (answer.answer_text or "").strip() or None,
                            answer.score,
                            (answer.comment or "").strip() or None,
                        ),
                    )

        return {"success": True, "submission_id": submission_id, "is_test": payload.is_test}

    except psycopg.Error as exc:
        print(f"Database error: {exc}")
        return JSONResponse(
            {"detail": "Une erreur est survenue pendant l'enregistrement des réponses."},
            status_code=500,
        )


def load_dashboard_data():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS total FROM submissions WHERE is_test = FALSE"
            )
            total = cursor.fetchone()["total"]

            cursor.execute(
                "SELECT COUNT(*) AS total FROM submissions WHERE is_test = TRUE"
            )
            test_total = cursor.fetchone()["total"]

            cursor.execute(
                """
                SELECT
                    a.question_id,
                    COUNT(a.score) AS responses,
                    ROUND(AVG(a.score)::numeric, 2) AS average
                FROM answers AS a
                JOIN submissions AS s ON s.id = a.submission_id
                WHERE a.score IS NOT NULL AND s.is_test = FALSE
                GROUP BY a.question_id
                ORDER BY a.question_id
                """
            )
            rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT ROUND(AVG(a.score)::numeric, 2) AS average
                FROM answers AS a
                JOIN submissions AS s ON s.id = a.submission_id
                WHERE a.score IS NOT NULL AND s.is_test = FALSE
                """
            )
            global_average = cursor.fetchone()["average"]

    stats = []
    section_values = defaultdict(list)
    for row in rows:
        question = QUESTION_BY_ID.get(row["question_id"])
        if question:
            average = float(row["average"]) if row["average"] is not None else None
            stats.append(
                {
                    "question_id": row["question_id"],
                    "section": question["section"],
                    "question": question["question"],
                    "responses": row["responses"],
                    "average": average,
                }
            )
            if average is not None:
                section_values[question["section"]].append(average)

    section_stats = [
        {
            "section": section,
            "average": round(sum(values) / len(values), 2),
            "satisfaction": round((sum(values) / len(values)) / 5 * 100, 1),
        }
        for section, values in section_values.items()
    ]

    global_average_float = float(global_average) if global_average is not None else 0.0
    satisfaction_rate = round(global_average_float / 5 * 100, 1) if global_average_float else 0.0
    return total, test_total, global_average_float, satisfaction_rate, stats, section_stats


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request, _admin: str = Depends(require_admin)):
    total, test_total, global_average, satisfaction_rate, stats, section_stats = load_dashboard_data()
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "total_submissions": total,
            "test_submissions": test_total,
            "global_average": global_average,
            "satisfaction_rate": satisfaction_rate,
            "stats": stats,
            "section_stats": section_stats,
        },
    )


@app.post("/admin/delete-tests")
async def delete_tests(_admin: str = Depends(require_admin)):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM submissions WHERE is_test = TRUE RETURNING id")
            deleted = len(cursor.fetchall())
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin/export.xlsx")
async def export_excel(_admin: str = Depends(require_admin)):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Réponses officielles"
    worksheet.append(
        [
            "Submission ID",
            "Date UTC",
            "Question ID",
            "Section",
            "Question",
            "Note",
            "Réponse ouverte",
            "Commentaire",
        ]
    )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    s.id AS submission_id,
                    s.submitted_at,
                    a.question_id,
                    a.score,
                    a.answer_text,
                    a.comment
                FROM answers AS a
                JOIN submissions AS s ON s.id = a.submission_id
                WHERE s.is_test = FALSE
                ORDER BY s.id, a.question_id
                """
            )
            rows = cursor.fetchall()

    for row in rows:
        question = QUESTION_BY_ID.get(row["question_id"], {})
        worksheet.append(
            [
                row["submission_id"],
                row["submitted_at"].isoformat() if row["submitted_at"] else "",
                row["question_id"],
                question.get("section", ""),
                question.get("question", ""),
                row["score"],
                row["answer_text"],
                row["comment"],
            ]
        )

    for column in worksheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column)
        worksheet.column_dimensions[column[0].column_letter].width = min(max_length + 2, 60)

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=speak-your-mind-reponses.xlsx"},
    )
