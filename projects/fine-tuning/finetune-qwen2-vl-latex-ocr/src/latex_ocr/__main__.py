import argparse

from .infer import BASE_MODEL, load, transcribe


def main() -> None:
    ap = argparse.ArgumentParser(prog="latex_ocr")
    ap.add_argument("image", help="path to an image of a formula")
    ap.add_argument("--model", default=BASE_MODEL)
    ap.add_argument("--adapter")
    args = ap.parse_args()

    from PIL import Image

    processor, model = load(args.model, args.adapter)
    print(transcribe(processor, model, Image.open(args.image)))


if __name__ == "__main__":
    main()
