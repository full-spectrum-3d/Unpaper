"""Globalna blokada PDFium.

PDFium nie jest bezpieczne wątkowo, a pypdfium2 tego nie pilnuje. Każde wywołanie pypdfium2
w procesie (walidacja uploadu, rasteryzacja do OCR) musi trzymać tę blokadę, bo żądania
obsługujemy równolegle w puli wątków.
"""

import threading

PDFIUM_LOCK = threading.Lock()
