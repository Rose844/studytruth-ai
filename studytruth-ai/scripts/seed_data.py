"""
Seeds StudyTruth AI with realistic sample study material for:
  - Computer Networks        (includes an intentional VLAN conflict pair)
  - Deep Neural Networks
  - Data Structures and Algorithms

Run with:  python scripts/seed_data.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.db import init_db, clear_all               # noqa: E402
from app.core.document_processor import ingest_document  # noqa: E402
from app.core.vector_store import rebuild_vector_store   # noqa: E402

SAMPLE_DIR = ROOT / "sample_data"

# (relative path, subject, doc_type, academic_year, version, upload_date, doc_id)
DOCS = [
    ("computer_networks/syllabus_2025_v2.txt", "Computer Networks", "syllabus",
     "2025-26", "v2", "2025-08-01", "cn-syl-v2"),
    ("computer_networks/syllabus_2023_v1.txt", "Computer Networks", "syllabus",
     "2023-24", "v1", "2023-07-01", "cn-syl-v1"),
    ("computer_networks/lecture_notes_unit3.txt", "Computer Networks", "lecture_notes",
     "2025-26", "v1", "2025-09-10", "cn-notes-u3"),
    ("computer_networks/pyqs_cn.txt", "Computer Networks", "pyq",
     "2025-26", "v1", "2025-01-15", "cn-pyq-1"),
    ("computer_networks/assignment_1.txt", "Computer Networks", "assignment",
     "2025-26", "v1", "2025-09-05", "cn-assign-1"),
    ("computer_networks/lab_manual_vlan.txt", "Computer Networks", "lab_manual",
     "2025-26", "v1", "2025-09-12", "cn-lab-1"),
    ("computer_networks/notice_exam_schedule.txt", "Computer Networks", "notice",
     "2025-26", "v1", "2025-09-20", "cn-notice-1"),

    ("deep_neural_networks/syllabus.txt", "Deep Neural Networks", "syllabus",
     "2025-26", "v1", "2025-08-01", "dnn-syl-v1"),
    ("deep_neural_networks/lecture_notes.txt", "Deep Neural Networks", "lecture_notes",
     "2025-26", "v1", "2025-09-08", "dnn-notes-1"),
    ("deep_neural_networks/pyqs.txt", "Deep Neural Networks", "pyq",
     "2025-26", "v1", "2025-01-15", "dnn-pyq-1"),
    ("deep_neural_networks/assignment_2.txt", "Deep Neural Networks", "assignment",
     "2025-26", "v1", "2025-09-06", "dnn-assign-1"),
    ("deep_neural_networks/notice_exam_schedule.txt", "Deep Neural Networks", "notice",
     "2025-26", "v1", "2025-09-18", "dnn-notice-1"),

    ("dsa/syllabus.txt", "Data Structures and Algorithms", "syllabus",
     "2025-26", "v1", "2025-08-01", "dsa-syl-v1"),
    ("dsa/lecture_notes.txt", "Data Structures and Algorithms", "lecture_notes",
     "2025-26", "v1", "2025-09-09", "dsa-notes-1"),
    ("dsa/pyqs.txt", "Data Structures and Algorithms", "pyq",
     "2025-26", "v1", "2025-01-15", "dsa-pyq-1"),
    ("dsa/assignment_3.txt", "Data Structures and Algorithms", "assignment",
     "2025-26", "v1", "2025-09-07", "dsa-assign-1"),
    ("dsa/notice_exam_schedule.txt", "Data Structures and Algorithms", "notice",
     "2025-26", "v1", "2025-09-19", "dsa-notice-1"),
]


def main():
    init_db()
    clear_all()
    print("Seeding StudyTruth AI sample data...\n")
    ingested, skipped = 0, []
    for rel_path, subject, doc_type, year, version, date, doc_id in DOCS:
        file_path = SAMPLE_DIR / rel_path
        if not file_path.exists():
            print(f"  ✗ SKIPPED (file not found): {rel_path}")
            skipped.append(rel_path)
            continue
        meta = ingest_document(
            file_path=file_path,
            filename=file_path.name,
            subject=subject,
            doc_type=doc_type,
            academic_year=year,
            version=version,
            upload_date=date,
            doc_id=doc_id,
        )
        print(f"  ✓ {meta['filename']:<32} subject={subject:<32} type={doc_type:<12} chunks={meta['chunk_count']}")
        ingested += 1

    rebuild_vector_store()
    print(f"\nSeeding complete: {ingested} documents ingested, {len(skipped)} skipped.")
    if skipped:
        print("The app will still work with what was seeded - the skipped files just weren't found at:")
        for rel_path in skipped:
            print(f"    sample_data/{rel_path}")
    print("Try: uvicorn app.main:app --reload --port 8000 (from the backend/ folder)")


if __name__ == "__main__":
    main()
