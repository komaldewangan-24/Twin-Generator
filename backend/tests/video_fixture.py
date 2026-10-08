import numpy as np
import cv2


def generate_test_video(path: str, seconds: float = 8.0, fps: float = 12.0, size=(480, 640)):
    """Create a synthetic 'room walkthrough' video with detectable furniture.

    Draws chair-like and table-like colored shapes that move slightly, so no
    real footage is needed to exercise the pipeline deterministically.
    """
    h, w = size
    w_out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    total = int(seconds * fps)

    def chair(x, y, color):
        # simple L-shaped chair made of rectangles
        body = (int(x), int(y), 40, 50)
        back = (int(x) + 5, int(y) - 25, 30, 30)
        seat = (body[0], body[1] + 40, 40, 10)
        cv2.rectangle(frame, body[:2], (body[0] + body[2], body[1] + body[3]), color, -1)
        cv2.rectangle(frame, back[:2], (back[0] + back[2], back[1] + back[3]), color, -1)
        cv2.rectangle(frame, seat[:2], (seat[0] + seat[2], seat[1] + seat[3]), (int(color[0] * 0.8), int(color[1] * 0.8), int(color[2] * 0.8)), -1)

    def table(x, y):
        cv2.rectangle(frame, (int(x), int(y)), (int(x) + 100, int(y) + 12), (90, 90, 90), -1)
        cv2.rectangle(frame, (int(x) + 10, int(y) + 12), (int(x) + 20, int(y) + 55), (60, 60, 60), -1)
        cv2.rectangle(frame, (int(x) + 80, int(y) + 12), (int(x) + 90, int(y) + 55), (60, 60, 60), -1)

    for i in range(total):
        frame = np.full((h, w, 3), (200, 200, 210), dtype="uint8")  # light wall
        cv2.putText(frame, f"frame {i}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        # floor line
        cv2.rectangle(frame, (0, int(h * 0.55)), (w, h), (160, 170, 160), -1)

        shift = int(i * 3 % 60)
        table(200 - shift // 2, int(h * 0.55))
        chair(120 - shift, int(h * 0.55) + 20, (200, 60, 60))
        chair(340 + shift, int(h * 0.55) + 25, (60, 60, 200))
        chair(430 + shift // 2, int(h * 0.62), (200, 160, 60))
        cv2.rectangle(frame, (int(w * 0.72), int(h * 0.72)), (int(w * 0.9), int(h * 0.92)), (140, 90, 50), -1)  # sofa-ish
        w_out.write(frame)

    w_out.release()
    return str(path)