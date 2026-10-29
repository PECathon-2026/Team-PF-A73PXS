# faces.py

## What it does
Finds faces in the page screenshot so the sanitizer can black them out.

## How
`find_faces(png)` decodes the PNG to grayscale with OpenCV, loads the Haar cascade `haarcascade_frontalface_default.xml` that ships with opencv-python, and calls `detectMultiScale` (scale factor 1.1, 4 neighbours, minimum 40x40 pixels). It returns (x, y, w, h) boxes. An image that cannot be decoded gives an empty list.

The sanitizer calls it only when the FACE rule is on. Separately, it always blacks out every `<video>` element and every image whose label looks like a person photo (`PERSON_IMAGE`).

## Likely judge questions
1. How accurate is it? Haar cascades are old and simple. They miss side profiles, small faces under 40 px, tilted or partly covered faces, and can fire on face-like patterns. See eval/results.json; face cases are not part of the text recall numbers.
2. Why not a neural network? It runs offline with no extra model download and no extra dependency. The video and person-image rules cover the main case without detection.
3. Does the face image leave the machine? No. Screenshots are never sent to the AI in the current prompt.
4. Is the cascade loaded each call? Yes. It is simple, not optimised.
