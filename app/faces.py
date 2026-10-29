import cv2
import numpy as np


def find_faces(png: bytes) -> list[tuple[int, int, int, int]]:
    """Face boxes (x, y, w, h) in screenshot pixels, using OpenCV's bundled Haar cascade."""
    image = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return []
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    boxes = cascade.detectMultiScale(image, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
    return [tuple(int(v) for v in b) for b in boxes]
