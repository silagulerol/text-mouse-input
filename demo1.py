"""
EMG-based scanning + cross-precision visual demo (Tkinter).
Updated:
- After TOP_LEVEL_LIMIT, user chooses algorithm.
- If user picks "Continue Scanning", after each partition the same question is asked again (modal).
- Partition preview: 0 → GREEN, 1 → BLUE (visualized before pressing).
- Minor UI tweaks to show chosen half color briefly.
"""
import tkinter as tk
import time

# ---------- CONFIG ----------
WINDOW_W, WINDOW_H = 700, 560
GRID_COLS, GRID_ROWS = 20, 20  # chosen by user
MARGIN = 10
CELL_W = (WINDOW_W - 2 * MARGIN) // GRID_COLS
CELL_H = (WINDOW_H - 180 - MARGIN) // GRID_ROWS  # leave more space for controls
MIN_REGION_CELLS = 4  # stop scanning when region area <= this (small enough)
TOP_LEVEL_LIMIT = 3  # after 3 top-level selections prompt user
# ----------------------------

# colors
COLOR_WHITE = "white"
COLOR_OUTLINE = "#ddd"
COLOR_HIGHLIGHT_DEFAULT = "#f0f8ff"  # faint neutral highlight if needed
COLOR_PART_0 = "#b6d7a8"  # green (for 0)
COLOR_PART_1 = "#9fc5e8"  # blue (for 1)
COLOR_CROSS = "#fff2cc"
COLOR_CROSS_INTER = "#ffd966"
COLOR_FINAL = "#f4cccc"

class Region:
    def __init__(self, c1, r1, c2, r2):
        # c1,r1 inclusive start indices; c2,r2 exclusive end indices
        self.c1, self.r1 = c1, r1
        self.c2, self.r2 = c2, r2

    def width(self):
        return self.c2 - self.c1

    def height(self):
        return self.r2 - self.r1

    def area(self):
        return max(0, self.width()) * max(0, self.height())

    def subdivide(self, direction):
        # direction = "horizontal" or "vertical"
        if direction == "horizontal":
            mid = (self.r1 + self.r2) // 2
            top = Region(self.c1, self.r1, self.c2, mid)
            bottom = Region(self.c1, mid, self.c2, self.r2)
            return top, bottom
        else:
            mid = (self.c1 + self.c2) // 2
            left = Region(self.c1, self.r1, mid, self.r2)
            right = Region(mid, self.r1, self.c2, self.r2)
            return left, right

    def contains(self, col, row):
        return self.c1 <= col < self.c2 and self.r1 <= row < self.r2

