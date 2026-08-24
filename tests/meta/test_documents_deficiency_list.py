from app.meta.student_step_forms import (
    CTX_DOCUMENT_FIELD_LABELS_FA,
    CTX_DOCUMENT_FIELD_REJECTION_NOTES,
    CTX_DOCUMENTS_RESUBMIT_FIELDS,
    format_documents_deficiency_list,
)


def test_format_documents_deficiency_list_includes_officer_notes():
    text = format_documents_deficiency_list(
        {
            CTX_DOCUMENTS_RESUBMIT_FIELDS: ["photo", "id_card"],
            CTX_DOCUMENT_FIELD_LABELS_FA: {
                "photo": "عکس پرسنلی",
                "id_card": "شناسنامه",
            },
            CTX_DOCUMENT_FIELD_REJECTION_NOTES: {"photo": "تصویر تار است"},
        }
    )
    assert "1- عکس پرسنلی: تصویر تار است" in text
    assert "2- شناسنامه" in text
    assert "شناسنامه:" not in text


def test_format_documents_deficiency_list_empty():
    assert format_documents_deficiency_list({}) == "—"
