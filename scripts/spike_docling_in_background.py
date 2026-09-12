import time
from fastapi import FastAPI, BackgroundTasks
from app.infrastructure.ocr.docling_engine import DoclingEngine

app = FastAPI()

# Created once, at import time — same pattern as our composition root,
# avoiding creating a new DocumentConverter on every request.
engine = DoclingEngine()


def run_real_docling_extraction():
    # flush=True on every print, same lesson learned from our very
    # first BackgroundTasks spike — without it, output can sit in
    # an invisible buffer and we'd wrongly conclude nothing happened.
    print("BACKGROUND TASK: starting real Docling extraction...", flush=True)
    start = time.time()

    result = engine.extract("tests/fixtures/Fiche_PFA.pdf")

    elapsed = time.time() - start
    print(
        f"BACKGROUND TASK: finished in {elapsed:.2f} seconds. Extracted {len(result)} characters.",
        flush=True,
    )


@app.post("/trigger")
def trigger_extraction(background_tasks: BackgroundTasks):
    print("ROUTE: request received, scheduling background task...", flush=True)
    background_tasks.add_task(run_real_docling_extraction)
    print("ROUTE: returning response now.", flush=True)
    return {"status": "triggered"}
