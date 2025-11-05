import cv2
import numpy as np
import math

class AirCanvas:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.canvas = None
        self.drawing = False
        self.prev_x = self.prev_y = None
        self.pen_enabled = False
        self.whiteboard_mode = False

        # HSV range for blue marker detection
        self.lower_color = np.array([100, 50, 50])
        self.upper_color = np.array([130, 255, 255])

        # Drawing colors
        self.colors = [
            (255, 0, 0),
            (0, 255, 0),
            (0, 0, 255),
            (255, 255, 0),
            (255, 0, 255)
        ]
        self.current_color_idx = 0
        self.brush_size = 5
        self.color_palette_size = 40

        # Shape drawing state
        self.points = []
        self.mode = "normal"
        self.temp_canvas = None
        
        # Undo/Redo feature - store canvas states
        self.canvas_history = []
        self.redo_history = []
        self.max_history = 20  # Maximum undo steps

    def save_canvas_state(self):
        """Save current canvas state for undo functionality"""
        if self.canvas is not None:
            # Keep only last max_history states
            if len(self.canvas_history) >= self.max_history:
                self.canvas_history.pop(0)
            self.canvas_history.append(self.canvas.copy())
            # Clear redo history when new action is performed
            self.redo_history.clear()

    def undo(self):
        """Restore previous canvas state"""
        if len(self.canvas_history) > 0:
            # Save current state to redo history before undoing
            self.redo_history.append(self.canvas.copy())
            if len(self.redo_history) > self.max_history:
                self.redo_history.pop(0)
            
            self.canvas = self.canvas_history.pop()
            print("Undo successful")
        else:
            print("Nothing to undo")

    def redo(self):
        """Restore next canvas state (redo)"""
        if len(self.redo_history) > 0:
            # Save current state back to undo history
            self.canvas_history.append(self.canvas.copy())
            if len(self.canvas_history) > self.max_history:
                self.canvas_history.pop(0)
            
            self.canvas = self.redo_history.pop()
            print("Redo successful")
        else:
            print("Nothing to redo")

    def setup_ui(self, frame):
        h, w = frame.shape[:2]
        # Color palette
        for i, c in enumerate(self.colors):
            x = 50 + i * (self.color_palette_size + 10)
            cv2.rectangle(frame,
                          (x, 10),
                          (x + self.color_palette_size, 10 + self.color_palette_size),
                          c, -1)
            if i == self.current_color_idx:
                cv2.rectangle(frame,
                              (x - 2, 8),
                              (x + self.color_palette_size + 2, 12 + self.color_palette_size),
                              (255, 255, 255), 2)
        
        # Two-line compact status bar at bottom with smaller font
        txt_col = (0,0,0) if self.whiteboard_mode else (255,255,255)
        pen = "ON" if self.pen_enabled else "OFF"
        bg = "WHITE" if self.whiteboard_mode else "CAM"
        
        # Split controls into two readable lines
        line1 = f'Pen:{pen}(P) Bg:{bg}(B) Mode:{self.mode} | [L]ine [O]circle [R]ect [N]ormal | [1-5]colors'
        line2 = f'[X]clear [U]ndo [Y]redo [Q]uit [F]ullscreen'
        
        # Position at bottom with small font (0.4) and thin stroke
        cv2.putText(frame, line1, (5, h - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.4, txt_col, 1)
        cv2.putText(frame, line2, (5, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, txt_col, 1)

    def detect_finger(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_color, self.upper_color)
        k = np.ones((5,5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return None, None
        c = max(cnts, key=cv2.contourArea)
        if cv2.contourArea(c) < 300:
            return None, None
        M = cv2.moments(c)
        if M["m00"] == 0:
            return None, None
        return int(M["m10"]/M["m00"]), int(M["m01"]/M["m00"])

    def perfect_shape(self):
        if len(self.points) < 2:
            self.points.clear()
            return
        
        # Save state before drawing shape
        self.save_canvas_state()
        
        col = self.colors[self.current_color_idx]
        p0, p1 = self.points[0], self.points[-1]
        if self.mode == "line":
            cv2.line(self.canvas, p0, p1, col, 2)
        elif self.mode == "circle":
            r = int(math.hypot(p1[0]-p0[0], p1[1]-p0[1]))
            if r > 0:
                cv2.circle(self.canvas, p0, r, col, 2)
        elif self.mode == "rect":
            cv2.rectangle(self.canvas, p0, p1, col, 2)
        self.points.clear()

    def run(self):
        print("=== Air Canvas with Undo/Redo Started! ===")
        print("X: Clear | U: Undo | Y: Redo | Q: Quit")
        print("P: Pen | B: Background | F: Fullscreen")
        print("L: Line | O: Circle | R: Rectangle | N: Normal")
        
        cv2.namedWindow('Air Canvas', cv2.WINDOW_NORMAL)
        cv2.setWindowProperty('Air Canvas', cv2.WND_PROP_FULLSCREEN,
                              cv2.WINDOW_FULLSCREEN)
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            if self.canvas is None or self.canvas.shape[:2] != (h, w):
                self.canvas = np.zeros((h, w, 3), dtype=np.uint8)
                self.canvas_history = []
                self.redo_history = []
            
            x, y = self.detect_finger(frame)

            # Drawing logic
            if self.pen_enabled and x is not None:
                # Check palette click
                palette_clicked = False
                if 10 <= y <= 10 + self.color_palette_size:
                    for i in range(len(self.colors)):
                        px = 50 + i * (self.color_palette_size + 10)
                        if px <= x <= px + self.color_palette_size:
                            self.current_color_idx = i
                            palette_clicked = True
                            break
                
                if not palette_clicked:
                    if not self.drawing:
                        # START DRAWING
                        self.drawing = True
                        self.points = [(x, y)]
                        if self.mode != "normal":
                            self.temp_canvas = self.canvas.copy()
                        else:
                            self.save_canvas_state()
                    else:
                        # CONTINUE DRAWING
                        if self.mode == "normal":
                            # Normal freehand drawing
                            if len(self.points) > 0:
                                cv2.line(self.canvas, self.points[-1], (x, y),
                                         self.colors[self.current_color_idx], self.brush_size)
                            self.points.append((x, y))
                        else:
                            # Shape drawing
                            if self.temp_canvas is not None:
                                self.canvas = self.temp_canvas.copy()
                            
                            # Always ensure we have exactly start and current point
                            if len(self.points) >= 1:
                                # Update current point (keep start point, update end point)
                                if len(self.points) == 1:
                                    self.points.append((x, y))
                                else:
                                    # Replace last point with current position
                                    self.points[-1] = (x, y)
                                
                                # Draw preview
                                p0, p1 = self.points[0], self.points[-1]
                                col = self.colors[self.current_color_idx]
                                if self.mode == "line":
                                    cv2.line(self.canvas, p0, p1, col, 2)
                                elif self.mode == "circle":
                                    r = int(math.hypot(p1[0]-p0[0], p1[1]-p0[1]))
                                    if r > 0:
                                        cv2.circle(self.canvas, p0, r, col, 2)
                                elif self.mode == "rect":
                                    cv2.rectangle(self.canvas, p0, p1, col, 2)
                else:
                    # Palette clicked - stop drawing
                    if self.drawing and self.mode != "normal":
                        self.perfect_shape()
                    self.drawing = False
                    self.points = []
            else:
                # No finger detected - finalize drawing
                if self.drawing and self.mode != "normal":
                    self.perfect_shape()
                self.drawing = False

            # Compose frame
            if self.whiteboard_mode:
                result = np.full((h, w, 3), 255, dtype=np.uint8)
                mask = np.any(self.canvas != [0, 0, 0], axis=2)
                result[mask] = self.canvas[mask]
            else:
                result = cv2.addWeighted(frame, 0.7, self.canvas, 0.3, 0)

            # Detection circle
            if x is not None:
                col = (0, 255, 0) if self.pen_enabled else (0, 0, 255)
                cv2.circle(result, (x, y), 10, col, -1)

            self.setup_ui(result)
            cv2.imshow('Air Canvas', result)

            # Keyboard controls
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('x'):
                self.save_canvas_state()
                self.canvas.fill(0)
                self.points = []
                self.drawing = False
                print("Canvas cleared")
            elif key == ord('u'):
                self.undo()
            elif key == ord('y'):  # Redo feature
                self.redo()
            elif key == 27:  # ESC
                cv2.setWindowProperty('Air Canvas', cv2.WND_PROP_FULLSCREEN,
                                      cv2.WINDOW_NORMAL)
            elif key == ord('f'):
                prop = cv2.getWindowProperty('Air Canvas', cv2.WND_PROP_FULLSCREEN)
                new_prop = cv2.WINDOW_NORMAL if prop == cv2.WINDOW_FULLSCREEN \
                           else cv2.WINDOW_FULLSCREEN
                cv2.setWindowProperty('Air Canvas', cv2.WND_PROP_FULLSCREEN, new_prop)
            elif key == ord('p'):
                self.pen_enabled = not self.pen_enabled
                print(f"Pen: {'ON' if self.pen_enabled else 'OFF'}")
            elif key == ord('b'):
                self.whiteboard_mode = not self.whiteboard_mode
                print(f"Background: {'WHITEBOARD' if self.whiteboard_mode else 'CAMERA'}")
            elif key == ord('l'):
                self.mode = "line"
                self.points = []
                self.drawing = False
                print("Mode: Line")
            elif key == ord('n'):
                self.mode = "normal"
                self.points = []
                self.drawing = False
                print("Mode: Normal")
            elif key == ord('r'):
                self.mode = "rect"
                self.points = []
                self.drawing = False
                print("Mode: Rectangle")
            elif key == ord('o'):
                self.mode = "circle"
                self.points = []
                self.drawing = False
                print("Mode: Circle")
            elif ord('1') <= key <= ord('5'):
                self.current_color_idx = key - ord('1')
                color_names = ['Red', 'Green', 'Blue', 'Yellow', 'Magenta']
                print(f"Color: {color_names[self.current_color_idx]}")

        self.cap.release()
        cv2.destroyAllWindows()
        print("Air Canvas closed!")

if __name__ == "__main__":
    AirCanvas().run()