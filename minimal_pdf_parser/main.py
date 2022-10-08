import io
from pathlib import Path

from parser import PDFParser

SPACE = 0x20

STARTXREF = b'startxref'
LEN_STARTXREF = len(STARTXREF)



def main(path: Path):
    with path.open('rb') as stream:
        parser = PDFParser(stream)
        startxref = parser._find_start_xref()
        while True:
            stream.seek(startxref, io.SEEK_SET)
            break
        print(stream.read())


if __name__ == '__main__':
    main(Path(__file__).parent / "fixture/rfc776.txt.pdf")
