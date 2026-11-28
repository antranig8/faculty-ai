from io import BytesIO
from zipfile import BadZipFile

from app.models.response_models import Slide
from app.services.presentation_preparer import _build_slide


class InvalidPresentationError(ValueError):
    pass


def parse_pptx_slides(file_bytes: bytes) -> list[Slide]:
    try:
        from lxml.etree import XMLSyntaxError
        from pptx import Presentation
        from pptx.exc import PackageNotFoundError
    except ImportError as exc:
        raise RuntimeError("PPTX parsing requires python-pptx. Install backend requirements first.") from exc

    try:
        presentation = Presentation(BytesIO(file_bytes))
    except (BadZipFile, PackageNotFoundError, XMLSyntaxError, KeyError, ValueError) as exc:
        raise InvalidPresentationError("The file is not a readable PowerPoint presentation.") from exc
    slides: list[Slide] = []

    for index, pptx_slide in enumerate(presentation.slides, start=1):
        text_runs: list[str] = []
        for shape in pptx_slide.shapes:
            if hasattr(shape, "text"):
                text = shape.text.strip()
                if text:
                    text_runs.append(text)

        title = text_runs[0].splitlines()[0] if text_runs else f"Slide {index}"
        content = "\n".join(text_runs[1:] if len(text_runs) > 1 else text_runs)
        slides.append(_build_slide(index, title, content))

    return slides

