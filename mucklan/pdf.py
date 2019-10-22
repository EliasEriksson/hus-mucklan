from .exceptions import NoPriceFound
from io import BytesIO
import pdftotext
import re


def read(bites: bytes) -> float:
    with BytesIO(bites) as io:
        pdf = pdftotext.PDF(io)
    for page in pdf:
        result = re.search(r"\s\d{5,25}\s+(\d+)\s(\d{2})\s", page)
        if result:
            return float(".".join(result.groups()))
        result = re.search(r"\s\d{5,25}\s+#\s+(\d+)\s(\d+)\s", page)
        if result:
            return float(".".join(result.groups()))
        result = re.search(r"Summa att betala\s+(\d+)\.(\d+)", page)
        if result:
            return float(".".join(result.groups()))
        result = re.search(r"TOTALSUMMA\s+(\d+),(\d+)\s+kr", page)
        if result:
            return float(".".join(result.groups()))
    raise NoPriceFound("No price on the bill could be found in the pdf.")
