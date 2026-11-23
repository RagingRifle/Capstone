import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pdfminer.high_level import extract_text
text = extract_text('Sample Research Paper.pdf')
print(text)