class EMGScanningApp:
    def __init__(self, root):
        self.root = root
        root.title("EMG Scanning + Cross Precision Demo (20x20)")

        # Canvas for grid
        self.canvas = tk.Canvas(root, width=WINDOW_W, height=WINDOW_H-180, bg="white")
        self.canvas.pack(padx=10, pady=10)

        # Control frame for buttons and labels
        ctrl_frame = tk.Frame(root)
        ctrl_frame.pack(pady=6, fill="x")

        # Buttons (simulate EMG)
        btn_frame = tk.Frame(ctrl_frame)
        btn_frame.pack(side="left", padx=8)

        # --- 0 button (green) ---
        self.btn0 = tk.Button(
            btn_frame,
            text="0",
            width=6,
            bg="#6AA84F",      # green
            fg="white",
            activebackground="#38761D",  # darker green when pressed
            activeforeground="white",
            command=lambda: self.set_signal(0)
        )
        self.btn0.grid(row=0, column=0, padx=6, pady=2)
        self.zero_desc_label = tk.Label(btn_frame, text="0 → (not set)", width=36, anchor="w")
        self.zero_desc_label.grid(row=0, column=1, padx=6)

        # --- 1 button (blue) ---
        self.btn1 = tk.Button(
            btn_frame,
            text="1",
            width=6,
            bg="#3C78D8",      # blue
            fg="white",
            activebackground="#1155CC",  # darker blue when pressed
            activeforeground="white",
            command=lambda: self.set_signal(1)
        )
        self.btn1.grid(row=1, column=0, padx=6, pady=2)
        self.one_desc_label = tk.Label(btn_frame, text="1 → (not set)", width=36, anchor="w")
        self.one_desc_label.grid(row=1, column=1, padx=6)

        # Info / status label
        self.info_label = tk.Label(ctrl_frame, text="Başlangıç: Use 0/1 to choose halves. After 3 selects you'll choose algorithm.", anchor="w")
        self.info_label.pack(side="left", padx=10)

        # state
        self.grid_cols, self.grid_rows = GRID_COLS, GRID_ROWS
        self.cell_w, self.cell_h = CELL_W, CELL_H
        self.signal = None
        self.top_level_counter = 0

        # initial full region
        self.current_region = Region(0, 0, self.grid_cols, self.grid_rows)
        self.direction_index = 0  # alternate horizontal (0) then vertical (1) ...
        self.drawing_rects = []  # store rect ids for grid cells

        # initialize grid
        self.draw_full_grid()
        self.root.update()

        # set initial descriptions for the first split (horizontal)
        self.update_signal_labels("Üst bölgeyi seç", "Alt bölgeyi seç")

        # Start main scanning flow soon
        self.root.after(300, self.main_scanning_flow)

    # ---------------- GUI / drawing routines ----------------
    def draw_full_grid(self, highlight_region: Region = None, cross=None, final_pixel=None, candidate_pixels=None):
        """Draw entire grid. Optionally highlight a region, a cross (col,row) and a final pixel."""
        self.canvas.delete("all")
        self.drawing_rects = []
        for c in range(self.grid_cols):
            col_rects = []
            for r in range(self.grid_rows):
                x1 = MARGIN + c * self.cell_w
                y1 = MARGIN + r * self.cell_h
                x2 = x1 + self.cell_w
                y2 = y1 + self.cell_h

                fill = COLOR_WHITE
                outline = COLOR_OUTLINE
                # highlight region cells lightly (default neutral)
                if highlight_region and highlight_region.contains(c, r):
                    fill = COLOR_HIGHLIGHT_DEFAULT

                rect_id = self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline)
                col_rects.append(rect_id)
            self.drawing_rects.append(col_rects)

        # if cross is given, highlight row & column strongly
        if cross:
            col_idx, row_idx = cross
            # safety checks
            if 0 <= col_idx < self.grid_cols and 0 <= row_idx < self.grid_rows:
                for r in range(self.grid_rows):
                    rid = self.drawing_rects[col_idx][r]
                    self.canvas.itemconfig(rid, fill=COLOR_CROSS)  # pale yellow
                for c in range(self.grid_cols):
                    rid = self.drawing_rects[c][row_idx]
                    self.canvas.itemconfig(rid, fill=COLOR_CROSS)
                # mark intersection darker
                rid = self.drawing_rects[col_idx][row_idx]
                self.canvas.itemconfig(rid, fill=COLOR_CROSS_INTER)

        # final pixel highlight
        if final_pixel:
            c, r = final_pixel
            if 0 <= c < self.grid_cols and 0 <= r < self.grid_rows:
                rid = self.drawing_rects[c][r]
                self.canvas.itemconfig(rid, fill=COLOR_FINAL)

        # candidate pixels (list)
        if candidate_pixels:
            for (c, r) in candidate_pixels:
                if 0 <= c < self.grid_cols and 0 <= r < self.grid_rows:
                    rid = self.drawing_rects[c][r]
                    self.canvas.itemconfig(rid, fill=COLOR_PART_0)  # reuse greenish for candidates

        # draw bounding rectangle for the current region
        if highlight_region:
            x1 = MARGIN + highlight_region.c1 * self.cell_w
            y1 = MARGIN + highlight_region.r1 * self.cell_h
            x2 = MARGIN + highlight_region.c2 * self.cell_w
            y2 = MARGIN + highlight_region.r2 * self.cell_h
            self.canvas.create_rectangle(x1, y1, x2, y2, outline="#1155cc", width=3)

        self.canvas.update()

    def draw_partition_preview(self, region: Region, r1: Region, r2: Region, direction):
        """Draw grid and color first half (r1) as GREEN (0) and second half (r2) as BLUE (1)."""
        # start from a neutral full draw of the region
        self.draw_full_grid(highlight_region=region)
        # color r1 cells green
        for c in range(r1.c1, r1.c2):
            for r in range(r1.r1, r1.r2):
                rid = self.drawing_rects[c][r]
                self.canvas.itemconfig(rid, fill=COLOR_PART_0)
        # color r2 cells blue
        for c in range(r2.c1, r2.c2):
            for r in range(r2.r1, r2.r2):
                rid = self.drawing_rects[c][r]
                self.canvas.itemconfig(rid, fill=COLOR_PART_1)

        # draw split line
        if direction == "horizontal":
            mid_r = (region.r1 + region.r2) // 2
            y = MARGIN + mid_r * self.cell_h
            x1 = MARGIN + region.c1 * self.cell_w
            x2 = MARGIN + region.c2 * self.cell_w
            self.canvas.create_line(x1, y, x2, y, fill="red", width=3)
        else:
            mid_c = (region.c1 + region.c2) // 2
            x = MARGIN + mid_c * self.cell_w
            y1 = MARGIN + region.r1 * self.cell_h
            y2 = MARGIN + region.r2 * self.cell_h
            self.canvas.create_line(x, y1, x, y2, fill="red", width=3)

        self.canvas.update()

    # ---------------- EMG signal handling ----------------
    def set_signal(self, s):
        self.signal = s

    def wait_for_signal(self, prompt_text=None):
        """Block (but keep GUI responsive) until the user clicks a simulated EMG button."""
        if prompt_text:
            self.info_label.config(text=prompt_text)
        else:
            # keep what was in info_label
            pass
        self.root.update()
        while self.signal is None:
            self.root.update()
            time.sleep(0.05)
        val = self.signal
        self.signal = None
        return val

    # ---------------- Dynamic label updater ----------------
    def update_signal_labels(self, text0, text1):
        """Update descriptive labels next to 0 and 1 buttons."""
        # Keep button numeric labels short; descriptions appear in labels
        self.zero_desc_label.config(text=f"0 → {text0}")
        self.one_desc_label.config(text=f"1 → {text1}")
        # Also set info_label briefly to clarify mapping
        self.info_label.config(text=f"0: {text0}    |    1: {text1}")
        self.root.update()

    # ---------------- Modal to ask continue vs diagonal ----------------
    def ask_continue_or_diagonal_modal(self):
        """Return True if user chooses Continue Scanning, False if choose Diagonal."""
        result = {"choice": None}
        def cont():
            result["choice"] = True
            modal.destroy()
        def diag():
            result["choice"] = False
            modal.destroy()

        modal = tk.Toplevel(self.root)
        modal.title("Bir sonraki algoritmayı seç")
        tk.Label(modal, text=" Taramaya devam mı etmek istersin yoksa Çapraz Aramaya geçmek mi?").pack(padx=12, pady=8)
        tk.Button(modal, text="0 -Taramaya devam et", width=24, command=cont).pack(padx=12, pady=6)
        tk.Button(modal, text="1 -Çapraz aramaya geç", width=24, command=diag).pack(padx=12, pady=6)
        modal.transient(self.root)
        modal.grab_set()
        self.root.wait_window(modal)
        return result["choice"]

    # ---------------- Main logic flows ----------------
    def main_scanning_flow(self):
        """
        - Top-level scanning limited by TOP_LEVEL_LIMIT
        - After TOP_LEVEL_LIMIT ask user to choose algorithm
        """
        # initial draw
        self.draw_full_grid(highlight_region=self.current_region)

        # TOP-LEVEL scanning: do up to TOP_LEVEL_LIMIT iterations
        while self.top_level_counter < TOP_LEVEL_LIMIT:
            direction = "horizontal" if (self.direction_index % 2 == 0) else "vertical"
            # update labels for this split
            if direction == "horizontal":
                self.update_signal_labels("Üst bölgeyi seç", "Alt bölgeyi seç")
            else:
                self.update_signal_labels("Sol bölgeyi seç", "Sağ bölgeyi seç")

            self.info_label.config(text=f"Top-level scanning #{self.top_level_counter + 1}. Splitting {direction}.")
            self.draw_full_grid(highlight_region=self.current_region)
            # show partition preview before choice (0 green, 1 blue)
            r1, r2 = self.current_region.subdivide(direction)
            self.draw_partition_preview(self.current_region, r1, r2, direction)

            # subdivide and wait for EMG
            s = self.wait_for_signal()
            if s == 0:
                # pick upper/left - briefly show chosen color green
                self.current_region = r1
                self.draw_full_grid(highlight_region=self.current_region)
                self._flash_region_color(self.current_region, COLOR_PART_0)
            else:
                # pick lower/right - briefly show chosen color blue
                self.current_region = r2
                self.draw_full_grid(highlight_region=self.current_region)
                self._flash_region_color(self.current_region, COLOR_PART_1)

            self.top_level_counter += 1
            self.direction_index += 1
            self.draw_full_grid(highlight_region=self.current_region)
            self.root.update()
            time.sleep(0.2)

        # After TOP_LEVEL_LIMIT navigations, ask user which algorithm to continue
        choice = self.ask_continue_or_diagonal_modal()
        if choice is None:
            # modal closed unexpectedly; continue scanning by default
            self.continue_scanning_inside_region()
            return
        if choice:
            # Continue scanning - but inside that function we'll prompt after each partition
            self.info_label.config(text="Continuing scanning inside selected region...")
            self.continue_scanning_inside_region()
        else:
            self.info_label.config(text="Switching to Diagonal (Cross Precision) algorithm...")
            self.start_diagonal_in_region()

    def _flash_region_color(self, region: Region, color, flashes=1, delay=0.12):
        """Temporarily color the whole region with given color for a short flash."""
        # color all cells in region
        for c in range(region.c1, region.c2):
            for r in range(region.r1, region.r2):
                rid = self.drawing_rects[c][r]
                self.canvas.itemconfig(rid, fill=color)
        self.canvas.update()
        time.sleep(delay)
        # redraw neutral highlight
        self.draw_full_grid(highlight_region=region)

    def continue_scanning_inside_region(self):
        # Keep subdividing inside the selected region until small enough
        while self.current_region.area() > MIN_REGION_CELLS:
            direction = "horizontal" if (self.direction_index % 2 == 0) else "vertical"
            if direction == "horizontal":
                self.update_signal_labels("Üst bölgeyi seç", "Alt bölgeyi seç")
            else:
                self.update_signal_labels("Sol bölgeyi seç", "Sağ bölgeyi seç")

            self.info_label.config(text=f"Refined scanning. Splitting {direction}.")
            # preview partition colored
            r1, r2 = self.current_region.subdivide(direction)
            self.draw_partition_preview(self.current_region, r1, r2, direction)

            s = self.wait_for_signal()
            if s == 0:
                self.current_region = r1
                # visual feedback for choice (green)
                self.draw_full_grid(highlight_region=self.current_region)
                self._flash_region_color(self.current_region, COLOR_PART_0)
            else:
                self.current_region = r2
                # visual feedback for choice (blue)
                self.draw_full_grid(highlight_region=self.current_region)
                self._flash_region_color(self.current_region, COLOR_PART_1)

            self.direction_index += 1
            self.draw_full_grid(highlight_region=self.current_region)
            self.root.update()
            time.sleep(0.12)

            # After each partition, ask the user whether to continue partitioning or switch to diagonal
            choice = self.ask_continue_or_diagonal_modal()
            # If user chose to continue scanning, loop continues.
            if choice is None:
                # closed dialog: default continue
                continue
            if not choice:
                # switch to diagonal
                self.info_label.config(text="Switching to Diagonal (Cross Precision) algorithm...")
                self.start_diagonal_in_region()
                return
            else:
                self.info_label.config(text="Continuing partitioning inside region...")

        # When region is small, mark the final candidate pixel(s) inside
        self.finalize_selection_from_region()

    def finalize_selection_from_region(self):
        """When region is reduced to small area, prompt user to select exact pixel visually."""
        # If area is 1 cell -> done.
        if self.current_region.area() == 1:
            c = self.current_region.c1
            r = self.current_region.r1
            self.draw_full_grid(final_pixel=(c, r))
            self.info_label.config(text=f"Final pixel selected at ({c}, {r}). Done.")
            self.update_signal_labels("—", "—")
            return

        # Otherwise show candidate pixels and allow user to press signal to pick.
        candidates = []
        for c in range(self.current_region.c1, self.current_region.c2):
            for r in range(self.current_region.r1, self.current_region.r2):
                candidates.append((c, r))
        self.draw_full_grid(candidate_pixels=candidates)
        self.info_label.config(text=f"Choose final pixel inside region of {len(candidates)} cells. Use EMG to pick halves iteratively.")

        # Now use a localized scanning inside this tiny region until one cell remains
        while self.current_region.area() > 1:
            direction = "horizontal" if (self.direction_index % 2 == 0) else "vertical"
            if direction == "horizontal":
                self.update_signal_labels("Üst yarım (0)", "Alt yarım (1)")
            else:
                self.update_signal_labels("Sol yarım (0)", "Sağ yarım (1)")

            self.visualize_split_line(self.current_region, direction)
            r1, r2 = self.current_region.subdivide(direction)
            # preview colored halves
            self.draw_partition_preview(self.current_region, r1, r2, direction)
            s = self.wait_for_signal()
            if s == 0:
                self.current_region = r1
            else:
                self.current_region = r2
            self.direction_index += 1
            self.draw_full_grid(highlight_region=self.current_region)
            self.root.update()
            time.sleep(0.08)

        # finalize single pixel
        self.draw_full_grid(final_pixel=(self.current_region.c1, self.current_region.r1))
        self.info_label.config(text=f"Final pixel selected at ({self.current_region.c1}, {self.current_region.r1}). Done.")
        self.update_signal_labels("—", "—")

    # ---------------- Diagonal / cross-precision flow ----------------
    def start_diagonal_in_region(self):
        """
        Diagonal flow per user's latest spec:
        - For i in 0..min(width,height)-1:
            draw cross at (c_min+i, r_min+i)
            Signal 1 => CROSS CONTAINS target
            Signal 0 => CROSS DOES NOT -> next i
        - If cross accepted:
            ask axis: Signal 1 = COLUMN, Signal 0 = ROW
            then scan along axis from i to end with:
                Signal 1 = FOUND, Signal 0 = CONTINUE
        """
        c_min, r_min = self.current_region.c1, self.current_region.r1
        max_w = self.current_region.width()
        max_h = self.current_region.height()

        limit = min(max_w, max_h)
        SAFETY = max(200, max_w * max_h * 6)
        steps = 0

        for i in range(limit):
            if steps > SAFETY:
                break

            col_idx = c_min + i
            row_idx = r_min + i

            # Draw cross and update descriptions:
            self.draw_full_grid(highlight_region=self.current_region, cross=(col_idx, row_idx))
            self.update_signal_labels("Kesişim içinde hedef yok", "Kesişim içinde hedef var")
            self.info_label.config(text=f"Diagonal i={i}: Cross at (col={col_idx}, row={row_idx}). 0=Hayır, 1=Evet")
            s_cross = self.wait_for_signal()

            # According to your rule: Signal 1 -> accepted, Signal 0 -> reject
            if s_cross == 0:
                steps += 1
                continue  # go next i

            # s_cross == 1 -> cross contains target. Now decide axis.
            self.update_signal_labels("SATIR üzerinde ara (0)", "SÜTUN üzerinde ara (1)")
            self.info_label.config(text="Cross kabul edildi. Hangi eksende ara? 0=SATIR, 1=SÜTUN")
            s_axis = self.wait_for_signal()

            if s_axis == 1:
                # COLUMN search: fixed column = col_idx, increase row from i -> end
                col_fixed = col_idx
                row_local = i  # local index relative to region start
                self.update_signal_labels("Devam et (0)", "Bulundu! (1)")
                while row_local < max_h:
                    if steps > SAFETY:
                        break
                    global_row = r_min + row_local
                    # highlight cell in column
                    self.draw_full_grid(highlight_region=self.current_region, cross=(col_fixed, global_row))
                    self.info_label.config(text=f"Column scan at (col={col_fixed}, row={global_row}). 0=Devam, 1=Bulundu")
                    s_chk = self.wait_for_signal()
                    if s_chk == 1:
                        self.draw_full_grid(final_pixel=(col_fixed, global_row))
                        self.info_label.config(text=f"Point selected at ({col_fixed},{global_row}). Done.")
                        self.update_signal_labels("—", "—")
                        return
                    row_local += 1
                    steps += 1
                # if column exhausted -> continue next diagonal i
                continue

            else:
                # ROW search: fixed row = row_idx, increase column from i -> end
                row_fixed = row_idx
                col_local = i
                self.update_signal_labels("Devam et (0)", "Bulundu! (1)")
                while col_local < max_w:
                    if steps > SAFETY:
                        break
                    global_col = c_min + col_local
                    # highlight cell in row
                    self.draw_full_grid(highlight_region=self.current_region, cross=(global_col, row_fixed))
                    self.info_label.config(text=f"Row scan at (col={global_col}, row={row_fixed}). 0=Devam, 1=Bulundu")
                    s_chk = self.wait_for_signal()
                    if s_chk == 1:
                        self.draw_full_grid(final_pixel=(global_col, row_fixed))
                        self.info_label.config(text=f"Point selected at ({global_col},{row_fixed}). Done.")
                        self.update_signal_labels("—", "—")
                        return
                    col_local += 1
                    steps += 1
                # if row exhausted -> continue next diagonal i
                continue

        # fallback if not found
        self.info_label.config(text="Diagonal search tamamlandı veya limit aşıldı. Scanning ile devam ediliyor.")
        self.update_signal_labels("Üst/Left (0)", "Alt/Right (1)")
        # after diagonal fallback, ask whether to continue scanning or not
        choice = self.ask_continue_or_diagonal_modal()
        if choice is None or choice:
            self.continue_scanning_inside_region()
        else:
            # if user insists diagonal but we finished diagonal, just finalize
            self.finalize_selection_from_region()

    # ---------------- small helper to draw subdivision line ----------------
    def visualize_split_line(self, region: Region, direction):
        """Draw the current grid, then draw a thick red line showing the split inside region."""
        self.draw_full_grid(highlight_region=region)
        if direction == "horizontal":
            mid_r = (region.r1 + region.r2) // 2
            y = MARGIN + mid_r * self.cell_h
            x1 = MARGIN + region.c1 * self.cell_w
            x2 = MARGIN + region.c2 * self.cell_w
            self.canvas.create_line(x1, y, x2, y, fill="red", width=3)
        else:
            mid_c = (region.c1 + region.c2) // 2
            x = MARGIN + mid_c * self.cell_w
            y1 = MARGIN + region.r1 * self.cell_h
            y2 = MARGIN + region.r2 * self.cell_h
            self.canvas.create_line(x, y1, x, y2, fill="red", width=3)
        self.canvas.update()

# Run
if __name__ == "__main__":
    root = tk.Tk()
    root.geometry(f"{WINDOW_W}x{WINDOW_H}")
    app = EMGScanningApp(root)
    root.mainloop()
