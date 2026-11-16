import asyncio
import json
import math
import os
import random
import struct
import sys
import pygame

API_URL = "https://vn-history-game.onrender.com"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

WIDTH, HEIGHT = 1280, 720
FPS = 60

# Bảng màu Chủ đề "Sử Vàng Đại Việt"
BG_SAND       = (245, 240, 230)
BG_PANEL      = (255, 252, 246)
SEA_BLUE      = (216, 234, 242)
SEA_GRID      = (198, 220, 232)
LAND_FILL     = (233, 223, 198)
LAND_BORDER   = (168, 142, 102)
INK_DARK      = (35, 28, 24)
INK_MUTED     = (110, 98, 88)
CRIMSON       = (178, 34, 34)
CRIMSON_LIGHT = (210, 55, 55)
GOLD          = (212, 160, 23)
GOLD_SOFT     = (248, 235, 196)
EMERALD       = (34, 139, 87)
EMERALD_SOFT  = (220, 245, 232)
ROYAL_BLUE    = (32, 74, 135)
ROYAL_SOFT    = (224, 236, 252)
PURPLE_ARENA  = (112, 48, 160)
PURPLE_SOFT   = (238, 226, 248)
LOCKED_GRAY   = (165, 158, 148)
WHITE         = (255, 255, 255)
SHADOW_COLOR  = (215, 206, 192)


class SoundBank:
    """Bộ tổng hợp âm thanh bằng PCM buffer trực tiếp (tương thích 100% WebAssembly)"""
    def __init__(self):
        self.enabled = True
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            self.sounds["click"]   = self._make_tone([(620, 0.045, 0.25)])
            self.sounds["correct"] = self._make_tone([(523.25, 0.08, 0.35), (659.25, 0.08, 0.35), (783.99, 0.14, 0.4)])
            self.sounds["wrong"]   = self._make_tone([(260, 0.12, 0.35), (195, 0.18, 0.35)])
            self.sounds["clear"]   = self._make_tone([(523.25, 0.09, 0.35), (659.25, 0.09, 0.35), (783.99, 0.09, 0.35), (1046.5, 0.24, 0.45)])
            self.sounds["hint"]    = self._make_tone([(440, 0.07, 0.3), (587.33, 0.11, 0.35)])
        except Exception:
            self.enabled = False

    def _make_tone(self, notes, sample_rate=22050):
        frames = bytearray()
        for freq, dur, vol in notes:
            n_samples = int(sample_rate * dur)
            for i in range(n_samples):
                t = i / sample_rate
                env = min(1.0, i / 180.0) * max(0.0, 1.0 - (i / n_samples) ** 1.6)
                val = math.sin(2.0 * math.pi * freq * t) * 0.75 + math.sin(4.0 * math.pi * freq * t) * 0.25
                sample = int(max(-32767, min(32767, val * vol * env * 32767)))
                frames.extend(struct.pack("<h", sample))
        return pygame.mixer.Sound(buffer=bytes(frames))

    def play(self, name):
        if self.enabled and name in self.sounds:
            try:
                self.sounds[name].play()
            except Exception:
                pass


async def api_request(endpoint, method="GET", payload=None):
    url = f"{API_URL}{endpoint}"
    try:
        if sys.platform == "emscripten":
            import platform
            from pyodide.ffi import create_proxy

            loop = asyncio.get_running_loop()
            fut = loop.create_future()

            opts_dict = {"method": method}
            if payload:
                opts_dict["headers"] = {"Content-Type": "text/plain;charset=UTF-8"}
                opts_dict["body"] = json.dumps(payload)

            js_opts = platform.window.JSON.parse(json.dumps(opts_dict))
            resp_status = [500]

            def on_text(text):
                if not fut.done():
                    try:
                        fut.set_result((resp_status[0], json.loads(text)))
                    except Exception:
                        fut.set_result((resp_status[0], {"detail": text}))

            def on_resp(resp):
                resp_status[0] = resp.status
                resp.text().then(create_proxy(on_text))

            def on_err(err):
                if not fut.done():
                    fut.set_result((500, {"detail": "Không kết nối được Backend (kiểm tra cổng 8080)"}))

            platform.window.fetch(url, js_opts).then(create_proxy(on_resp)).catch(create_proxy(on_err))
            return await asyncio.wait_for(fut, timeout=8.0)
        else:
            import urllib.request
            import urllib.error
            data = json.dumps(payload).encode("utf-8") if payload else None
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
            try:
                with urllib.request.urlopen(req, timeout=5) as response:
                    return response.status, json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as he:
                return he.code, json.loads(he.read().decode("utf-8"))
    except Exception as e:
        return 500, {"detail": str(e)}


def draw_card(surface, rect, bg=BG_PANEL, border=None, border_w=2, radius=14, shadow=True):
    if shadow:
        s_rect = pygame.Rect(rect.x + 4, rect.y + 5, rect.width, rect.height)
        pygame.draw.rect(surface, SHADOW_COLOR, s_rect, border_radius=radius)
    pygame.draw.rect(surface, bg, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surface, border, rect, width=border_w, border_radius=radius)


def draw_heart_icon(surface, cx, cy, filled=True):
    color = CRIMSON if filled else (210, 202, 192)
    pygame.draw.circle(surface, color, (cx - 5, cy - 2), 5)
    pygame.draw.circle(surface, color, (cx + 5, cy - 2), 5)
    pygame.draw.polygon(surface, color, [(cx - 10, cy), (cx + 10, cy), (cx, cy + 10)])


def draw_wrapped_text(surface, text, font, color, rect, line_spacing=6):
    words = text.split(" ")
    lines = []
    current = ""
    for w in words:
        test = f"{current} {w}".strip()
        if font.size(test)[0] <= rect.width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)

    y = rect.y
    for line in lines:
        if y + font.get_height() > rect.bottom:
            break
        img = font.render(line, True, color)
        surface.blit(img, (rect.x, y))
        y += font.get_height() + line_spacing
    return y


class Particle:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        angle = random.uniform(0, math.pi * 2)
        speed = random.uniform(60, 220)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed - 60
        self.life = random.uniform(0.6, 1.2)
        self.max_life = self.life
        self.color = color
        self.size = random.randint(4, 8)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 260 * dt
        self.life -= dt

    def draw(self, surface):
        if self.life > 0:
            r = max(1, int(self.size * (self.life / self.max_life)))
            pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), r)


class VietnamHistoryGame:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Sử Ký Việt Nam - Khám Phá Lịch Sử Dân Tộc")
        self.clock = pygame.time.Clock()
        self.sfx = SoundBank()

        font_path = os.path.join(BASE_DIR, "assets", "Roboto-Regular.ttf")
        if not os.path.exists(font_path):
            font_path = None
        self.f_title = pygame.font.Font(font_path, 28)
        self.f_h2    = pygame.font.Font(font_path, 20)
        self.f_body  = pygame.font.Font(font_path, 18)
        self.f_small = pygame.font.Font(font_path, 15)
        self.f_badge = pygame.font.Font(font_path, 13)

        data_path = os.path.join(BASE_DIR, "data", "events.json")
        with open(data_path, "r", encoding="utf-8") as f:
            self.events = json.load(f)

        # Trạng thái Đăng nhập / Đăng ký & Phân quyền
        self.state = "AUTH"
        self.auth_tab = "LOGIN"
        self.username = ""
        self.password = ""
        self.confirm_password = ""
        self.user_role = "player"
        self.active_field = "username"
        self.status_msg = ""
        self.status_is_error = True
        self.loading = False

        # Trạng thái Quản trị Admin
        self.admin_data = {"total_users": 0, "total_attempts": 0, "accuracy_rate": 0, "users": []}
        self.admin_page = 0

        # Trạng thái Tiến trình Mở khóa & Chuỗi 5 câu hỏi/sự kiện
        self.score = 0
        self.hearts = 3
        self.streak = 0
        self.hints_left = 3
        self.completed_ids = set()
        self.unlocked_count = 1

        # Trạng thái Huy hiệu & Đấu trường 50 câu
        self.achievements = set()
        self.stage_used_hint = False
        self.arena_mode = False
        self.arena_pool = []
        self.arena_solved = 0

        self.selected_event = None
        self.selected_idx = 0
        self.q_index = 0
        self.shuffled_options = []
        self.shuffled_answer = 0
        self.eliminated_options = set()
        self.active_hint_text = ""
        self.quiz_timer = 20.0
        self.stage_points_earned = 0
        self.stage_passed = False
        self.last_correct_ans_text = ""

        self.explorer_x = 434.0
        self.explorer_y = 132.0
        self.target_x = 434.0
        self.target_y = 132.0
        self.particles = []
        self.toast_text = ""
        self.toast_color = EMERALD
        self.toast_timer = 0.0
        self.anim_time = 0.0
        self.leaderboard = []

        self.pin_offsets = {
            "40":   (-18, -14),
            "938":  (28, -8),
            "968":  (0, 12),
            "1010": (2, -16),
            "1077": (14, -26),
            "1288": (32, 10),
            "1427": (22, -34),
            "1789": (-22, 18),
            "1954": (-14, -6),
        }

        self.vn_mainland = [
            (412, 102), (438, 96), (468, 94), (498, 92), (528, 98),
            (556, 108), (578, 124), (566, 144), (546, 158), (524, 172),
            (504, 188), (496, 212), (498, 238), (506, 266), (518, 294),
            (536, 322), (558, 348), (582, 376), (602, 408), (612, 442),
            (614, 476), (606, 510), (588, 540), (564, 566), (538, 586),
            (512, 602), (488, 622), (468, 642), (452, 634), (448, 610),
            (462, 586), (480, 564), (498, 542), (516, 516), (526, 486),
            (524, 454), (514, 422), (496, 392), (476, 362), (458, 330),
            (446, 298), (440, 266), (434, 234), (420, 208), (396, 192),
            (376, 174), (368, 150), (376, 126), (392, 110)
        ]
        self.phu_quoc = [(414, 586), (424, 582), (428, 598), (418, 604)]
        self.con_dao  = [(546, 616), (554, 614), (556, 622), (548, 624)]

    def get_rank_info(self):
        if self.user_role == "admin":
            return "Quản trị viên Hệ thống", ROYAL_BLUE, ROYAL_SOFT
        if self.score >= 3000:
            return "Trạng nguyên Quốc sử", CRIMSON, GOLD_SOFT
        elif self.score >= 1500:
            return "Danh tướng Sử ký", ROYAL_BLUE, ROYAL_SOFT
        elif self.score >= 500:
            return "Hào kiệt Đại Việt", EMERALD, EMERALD_SOFT
        return "Tập sự Sử học", INK_MUTED, BG_SAND

    def grant_achievement(self, code, title):
        if code not in self.achievements:
            self.achievements.add(code)
            self.show_toast(f"Mở khóa Huy hiệu mới: [{title}]!", GOLD)

    def get_event_status(self, idx, ev):
        if ev["id"] in self.completed_ids:
            return "DONE"
        if idx < self.unlocked_count:
            return "UNLOCKED"
        return "LOCKED"

    def show_toast(self, text, color=EMERALD):
        self.toast_text = text
        self.toast_color = color
        self.toast_timer = 4.0

    def spawn_celebration(self, x, y):
        for _ in range(45):
            self.particles.append(Particle(x, y, random.choice([GOLD, CRIMSON, EMERALD])))

    async def handle_auth_submit(self):
        u = self.username.strip()
        p = self.password.strip()
        cp = self.confirm_password.strip()

        if not u or not p:
            self.status_is_error = True
            self.status_msg = "Vui lòng nhập đầy đủ Tên đăng nhập và Mật khẩu!"
            return

        if self.auth_tab == "REGISTER":
            if len(p) < 3:
                self.status_is_error = True
                self.status_msg = "Mật khẩu đăng ký phải có ít nhất 3 ký tự!"
                return
            if p != cp:
                self.status_is_error = True
                self.status_msg = "Mật khẩu xác nhận không khớp!"
                return

        self.loading = True
        self.status_is_error = False
        self.status_msg = "Đang xác thực quyền & tải dữ liệu..."

        endpoint = "/auth/login" if self.auth_tab == "LOGIN" else "/auth/register"
        payload = {"username": u, "password": p}

        code, res = await api_request(endpoint, "POST", payload)
        self.loading = False

        if code == 200 and "user" in res:
            user_obj = res["user"]
            self.user_role = user_obj.get("role", "player")
            self.score = user_obj.get("total_score", 0)

            raw_comp = user_obj.get("completed_events") or "[]"
            try:
                comp_list = json.loads(raw_comp) if isinstance(raw_comp, str) else list(raw_comp)
            except Exception:
                comp_list = []
            self.completed_ids = set(int(x) for x in comp_list)
            self.unlocked_count = min(len(self.events), len(self.completed_ids) + 1)

            if self.completed_ids:
                self.achievements.add("FIRST_BLOOD")
            if len(self.completed_ids) >= len(self.events):
                self.achievements.add("CONQUEROR")

            cur_ev = self.events[self.unlocked_count - 1]
            dx, dy = self.pin_offsets.get(str(cur_ev["year"]), (0, 0))
            self.explorer_x = self.target_x = float(cur_ev["x"] + dx)
            self.explorer_y = self.target_y = float(cur_ev["y"] + dy)

            self.status_msg = ""
            self.sfx.play("clear")

            if self.user_role == "admin":
                self.state = "ADMIN"
                self.show_toast("Đăng nhập với quyền Quản trị viên (Admin)!", ROYAL_BLUE)
                asyncio.create_task(self.fetch_admin_data())
            else:
                self.state = "MAP"
                self.show_toast(f"Chào mừng {u}! Đã khôi phục {len(self.completed_ids)}/{len(self.events)} mốc sử!", EMERALD)
                asyncio.create_task(self.fetch_leaderboard())
        else:
            self.status_is_error = True
            self.status_msg = res.get("detail", "Lỗi kết nối máy chủ!")

    async def fetch_leaderboard(self):
        code, data = await api_request("/leaderboard", "GET")
        if code == 200 and isinstance(data, list):
            self.leaderboard = data[:5]

    async def fetch_admin_data(self):
        code, data = await api_request("/admin/overview", "GET")
        if code == 200 and isinstance(data, dict):
            self.admin_data = data

    async def admin_user_action(self, action, target_user, extra=None):
        self.sfx.play("click")
        if action == "reset":
            code, res = await api_request("/admin/user/reset", "POST", {"username": target_user})
        elif action == "role":
            code, res = await api_request("/admin/user/role", "POST", {"username": target_user, "role": extra})
        elif action == "delete":
            code, res = await api_request("/admin/user/delete", "POST", {"username": target_user})
        else:
            return

        if code == 200:
            self.show_toast(res.get("message", "Thao tác thành công!"), EMERALD)
            await self.fetch_admin_data()
        else:
            self.show_toast(res.get("detail", "Không thể thực hiện thao tác!"), CRIMSON)

    async def sync_progress(self, event_id, is_correct):
        await api_request("/game/score", "POST", {
            "username": self.username,
            "score": self.score,
            "completed_events": sorted(list(self.completed_ids))
        })
        await api_request("/game/analytics", "POST", {
            "username": self.username,
            "event_id": event_id,
            "is_correct": is_correct
        })
        await self.fetch_leaderboard()

    def open_event_story(self, idx, ev):
        status = self.get_event_status(idx, ev)
        if status == "LOCKED":
            self.sfx.play("wrong")
            prev_ev = self.events[idx - 1]
            self.show_toast(f"Mốc này đang khóa! Hãy hoàn thành Mốc {idx}: [{prev_ev['year']}] {prev_ev['title']} trước!", CRIMSON)
            return

        self.sfx.play("click")
        self.arena_mode = False
        dx, dy = self.pin_offsets.get(str(ev["year"]), (0, 0))
        self.selected_event = ev
        self.selected_idx = idx
        self.target_x = float(ev["x"] + dx)
        self.target_y = float(ev["y"] + dy)
        self.state = "STORY_MODAL"

    def begin_quiz_questions(self):
        self.sfx.play("click")
        self.arena_mode = False
        self.q_index = 0
        self.stage_points_earned = 0
        self.stage_passed = False
        self.stage_used_hint = False
        self.prepare_current_question()
        self.state = "QUIZ"

    def start_arena_mode(self):
        if len(self.completed_ids) < len(self.events) and self.score < 1500 and self.user_role != "admin":
            self.sfx.play("wrong")
            self.show_toast("Hoàn thành đủ 10 mốc (hoặc đạt 1.500 điểm) để mở Đấu Trường!", PURPLE_ARENA)
            return
        self.sfx.play("clear")
        self.arena_mode = True
        self.arena_pool = []
        for ev in self.events:
            for q in ev["questions"]:
                self.arena_pool.append((ev, q))
        random.shuffle(self.arena_pool)
        self.q_index = 0
        self.arena_solved = 0
        self.stage_points_earned = 0
        self.prepare_current_question()
        self.state = "QUIZ"

    def prepare_current_question(self):
        if self.arena_mode:
            ev, q_obj = self.arena_pool[self.q_index % len(self.arena_pool)]
            self.selected_event = ev
            self.quiz_timer = 12.0
        else:
            ev = self.selected_event
            q_obj = ev["questions"][self.q_index]
            self.quiz_timer = 20.0

        raw_opts = list(enumerate(q_obj["options"]))
        random.shuffle(raw_opts)
        self.shuffled_options = [opt for _, opt in raw_opts]
        for new_idx, (old_idx, _) in enumerate(raw_opts):
            if old_idx == q_obj["answer"]:
                self.shuffled_answer = new_idx
                break
        self.eliminated_options = set()
        self.active_hint_text = ""

    def submit_answer(self, option_idx):
        if not self.selected_event or option_idx in self.eliminated_options:
            return
        ev = self.selected_event
        is_correct = (option_idx == self.shuffled_answer)

        if is_correct:
            self.sfx.play("correct")
            self.streak += 1
            max_t = 12.0 if self.arena_mode else 20.0
            if max_t - self.quiz_timer <= 5.0:
                self.grant_achievement("SPEEDSTER", "Thần tốc (Trả lời dưới 5s)")

            time_bonus = int(self.quiz_timer * (5 if self.arena_mode else 3))
            earned = (80 if self.arena_mode else 50) + time_bonus
            self.score += earned
            self.stage_points_earned += earned

            if self.arena_mode:
                self.arena_solved += 1
                self.q_index += 1
                self.prepare_current_question()
                self.show_toast(f"Đấu trường +{earned}đ! Chuỗi {self.arena_solved} câu!", PURPLE_ARENA)
                asyncio.create_task(self.sync_progress(ev["id"], True))
                return

            if self.q_index + 1 < len(ev["questions"]):
                self.q_index += 1
                self.prepare_current_question()
                self.show_toast(f"Chính xác +{earned}đ! Sang câu {self.q_index + 1}/5...", EMERALD)
                asyncio.create_task(self.sync_progress(ev["id"], True))
            else:
                self.sfx.play("clear")
                first_time = ev["id"] not in self.completed_ids
                self.completed_ids.add(ev["id"])
                if first_time and self.unlocked_count < len(self.events):
                    self.unlocked_count += 1
                bonus_clear = 150
                self.score += bonus_clear
                self.stage_points_earned += bonus_clear
                self.stage_passed = True

                self.grant_achievement("FIRST_BLOOD", "Khởi đầu hào hùng")
                if not self.stage_used_hint:
                    self.grant_achievement("UNTOUCHABLE", "Bất bại (Qua ải không dùng gợi ý)")
                if len(self.completed_ids) >= len(self.events):
                    self.grant_achievement("CONQUEROR", "Chinh phục giang sơn (10/10 mốc)")

                self.spawn_celebration(self.target_x, self.target_y)
                self.state = "RESULT_MODAL"
                asyncio.create_task(self.sync_progress(ev["id"], True))
        else:
            self.sfx.play("wrong")
            self.streak = 0
            self.hearts -= 1
            self.stage_passed = False
            self.last_correct_ans_text = self.shuffled_options[self.shuffled_answer]
            self.show_toast("Sai rồi! Bạn bị mất 1 Tim.", CRIMSON)
            asyncio.create_task(self.sync_progress(ev["id"], False))

            if self.hearts <= 0:
                self.state = "GAMEOVER"
            elif self.arena_mode:
                if self.q_index + 1 < len(self.arena_pool):
                    self.q_index += 1
                    self.prepare_current_question()
            else:
                self.state = "RESULT_MODAL"

    def use_story_hint(self):
        if self.active_hint_text or not self.selected_event:
            return
        if self.score < 15:
            self.sfx.play("wrong")
            self.show_toast("Cần tối thiểu 15 điểm để mở Gợi ý sử liệu!", CRIMSON)
            return

        self.sfx.play("hint")
        self.stage_used_hint = True
        self.score -= 15
        ev = self.selected_event
        q_obj = self.arena_pool[self.q_index % len(self.arena_pool)][1] if self.arena_mode else ev["questions"][self.q_index]
        correct_opt = q_obj["options"][q_obj["answer"]]
        story_sentences = [s.strip() for s in ev.get("story", "").split(".") if s.strip()]

        keywords = [w.lower() for w in correct_opt.replace("(", "").replace(")", "").split() if len(w) > 2]
        best_sentence = story_sentences[0] if story_sentences else ev.get("fact", "")
        best_hits = -1
        for sent in story_sentences:
            hits = sum(1 for kw in keywords if kw in sent.lower())
            if hits > best_hits:
                best_hits = hits
                best_sentence = sent

        self.active_hint_text = f"Gợi ý từ sử liệu (-15đ): \"{best_sentence}.\""
        self.show_toast("Đã mở Gợi ý trích dẫn sử liệu (-15 điểm)!", ROYAL_BLUE)

    def use_hint_5050(self):
        if self.hints_left <= 0 or not self.selected_event:
            return
        wrong_indices = [i for i in range(4) if i != self.shuffled_answer and i not in self.eliminated_options]
        if len(wrong_indices) >= 2:
            self.sfx.play("hint")
            self.stage_used_hint = True
            to_hide = random.sample(wrong_indices, 2)
            self.eliminated_options.update(to_hide)
            self.hints_left -= 1
            self.show_toast("Đã loại bỏ 2 phương án sai (50/50)!", GOLD)

    def reset_run(self):
        self.sfx.play("click")
        self.hearts = 3
        self.streak = 0
        self.hints_left = 3
        self.arena_mode = False
        self.state = "MAP"

    # ==================== RENDER AUTH ====================

    def draw_auth(self):
        self.screen.fill(BG_SAND)
        pygame.draw.circle(self.screen, (234, 226, 210), (200, 180), 170)
        pygame.draw.circle(self.screen, (234, 226, 210), (1100, 560), 210)
        pygame.draw.circle(self.screen, GOLD, (200, 180), 170, width=2)

        card_h = 525 if self.auth_tab == "REGISTER" else 450
        card_y = (HEIGHT - card_h) // 2
        card = pygame.Rect(WIDTH // 2 - 250, card_y, 500, card_h)
        draw_card(self.screen, card, BG_PANEL, border=GOLD, border_w=2, radius=18)

        title = self.f_title.render("SỬ KÝ VIỆT NAM", True, CRIMSON)
        sub = self.f_small.render("Hành trình khám phá 4.000 năm lịch sử dựng nước & giữ nước", True, INK_MUTED)
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, card.y + 20))
        self.screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, card.y + 56))

        tab_bar = pygame.Rect(card.x + 40, card.y + 88, 420, 42)
        pygame.draw.rect(self.screen, BG_SAND, tab_bar, border_radius=12)

        tab_login_rect = pygame.Rect(tab_bar.x + 4, tab_bar.y + 4, 205, 34)
        tab_reg_rect   = pygame.Rect(tab_bar.x + 211, tab_bar.y + 4, 205, 34)

        pygame.draw.rect(self.screen, CRIMSON, tab_login_rect if self.auth_tab == "LOGIN" else tab_reg_rect, border_radius=10)

        t1 = self.f_body.render("ĐĂNG NHẬP", True, WHITE if self.auth_tab == "LOGIN" else INK_DARK)
        t2 = self.f_body.render("ĐĂNG KÝ MỚI", True, WHITE if self.auth_tab == "REGISTER" else INK_DARK)
        self.screen.blit(t1, (tab_login_rect.centerx - t1.get_width() // 2, tab_login_rect.y + 6))
        self.screen.blit(t2, (tab_reg_rect.centerx - t2.get_width() // 2, tab_reg_rect.y + 6))

        y_cur = card.y + 146

        self.screen.blit(self.f_small.render("Tên đăng nhập:", True, INK_DARK), (card.x + 40, y_cur))
        box_u = pygame.Rect(card.x + 40, y_cur + 22, 420, 44)
        draw_card(self.screen, box_u, BG_SAND, border=CRIMSON if self.active_field == "username" else LAND_BORDER, shadow=False, radius=10)
        self.screen.blit(self.f_body.render(self.username or "Nhập tên tài khoản...", True, INK_DARK if self.username else INK_MUTED), (box_u.x + 14, box_u.y + 10))
        y_cur += 78

        self.screen.blit(self.f_small.render("Mật khẩu:", True, INK_DARK), (card.x + 40, y_cur))
        box_p = pygame.Rect(card.x + 40, y_cur + 22, 420, 44)
        draw_card(self.screen, box_p, BG_SAND, border=CRIMSON if self.active_field == "password" else LAND_BORDER, shadow=False, radius=10)
        self.screen.blit(self.f_body.render(("*" * len(self.password)) or "Nhập mật khẩu...", True, INK_DARK if self.password else INK_MUTED), (box_p.x + 14, box_p.y + 10))
        y_cur += 78

        if self.auth_tab == "REGISTER":
            self.screen.blit(self.f_small.render("Xác nhận lại mật khẩu:", True, INK_DARK), (card.x + 40, y_cur))
            box_cp = pygame.Rect(card.x + 40, y_cur + 22, 420, 44)
            draw_card(self.screen, box_cp, BG_SAND, border=CRIMSON if self.active_field == "confirm" else LAND_BORDER, shadow=False, radius=10)
            self.screen.blit(self.f_body.render(("*" * len(self.confirm_password)) or "Nhập lại mật khẩu...", True, INK_DARK if self.confirm_password else INK_MUTED), (box_cp.x + 14, box_cp.y + 10))
            y_cur += 78

        btn_go = pygame.Rect(card.x + 40, y_cur + 8, 420, 50)
        hover = btn_go.collidepoint(pygame.mouse.get_pos())
        btn_bg = (EMERALD if self.auth_tab == "REGISTER" else CRIMSON)
        if hover:
            btn_bg = (45, 165, 105) if self.auth_tab == "REGISTER" else CRIMSON_LIGHT
        draw_card(self.screen, btn_go, btn_bg, shadow=True, radius=12)

        btn_label = "TẠO TÀI KHOẢN & BẮT ĐẦU CHƠI" if self.auth_tab == "REGISTER" else "ĐĂNG NHẬP HỆ THỐNG"
        if self.loading:
            btn_label = "ĐANG KẾT NỐI..."
        go_txt = self.f_h2.render(btn_label, True, WHITE)
        self.screen.blit(go_txt, (btn_go.centerx - go_txt.get_width() // 2, btn_go.y + 12))

        if self.status_msg:
            msg_color = CRIMSON if self.status_is_error else EMERALD
            err = self.f_small.render(self.status_msg, True, msg_color)
            self.screen.blit(err, (WIDTH // 2 - err.get_width() // 2, btn_go.bottom + 10))
        elif self.auth_tab == "LOGIN":
            hint_adm = self.f_badge.render("Tài khoản Quản trị (Admin): admin  |  Mật khẩu: 123", True, INK_MUTED)
            self.screen.blit(hint_adm, (WIDTH // 2 - hint_adm.get_width() // 2, btn_go.bottom + 14))

    # ==================== RENDER ADMIN DASHBOARD ====================

    def draw_admin_view(self):
        self.screen.fill(BG_SAND)

        # Thanh tiêu đề Admin
        hdr = pygame.Rect(24, 16, WIDTH - 48, 64)
        draw_card(self.screen, hdr, BG_PANEL, border=ROYAL_BLUE, border_w=2, radius=14)
        self.screen.blit(self.f_title.render("QUẢN TRỊ HỆ THỐNG & QUẢN LÝ NGƯỜI DÙNG", True, ROYAL_BLUE), (44, 30))

        btn_play = pygame.Rect(WIDTH - 410, 26, 175, 44)
        draw_card(self.screen, btn_play, EMERALD, shadow=False, radius=10)
        p_txt = self.f_small.render("Vào chơi thử Game", True, WHITE)
        self.screen.blit(p_txt, (btn_play.centerx - p_txt.get_width() // 2, btn_play.y + 12))

        btn_ref = pygame.Rect(WIDTH - 225, 26, 100, 44)
        draw_card(self.screen, btn_ref, ROYAL_SOFT, border=ROYAL_BLUE, border_w=1, shadow=False, radius=10)
        r_txt = self.f_small.render("Làm mới", True, ROYAL_BLUE)
        self.screen.blit(r_txt, (btn_ref.centerx - r_txt.get_width() // 2, btn_ref.y + 12))

        btn_out = pygame.Rect(WIDTH - 115, 26, 75, 44)
        draw_card(self.screen, btn_out, BG_SAND, border=LAND_BORDER, border_w=1, shadow=False, radius=10)
        o_txt = self.f_small.render("Thoát", True, INK_DARK)
        self.screen.blit(o_txt, (btn_out.centerx - o_txt.get_width() // 2, btn_out.y + 12))

        # 3 thẻ thống kê tổng quan
        cards_info = [
            ("TỔNG SỐ TÀI KHOẢN", str(self.admin_data.get("total_users", 0)), ROYAL_BLUE, ROYAL_SOFT),
            ("TỔNG LƯỢT TRẢ LỜI CÂU HỎI", str(self.admin_data.get("total_attempts", 0)), GOLD, GOLD_SOFT),
            ("TỶ LỆ TRẢ LỜI ĐÚNG TOÀN HỆ THỐNG", f"{self.admin_data.get('accuracy_rate', 0)}%", EMERALD, EMERALD_SOFT),
        ]
        for idx, (label, val, fg, bg) in enumerate(cards_info):
            c_rect = pygame.Rect(24 + idx * 418, 96, 396, 94)
            draw_card(self.screen, c_rect, bg, border=fg, border_w=2, shadow=False, radius=14)
            self.screen.blit(self.f_small.render(label, True, INK_DARK), (c_rect.x + 20, c_rect.y + 16))
            self.screen.blit(self.f_title.render(val, True, fg), (c_rect.x + 20, c_rect.y + 44))

        # Bảng quản lý danh sách User
        tbl = pygame.Rect(24, 206, WIDTH - 48, 492)
        draw_card(self.screen, tbl, BG_PANEL, border=LAND_BORDER, border_w=1, radius=16)

        col_hdr = pygame.Rect(42, 222, WIDTH - 84, 42)
        pygame.draw.rect(self.screen, BG_SAND, col_hdr, border_radius=10)
        self.screen.blit(self.f_small.render("STT", True, INK_DARK), (58, 232))
        self.screen.blit(self.f_small.render("Tên đăng nhập", True, INK_DARK), (125, 232))
        self.screen.blit(self.f_small.render("Vai trò (Role)", True, INK_DARK), (360, 232))
        self.screen.blit(self.f_small.render("Điểm số", True, INK_DARK), (520, 232))
        self.screen.blit(self.f_small.render("Tiến độ mở khóa", True, INK_DARK), (650, 232))
        self.screen.blit(self.f_small.render("Thao tác quản lý User", True, INK_DARK), (860, 232))

        users = self.admin_data.get("users", [])
        per_page = 6
        max_page = max(0, (len(users) - 1) // per_page)
        self.admin_page = min(self.admin_page, max_page)
        page_users = users[self.admin_page * per_page : (self.admin_page + 1) * per_page]

        ry = 274
        for i, u in enumerate(page_users):
            global_idx = self.admin_page * per_page + i + 1
            uname = u.get("username", "")
            urole = u.get("role", "player")
            uscore = u.get("total_score", 0)
            try:
                comp_cnt = len(json.loads(u.get("completed_events") or "[]"))
            except Exception:
                comp_cnt = 0

            row = pygame.Rect(42, ry, WIDTH - 84, 54)
            draw_card(self.screen, row, WHITE, border=LAND_BORDER, border_w=1, shadow=False, radius=10)

            self.screen.blit(self.f_body.render(f"#{global_idx}", True, INK_MUTED), (58, ry + 15))
            self.screen.blit(self.f_body.render(uname, True, INK_DARK), (125, ry + 15))

            role_bg = ROYAL_SOFT if urole == "admin" else EMERALD_SOFT
            role_fg = ROYAL_BLUE if urole == "admin" else EMERALD
            r_box = pygame.Rect(360, ry + 12, 100, 30)
            pygame.draw.rect(self.screen, role_bg, r_box, border_radius=8)
            self.screen.blit(self.f_small.render(urole.upper(), True, role_fg), (r_box.x + 18, r_box.y + 5))

            self.screen.blit(self.f_body.render(f"{uscore} đ", True, CRIMSON), (520, ry + 15))
            self.screen.blit(self.f_body.render(f"{comp_cnt}/10 mốc", True, INK_DARK), (650, ry + 15))

            # Các nút quản lý từng user
            btn_reset = pygame.Rect(855, ry + 10, 115, 34)
            draw_card(self.screen, btn_reset, GOLD_SOFT, border=GOLD, border_w=1, shadow=False, radius=8)
            t_rst = self.f_badge.render("Reset điểm", True, (140, 90, 0))
            self.screen.blit(t_rst, (btn_reset.centerx - t_rst.get_width() // 2, btn_reset.y + 8))

            btn_role = pygame.Rect(980, ry + 10, 130, 34)
            draw_card(self.screen, btn_role, ROYAL_SOFT, border=ROYAL_BLUE, border_w=1, shadow=False, radius=8)
            t_rl = self.f_badge.render("Đổi Role" if uname != "admin" else "Admin gốc", True, ROYAL_BLUE)
            self.screen.blit(t_rl, (btn_role.centerx - t_rl.get_width() // 2, btn_role.y + 8))

            btn_del = pygame.Rect(1120, ry + 10, 95, 34)
            draw_card(self.screen, btn_del, (252, 224, 224) if uname != "admin" else BG_SAND, border=CRIMSON if uname != "admin" else LAND_BORDER, border_w=1, shadow=False, radius=8)
            t_dl = self.f_badge.render("Xóa User" if uname != "admin" else "Khóa", True, CRIMSON if uname != "admin" else INK_MUTED)
            self.screen.blit(t_dl, (btn_del.centerx - t_dl.get_width() // 2, btn_del.y + 8))

            ry += 60

        # Phân trang danh sách user
        self.screen.blit(self.f_small.render(f"Trang {self.admin_page + 1}/{max_page + 1}  (Tổng {len(users)} tài khoản)", True, INK_MUTED), (50, 650))
        btn_prev = pygame.Rect(WIDTH - 250, 642, 95, 36)
        btn_next = pygame.Rect(WIDTH - 145, 642, 95, 36)
        draw_card(self.screen, btn_prev, BG_SAND, border=LAND_BORDER, border_w=1, shadow=False, radius=8)
        draw_card(self.screen, btn_next, BG_SAND, border=LAND_BORDER, border_w=1, shadow=False, radius=8)
        self.screen.blit(self.f_small.render("<- Trước", True, INK_DARK), (btn_prev.x + 18, btn_prev.y + 8))
        self.screen.blit(self.f_small.render("Sau ->", True, INK_DARK), (btn_next.x + 24, btn_next.y + 8))

    # ==================== RENDER MAP & MODALS ====================

    def draw_top_hud(self):
        hud = pygame.Rect(20, 14, WIDTH - 40, 58)
        draw_card(self.screen, hud, BG_PANEL, border=LAND_BORDER, border_w=1, radius=14)

        self.screen.blit(self.f_h2.render(self.username, True, INK_DARK), (34, 28))

        rank_title, rank_fg, rank_bg = self.get_rank_info()
        r_w = self.f_badge.size(rank_title)[0] + 18
        r_badge = pygame.Rect(34 + self.f_h2.size(self.username)[0] + 12, 29, r_w, 26)
        pygame.draw.rect(self.screen, rank_bg, r_badge, border_radius=8)
        pygame.draw.rect(self.screen, rank_fg, r_badge, width=1, border_radius=8)
        self.screen.blit(self.f_badge.render(rank_title, True, rank_fg), (r_badge.x + 9, r_badge.y + 5))

        self.screen.blit(self.f_body.render("Tim:", True, CRIMSON), (455, 30))
        for h in range(3):
            draw_heart_icon(self.screen, 505 + h * 24, 39, filled=(h < self.hearts))

        self.screen.blit(self.f_small.render(f"Chuỗi: {self.streak}x", True, (200, 110, 0)), (595, 33))
        self.screen.blit(self.f_small.render(f"Mốc: {len(self.completed_ids)}/{len(self.events)}", True, ROYAL_BLUE), (685, 33))

        btn_ach = pygame.Rect(780, 22, 130, 42)
        draw_card(self.screen, btn_ach, GOLD_SOFT, border=GOLD, border_w=1, shadow=False, radius=10)
        ach_txt = self.f_small.render(f"Huy hiệu ({len(self.achievements)}/4)", True, (130, 85, 10))
        self.screen.blit(ach_txt, (btn_ach.centerx - ach_txt.get_width() // 2, btn_ach.y + 11))

        sc_badge = pygame.Rect(920, 22, 155, 42)
        pygame.draw.rect(self.screen, GOLD_SOFT, sc_badge, border_radius=10)
        sc_txt = self.f_h2.render(f"{self.score} ĐIỂM", True, (150, 100, 0))
        self.screen.blit(sc_txt, (sc_badge.centerx - sc_txt.get_width() // 2, sc_badge.y + 7))

        btn_snd = pygame.Rect(1085, 22, 75, 42)
        draw_card(self.screen, btn_snd, EMERALD_SOFT if self.sfx.enabled else BG_SAND, border=EMERALD if self.sfx.enabled else LAND_BORDER, border_w=1, shadow=False, radius=10)
        snd_txt = self.f_badge.render("Loa: Bật" if self.sfx.enabled else "Loa: Tắt", True, EMERALD if self.sfx.enabled else INK_MUTED)
        self.screen.blit(snd_txt, (btn_snd.centerx - snd_txt.get_width() // 2, btn_snd.y + 13))

        btn_out = pygame.Rect(1170, 22, 75, 42)
        draw_card(self.screen, btn_out, ROYAL_SOFT if self.user_role == "admin" else BG_SAND, border=ROYAL_BLUE if self.user_role == "admin" else LAND_BORDER, border_w=1, shadow=False, radius=10)
        out_txt = self.f_badge.render("Admin" if self.user_role == "admin" else "Thoát", True, ROYAL_BLUE if self.user_role == "admin" else INK_DARK)
        self.screen.blit(out_txt, (btn_out.centerx - out_txt.get_width() // 2, btn_out.y + 13))

    def draw_map_view(self):
        self.screen.fill(BG_SAND)
        self.draw_top_hud()

        map_rect = pygame.Rect(20, 86, 760, 614)
        draw_card(self.screen, map_rect, SEA_BLUE, border=LAND_BORDER, border_w=2, radius=16)

        for gx in range(map_rect.x + 60, map_rect.right, 75):
            pygame.draw.line(self.screen, SEA_GRID, (gx, map_rect.y + 12), (gx, map_rect.bottom - 12), 1)
        for gy in range(map_rect.y + 60, map_rect.bottom, 75):
            pygame.draw.line(self.screen, SEA_GRID, (map_rect.x + 12, gy), (map_rect.right - 12, gy), 1)
        pygame.draw.rect(self.screen, LAND_BORDER, map_rect.inflate(-16, -16), width=1, border_radius=12)

        shelf_poly = [(x + 4, y + 6) for (x, y) in self.vn_mainland]
        shadow_poly = [(x + 8, y + 10) for (x, y) in self.vn_mainland]
        pygame.draw.polygon(self.screen, (175, 202, 218), shadow_poly)
        pygame.draw.polygon(self.screen, (195, 224, 236), shelf_poly)

        pygame.draw.polygon(self.screen, LAND_FILL, self.vn_mainland)
        pygame.draw.polygon(self.screen, (150, 120, 78), self.vn_mainland, width=3)
        for island in (self.phu_quoc, self.con_dao):
            pygame.draw.polygon(self.screen, LAND_FILL, island)
            pygame.draw.polygon(self.screen, (150, 120, 78), island, width=2)

        truong_son = [(452, 240), (470, 295), (495, 350), (535, 405), (562, 465), (545, 520)]
        pygame.draw.lines(self.screen, (214, 198, 166), False, truong_son, 6)
        song_hong = [(425, 118), (475, 152), (528, 174)]
        song_mekong = [(465, 555), (505, 575), (535, 592)]
        pygame.draw.lines(self.screen, (145, 195, 222), False, song_hong, 3)
        pygame.draw.lines(self.screen, (145, 195, 222), False, song_mekong, 3)

        cx, cy = 115, 600
        pygame.draw.circle(self.screen, BG_PANEL, (cx, cy), 42)
        pygame.draw.circle(self.screen, LAND_BORDER, (cx, cy), 42, width=2)
        pygame.draw.circle(self.screen, GOLD, (cx, cy), 34, width=1)
        pygame.draw.polygon(self.screen, CRIMSON, [(cx, cy - 36), (cx - 7, cy), (cx + 7, cy)])
        pygame.draw.polygon(self.screen, INK_MUTED, [(cx, cy + 36), (cx - 7, cy), (cx + 7, cy)])
        pygame.draw.polygon(self.screen, GOLD, [(cx - 32, cy), (cx, cy - 6), (cx, cy + 6)])
        pygame.draw.polygon(self.screen, GOLD, [(cx + 32, cy), (cx, cy - 6), (cx, cy + 6)])
        n_lbl = self.f_badge.render("B", True, CRIMSON)
        self.screen.blit(n_lbl, (cx - n_lbl.get_width() // 2, cy - 55))

        for pos, name, offsets in [
            ((668, 340), "QĐ. Hoàng Sa", [(-10, -6), (8, -8), (2, 7), (-12, 8)]),
            ((688, 535), "QĐ. Trường Sa", [(-12, -8), (10, -5), (-4, 9), (12, 8), (0, -12)])
        ]:
            pygame.draw.circle(self.screen, (195, 224, 236), pos, 26)
            pygame.draw.circle(self.screen, CRIMSON, pos, 26, width=1)
            for ox, oy in offsets:
                pygame.draw.circle(self.screen, LAND_FILL, (pos[0] + ox, pos[1] + oy), 4)
                pygame.draw.circle(self.screen, (150, 120, 78), (pos[0] + ox, pos[1] + oy), 4, width=1)
            lbl = self.f_badge.render(name, True, CRIMSON)
            self.screen.blit(lbl, (pos[0] - lbl.get_width() // 2, pos[1] + 30))

        unlocked_pts = []
        for idx, ev in enumerate(self.events):
            if idx < self.unlocked_count:
                dx, dy = self.pin_offsets.get(str(ev["year"]), (0, 0))
                unlocked_pts.append((ev["x"] + dx, ev["y"] + dy))
        if len(unlocked_pts) > 1:
            pygame.draw.lines(self.screen, EMERALD, False, unlocked_pts, 2)

        mouse_pos = pygame.mouse.get_pos()
        hovered_info = None
        pulse = (math.sin(self.anim_time * 4) + 1) * 0.5
        bounce = math.sin(self.anim_time * 5) * 4

        for idx, ev in enumerate(self.events):
            dx, dy = self.pin_offsets.get(str(ev["year"]), (0, 0))
            ex, ey = ev["x"] + dx, ev["y"] + dy
            status = self.get_event_status(idx, ev)
            is_hover = math.hypot(mouse_pos[0] - ex, mouse_pos[1] - ey) < 18
            if is_hover:
                hovered_info = (idx, ev, status)

            if status == "UNLOCKED":
                pygame.draw.circle(self.screen, CRIMSON_LIGHT, (ex, ey), int(12 + pulse * 11), width=2)
                ay = int(ey - 22 + bounce)
                pygame.draw.polygon(self.screen, GOLD, [(ex, ay + 9), (ex - 7, ay), (ex + 7, ay)])
                pygame.draw.polygon(self.screen, CRIMSON, [(ex, ay + 9), (ex - 7, ay), (ex + 7, ay)], width=1)

            pin_color = EMERALD if status == "DONE" else (CRIMSON if status == "UNLOCKED" else LOCKED_GRAY)
            pygame.draw.circle(self.screen, WHITE, (ex, ey), 11 if is_hover else 9)
            pygame.draw.circle(self.screen, pin_color, (ex, ey), 8 if is_hover else 6)

            yr_label = f"#{idx+1} {ev['year']}" if status != "LOCKED" else f"#{idx+1} Khóa"
            yr_surf = self.f_badge.render(yr_label, True, INK_DARK if status != "LOCKED" else INK_MUTED)
            yr_box = pygame.Rect(ex + 11, ey - 9, yr_surf.get_width() + 8, 18)
            pygame.draw.rect(self.screen, BG_PANEL if status != "LOCKED" else (235, 230, 222), yr_box, border_radius=5)
            pygame.draw.rect(self.screen, LAND_BORDER, yr_box, width=1, border_radius=5)
            self.screen.blit(yr_surf, (yr_box.x + 4, yr_box.y + 1))

        pygame.draw.circle(self.screen, ROYAL_BLUE, (int(self.explorer_x), int(self.explorer_y) - 14), 8)
        pygame.draw.circle(self.screen, WHITE, (int(self.explorer_x), int(self.explorer_y) - 14), 8, width=2)

        if hovered_info:
            h_idx, h_ev, h_status = hovered_info
            tip = pygame.Rect(min(mouse_pos[0] + 16, 480), max(mouse_pos[1] - 48, 96), 295, 72)
            draw_card(self.screen, tip, BG_PANEL, border=CRIMSON if h_status != "LOCKED" else INK_MUTED, border_w=2, radius=10)
            self.screen.blit(self.f_small.render(f"Mốc {h_idx+1} [{h_ev['year']}]: {h_ev['title']}", True, CRIMSON if h_status != "LOCKED" else INK_MUTED), (tip.x + 10, tip.y + 10))
            sub_tip = "Bấm để đọc tư liệu & làm 5 câu hỏi!" if h_status != "LOCKED" else f"Hoàn thành Mốc {h_idx} để mở khóa!"
            self.screen.blit(self.f_badge.render(sub_tip, True, INK_DARK), (tip.x + 10, tip.y + 38))

        side_top = pygame.Rect(800, 86, 460, 368)
        draw_card(self.screen, side_top, BG_PANEL, border=GOLD, border_w=2, radius=16)
        self.screen.blit(self.f_h2.render("HÀNH TRÌNH 10 MỐC LỊCH SỬ", True, CRIMSON), (820, 100))

        arena_unlocked = (len(self.completed_ids) >= len(self.events)) or (self.score >= 1500) or (self.user_role == "admin")
        btn_arena = pygame.Rect(820, 132, 420, 36)
        draw_card(self.screen, btn_arena, PURPLE_ARENA if arena_unlocked else PURPLE_SOFT, border=PURPLE_ARENA, border_w=1, shadow=False, radius=9)
        ar_lbl = "ĐẤU TRƯỜNG 50 CÂU (Tốc độ 12s) — Bấm vào thi!" if arena_unlocked else "Đấu trường 50 câu (Mở khi xong 10 mốc hoặc 1.500đ)"
        ar_txt = self.f_badge.render(ar_lbl, True, WHITE if arena_unlocked else PURPLE_ARENA)
        self.screen.blit(ar_txt, (btn_arena.centerx - ar_txt.get_width() // 2, btn_arena.y + 9))

        start_idx = max(0, min(self.unlocked_count - 2, len(self.events) - 4))
        visible_events = list(enumerate(self.events))[start_idx:start_idx + 4]
        ny = 178
        for idx, ev in visible_events:
            status = self.get_event_status(idx, ev)
            row = pygame.Rect(820, ny, 420, 62)
            r_hover = row.collidepoint(mouse_pos) and status != "LOCKED"

            if status == "DONE":
                bg_c, bd_c = EMERALD_SOFT, EMERALD
            elif status == "UNLOCKED":
                bg_c, bd_c = (GOLD_SOFT if r_hover else WHITE), CRIMSON
            else:
                bg_c, bd_c = (236, 231, 223), LAND_BORDER

            draw_card(self.screen, row, bg_c, border=bd_c, border_w=2 if status == "UNLOCKED" else 1, shadow=False, radius=10)
            self.screen.blit(self.f_small.render(f"Mốc {idx+1} [{ev['year']}]: {ev['title']}", True, INK_DARK if status != "LOCKED" else INK_MUTED), (row.x + 12, row.y + 8))

            if status == "DONE":
                st_txt = "Đã hoàn thành 5/5 câu (Bấm để ôn tập lại)"
                st_c = EMERALD
            elif status == "UNLOCKED":
                st_txt = "ĐANG MỞ KHÓA — Bấm đọc tư liệu & làm bài!"
                st_c = CRIMSON
            else:
                st_txt = f"Đang khóa — Hoàn thành Mốc {idx} để mở"
                st_c = INK_MUTED
            self.screen.blit(self.f_badge.render(st_txt, True, st_c), (row.x + 12, row.y + 34))
            ny += 67

        side_bot = pygame.Rect(800, 466, 460, 234)
        draw_card(self.screen, side_bot, BG_PANEL, border=LAND_BORDER, border_w=1, radius=16)
        self.screen.blit(self.f_h2.render("BẢNG VÀNG NGƯỜI CHƠI", True, (150, 100, 0)), (820, 480))

        ly = 516
        if not self.leaderboard:
            self.screen.blit(self.f_small.render("Đang tải bảng xếp hạng...", True, INK_MUTED), (820, ly))
        else:
            for idx, entry in enumerate(self.leaderboard[:4]):
                r_rect = pygame.Rect(820, ly, 420, 36)
                pygame.draw.rect(self.screen, GOLD_SOFT if idx == 0 else BG_SAND, r_rect, border_radius=8)
                self.screen.blit(self.f_small.render(f"#{idx+1}  {entry.get('username', 'Ẩn danh')}", True, INK_DARK), (r_rect.x + 12, r_rect.y + 8))
                pts_s = self.f_small.render(f"{entry.get('total_score', 0)} đ", True, CRIMSON)
                self.screen.blit(pts_s, (r_rect.right - pts_s.get_width() - 12, r_rect.y + 8))
                ly += 42

    def draw_achievements_modal(self):
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((25, 20, 18, 175))
        self.screen.blit(dim, (0, 0))

        modal = pygame.Rect(WIDTH // 2 - 390, 95, 780, 530)
        draw_card(self.screen, modal, BG_PANEL, border=GOLD, border_w=3, radius=20)

        self.screen.blit(self.f_title.render("BỘ SƯU TẬP HUY HIỆU SỬ KÝ", True, CRIMSON), (modal.x + 34, modal.y + 26))
        rank_title, rank_fg, _ = self.get_rank_info()
        self.screen.blit(self.f_small.render(f"Danh hiệu hiện tại: {rank_title} ({self.score} điểm)", True, rank_fg), (modal.x + 34, modal.y + 66))

        badge_defs = [
            ("FIRST_BLOOD", "Khởi đầu hào hùng", "Hoàn thành trọn vẹn 5 câu hỏi của mốc lịch sử đầu tiên."),
            ("SPEEDSTER", "Thần tốc đại phá", "Trả lời chính xác một câu hỏi lịch sử trong vòng dưới 5 giây."),
            ("UNTOUCHABLE", "Bất bại trên chiến trường", "Vượt qua trọn vẹn 5/5 câu của một mốc mà không dùng gợi ý."),
            ("CONQUEROR", "Chinh phục giang sơn", "Mở khóa và hoàn thành toàn bộ 10/10 mốc lịch sử Việt Nam."),
        ]

        ay = modal.y + 108
        for code, title, desc in badge_defs:
            unlocked = code in self.achievements
            row = pygame.Rect(modal.x + 34, ay, 712, 76)
            draw_card(self.screen, row, EMERALD_SOFT if unlocked else BG_SAND, border=EMERALD if unlocked else LAND_BORDER, border_w=2 if unlocked else 1, shadow=False, radius=12)

            st_tag = "ĐÃ ĐẠT" if unlocked else "CHƯA MỞ"
            tag_rect = pygame.Rect(row.x + 16, row.y + 22, 92, 32)
            pygame.draw.rect(self.screen, EMERALD if unlocked else LOCKED_GRAY, tag_rect, border_radius=8)
            t_s = self.f_badge.render(st_tag, True, WHITE)
            self.screen.blit(t_s, (tag_rect.centerx - t_s.get_width() // 2, tag_rect.y + 8))

            self.screen.blit(self.f_h2.render(title, True, INK_DARK if unlocked else INK_MUTED), (row.x + 124, row.y + 12))
            self.screen.blit(self.f_small.render(desc, True, INK_DARK if unlocked else INK_MUTED), (row.x + 124, row.y + 42))
            ay += 86

        btn_close = pygame.Rect(modal.centerx - 130, modal.bottom - 68, 260, 46)
        draw_card(self.screen, btn_close, CRIMSON, shadow=True, radius=12)
        c_txt = self.f_body.render("ĐÓNG BẢNG HUY HIỆU", True, WHITE)
        self.screen.blit(c_txt, (btn_close.centerx - c_txt.get_width() // 2, btn_close.y + 11))

    def draw_story_modal(self):
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((25, 20, 18, 175))
        self.screen.blit(dim, (0, 0))

        ev = self.selected_event
        modal = pygame.Rect(WIDTH // 2 - 420, 75, 840, 570)
        draw_card(self.screen, modal, BG_PANEL, border=GOLD, border_w=3, radius=20)

        badge = pygame.Rect(modal.x + 32, modal.y + 24, 340, 32)
        pygame.draw.rect(self.screen, ROYAL_SOFT, badge, border_radius=10)
        self.screen.blit(self.f_small.render(f"MỐC {self.selected_idx + 1}/{len(self.events)}  |  {ev['era']} ({ev['year']})", True, ROYAL_BLUE), (badge.x + 14, badge.y + 6))

        self.screen.blit(self.f_title.render(ev["title"], True, CRIMSON), (modal.x + 32, modal.y + 68))
        self.screen.blit(self.f_small.render(f"Địa danh lịch sử: {ev['location']}", True, INK_MUTED), (modal.x + 32, modal.y + 106))

        story_box = pygame.Rect(modal.x + 32, modal.y + 138, 776, 330)
        draw_card(self.screen, story_box, BG_SAND, border=LAND_BORDER, border_w=1, shadow=False, radius=14)
        self.screen.blit(self.f_small.render("DỮ KIỆN & BỐI CẢNH LỊCH SỬ (Đọc kỹ trước khi làm 5 câu hỏi):", True, ROYAL_BLUE), (story_box.x + 20, story_box.y + 14))

        story_text = ev.get("story") or ev.get("fact", "")
        draw_wrapped_text(
            self.screen, story_text, self.f_body, INK_DARK,
            pygame.Rect(story_box.x + 20, story_box.y + 46, 736, 268),
            line_spacing=8
        )

        btn_back = pygame.Rect(modal.x + 32, modal.bottom - 76, 190, 50)
        draw_card(self.screen, btn_back, BG_SAND, border=LAND_BORDER, border_w=1, shadow=False, radius=12)
        b_txt = self.f_body.render("<- Về bản đồ", True, INK_DARK)
        self.screen.blit(b_txt, (btn_back.centerx - b_txt.get_width() // 2, btn_back.y + 13))

        btn_start = pygame.Rect(modal.right - 392, modal.bottom - 76, 360, 50)
        hover = btn_start.collidepoint(pygame.mouse.get_pos())
        draw_card(self.screen, btn_start, CRIMSON_LIGHT if hover else CRIMSON, shadow=True, radius=12)
        s_txt = self.f_h2.render("BẮT ĐẦU LÀM 5 CÂU HỎI ->", True, WHITE)
        self.screen.blit(s_txt, (btn_start.centerx - s_txt.get_width() // 2, btn_start.y + 11))

    def draw_quiz_overlay(self):
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((25, 20, 18, 170))
        self.screen.blit(dim, (0, 0))

        ev = self.selected_event
        q_obj = self.arena_pool[self.q_index % len(self.arena_pool)][1] if self.arena_mode else ev["questions"][self.q_index]
        total_q = len(ev["questions"])

        modal = pygame.Rect(WIDTH // 2 - 430, 55, 860, 610)
        draw_card(self.screen, modal, BG_PANEL, border=PURPLE_ARENA if self.arena_mode else GOLD, border_w=3, radius=20)

        era_badge = pygame.Rect(modal.x + 30, modal.y + 20, 290, 32)
        pygame.draw.rect(self.screen, PURPLE_SOFT if self.arena_mode else GOLD_SOFT, era_badge, border_radius=10)
        badge_str = f"ĐẤU TRƯỜNG — Đã đúng: {self.arena_solved} câu" if self.arena_mode else f"{ev['era']} ({ev['year']})"
        self.screen.blit(self.f_small.render(badge_str, True, PURPLE_ARENA if self.arena_mode else (130, 85, 10)), (era_badge.x + 12, era_badge.y + 6))

        if not self.arena_mode:
            step_x = modal.centerx - 95
            for s in range(total_q):
                c_rect = pygame.Rect(step_x + s * 40, modal.y + 20, 32, 32)
                if s < self.q_index:
                    c_bg, c_fg = EMERALD, WHITE
                elif s == self.q_index:
                    c_bg, c_fg = CRIMSON, WHITE
                else:
                    c_bg, c_fg = BG_SAND, INK_MUTED
                pygame.draw.rect(self.screen, c_bg, c_rect, border_radius=8)
                s_lbl = self.f_small.render(str(s + 1), True, c_fg)
                self.screen.blit(s_lbl, (c_rect.centerx - s_lbl.get_width() // 2, c_rect.y + 6))

        timer_color = CRIMSON if self.quiz_timer < 5.0 else EMERALD
        t_txt = self.f_h2.render(f"{int(math.ceil(self.quiz_timer))}s", True, timer_color)
        self.screen.blit(t_txt, (modal.right - t_txt.get_width() - 35, modal.y + 22))

        header_title = f"[{ev['year']}] {ev['title']}" if self.arena_mode else f"{ev['title']} — Câu {self.q_index + 1}/{total_q}"
        self.screen.blit(self.f_title.render(header_title, True, PURPLE_ARENA if self.arena_mode else CRIMSON), (modal.x + 30, modal.y + 62))

        q_box = pygame.Rect(modal.x + 30, modal.y + 104, 800, 82)
        draw_card(self.screen, q_box, BG_SAND, border=LAND_BORDER, border_w=1, shadow=False, radius=12)
        draw_wrapped_text(self.screen, q_obj["q"], self.f_body, INK_DARK, pygame.Rect(q_box.x + 18, q_box.y + 12, 764, 62))

        if self.active_hint_text:
            h_box = pygame.Rect(modal.x + 30, modal.y + 194, 800, 56)
            draw_card(self.screen, h_box, ROYAL_SOFT, border=ROYAL_BLUE, border_w=1, shadow=False, radius=10)
            draw_wrapped_text(self.screen, self.active_hint_text, self.f_small, ROYAL_BLUE, pygame.Rect(h_box.x + 14, h_box.y + 7, 772, 44), line_spacing=3)

        labels = ["A", "B", "C", "D"]
        mouse_pos = pygame.mouse.get_pos()
        opt_start_y = modal.y + (260 if self.active_hint_text else 210)
        for i, opt in enumerate(self.shuffled_options):
            col = i % 2
            row = i // 2
            btn = pygame.Rect(modal.x + 30 + col * 410, opt_start_y + row * 108, 390, 94)
            eliminated = i in self.eliminated_options
            hover = btn.collidepoint(mouse_pos) and not eliminated

            bg_c = (230, 225, 218) if eliminated else (GOLD_SOFT if hover else WHITE)
            bd_c = INK_MUTED if eliminated else (CRIMSON if hover else LAND_BORDER)
            draw_card(self.screen, btn, bg_c, border=bd_c, border_w=2 if hover else 1, shadow=not eliminated, radius=12)

            pygame.draw.circle(self.screen, INK_MUTED if eliminated else CRIMSON, (btn.x + 28, btn.centery), 17)
            l_img = self.f_body.render(labels[i], True, WHITE)
            self.screen.blit(l_img, (btn.x + 28 - l_img.get_width() // 2, btn.centery - l_img.get_height() // 2))

            disp_opt = "Đã loại bỏ (50/50)" if eliminated else opt
            draw_wrapped_text(
                self.screen, disp_opt, self.f_small,
                INK_MUTED if eliminated else INK_DARK,
                pygame.Rect(btn.x + 56, btn.y + 14, 320, 70),
                line_spacing=4
            )

        btn_story_hint = pygame.Rect(modal.x + 30, modal.bottom - 62, 220, 44)
        sh_avail = (not self.active_hint_text) and (self.score >= 15)
        draw_card(self.screen, btn_story_hint, ROYAL_BLUE if sh_avail else BG_SAND, border=ROYAL_BLUE if not self.active_hint_text else LAND_BORDER, border_w=1, shadow=False, radius=10)
        sh_lbl = self.f_small.render("Gợi ý sử liệu (-15đ)" if not self.active_hint_text else "Đã mở gợi ý", True, WHITE if sh_avail else INK_MUTED)
        self.screen.blit(sh_lbl, (btn_story_hint.centerx - sh_lbl.get_width() // 2, btn_story_hint.y + 12))

        btn_hint = pygame.Rect(modal.x + 262, modal.bottom - 62, 210, 44)
        h_active = self.hints_left > 0
        draw_card(self.screen, btn_hint, GOLD if h_active else BG_SAND, shadow=False, radius=10)
        h_lbl = self.f_small.render(f"50/50 (Còn {self.hints_left})", True, WHITE if h_active else INK_MUTED)
        self.screen.blit(h_lbl, (btn_hint.centerx - h_lbl.get_width() // 2, btn_hint.y + 12))

        if not self.arena_mode:
            btn_story = pygame.Rect(modal.x + 484, modal.bottom - 62, 185, 44)
            draw_card(self.screen, btn_story, ROYAL_SOFT, border=ROYAL_BLUE, border_w=1, shadow=False, radius=10)
            st_lbl = self.f_small.render("Đọc lại tư liệu", True, ROYAL_BLUE)
            self.screen.blit(st_lbl, (btn_story.centerx - st_lbl.get_width() // 2, btn_story.y + 12))

        btn_back = pygame.Rect(modal.right - 180, modal.bottom - 62, 150, 44)
        draw_card(self.screen, btn_back, BG_SAND, border=LAND_BORDER, border_w=1, shadow=False, radius=10)
        b_lbl = self.f_small.render("Về bản đồ", True, INK_DARK)
        self.screen.blit(b_lbl, (btn_back.centerx - b_lbl.get_width() // 2, btn_back.y + 12))

    def draw_result_modal(self):
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((25, 20, 18, 170))
        self.screen.blit(dim, (0, 0))

        ev = self.selected_event
        modal = pygame.Rect(WIDTH // 2 - 380, 120, 760, 480)
        accent = EMERALD if self.stage_passed else CRIMSON
        draw_card(self.screen, modal, BG_PANEL, border=accent, border_w=3, radius=20)

        if self.stage_passed:
            head = "HOÀN THÀNH 5/5 CÂU — MỞ KHÓA MỐC MỚI!"
            sub_s = f"Chúc mừng! Bạn nhận +{self.stage_points_earned} điểm (gồm +150đ thưởng vượt ải)!"
        else:
            head = f"CHƯA QUA ẢI (DỪNG Ở CÂU {self.q_index + 1}/5)"
            sub_s = f"Đáp án đúng là: {self.last_correct_ans_text}"

        h_img = self.f_h2.render(head, True, accent)
        self.screen.blit(h_img, (modal.centerx - h_img.get_width() // 2, modal.y + 28))

        s_img = self.f_body.render(sub_s, True, INK_DARK)
        self.screen.blit(s_img, (modal.centerx - s_img.get_width() // 2, modal.y + 72))

        fact_box = pygame.Rect(modal.x + 35, modal.y + 122, 690, 240)
        draw_card(self.screen, fact_box, EMERALD_SOFT if self.stage_passed else GOLD_SOFT, shadow=False, radius=14)
        self.screen.blit(self.f_small.render(f"TỔNG KẾT LỊCH SỬ: [{ev['year']}] {ev['title']}", True, accent), (fact_box.x + 18, fact_box.y + 14))
        draw_wrapped_text(self.screen, ev["fact"], self.f_body, INK_DARK, pygame.Rect(fact_box.x + 18, fact_box.y + 46, 654, 175))

        btn_cont = pygame.Rect(modal.centerx - 175, modal.bottom - 76, 350, 52)
        draw_card(self.screen, btn_cont, accent, shadow=True, radius=12)
        btn_txt = "CHINH PHỤC MỐC TIẾP THEO" if self.stage_passed else "ĐỌC LẠI TƯ LIỆU & THỬ LẠI"
        c_txt = self.f_h2.render(btn_txt, True, WHITE)
        self.screen.blit(c_txt, (btn_cont.centerx - c_txt.get_width() // 2, btn_cont.y + 12))

    def draw_gameover_modal(self):
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((25, 20, 18, 180))
        self.screen.blit(dim, (0, 0))

        modal = pygame.Rect(WIDTH // 2 - 320, 180, 640, 360)
        draw_card(self.screen, modal, BG_PANEL, border=CRIMSON, border_w=3, radius=20)

        t1 = self.f_title.render("HẾT LƯỢT THỬ THÁCH!", True, CRIMSON)
        self.screen.blit(t1, (modal.centerx - t1.get_width() // 2, modal.y + 40))

        t2 = self.f_body.render(f"Tổng điểm hiện tại của bạn: {self.score} điểm", True, INK_DARK)
        self.screen.blit(t2, (modal.centerx - t2.get_width() // 2, modal.y + 110))

        t3 = self.f_small.render("Bấm nút bên dưới để hồi phục 3 Tim và chinh phục tiếp các mốc đang mở!", True, INK_MUTED)
        self.screen.blit(t3, (modal.centerx - t3.get_width() // 2, modal.y + 155))

        btn_retry = pygame.Rect(modal.centerx - 150, modal.bottom - 95, 300, 54)
        draw_card(self.screen, btn_retry, EMERALD, shadow=True, radius=12)
        r_txt = self.f_h2.render("HỒI PHỤC 3 TIM & CHƠI TIẾP", True, WHITE)
        self.screen.blit(r_txt, (btn_retry.centerx - r_txt.get_width() // 2, btn_retry.y + 13))

    def draw_toast(self):
        if self.toast_timer > 0 and self.toast_text:
            t_surf = self.f_small.render(self.toast_text, True, WHITE)
            box = pygame.Rect(WIDTH - t_surf.get_width() - 60, HEIGHT - 65, t_surf.get_width() + 36, 42)
            pygame.draw.rect(self.screen, self.toast_color, box, border_radius=10)
            self.screen.blit(t_surf, (box.x + 18, box.y + 11))

    async def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            self.anim_time += dt

            if self.toast_timer > 0:
                self.toast_timer -= dt

            self.explorer_x += (self.target_x - self.explorer_x) * min(1.0, dt * 6.0)
            self.explorer_y += (self.target_y - self.explorer_y) * min(1.0, dt * 6.0)

            if self.state == "QUIZ":
                self.quiz_timer -= dt
                if self.quiz_timer <= 0:
                    self.quiz_timer = 0
                    self.submit_answer(-1)

            for p in self.particles[:]:
                p.update(dt)
                if p.life <= 0:
                    self.particles.remove(p)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos

                    if self.state == "AUTH":
                        card_h = 525 if self.auth_tab == "REGISTER" else 450
                        card_y = (HEIGHT - card_h) // 2
                        card_x = WIDTH // 2 - 250

                        tab_bar = pygame.Rect(card_x + 40, card_y + 88, 420, 42)
                        if pygame.Rect(tab_bar.x + 4, tab_bar.y + 4, 205, 34).collidepoint(mx, my):
                            self.sfx.play("click")
                            self.auth_tab = "LOGIN"
                            self.status_msg = ""
                            continue
                        elif pygame.Rect(tab_bar.x + 211, tab_bar.y + 4, 205, 34).collidepoint(mx, my):
                            self.sfx.play("click")
                            self.auth_tab = "REGISTER"
                            self.status_msg = ""
                            continue

                        y_cur = card_y + 146
                        if pygame.Rect(card_x + 40, y_cur + 22, 420, 44).collidepoint(mx, my):
                            self.active_field = "username"
                        elif pygame.Rect(card_x + 40, y_cur + 78 + 22, 420, 44).collidepoint(mx, my):
                            self.active_field = "password"

                        y_next = y_cur + 156
                        if self.auth_tab == "REGISTER":
                            if pygame.Rect(card_x + 40, y_next + 22, 420, 44).collidepoint(mx, my):
                                self.active_field = "confirm"
                            y_next += 78

                        if pygame.Rect(card_x + 40, y_next + 8, 420, 50).collidepoint(mx, my) and not self.loading:
                            asyncio.create_task(self.handle_auth_submit())

                    elif self.state == "ADMIN":
                        if pygame.Rect(WIDTH - 410, 26, 175, 44).collidepoint(mx, my):
                            self.sfx.play("click")
                            self.state = "MAP"
                            asyncio.create_task(self.fetch_leaderboard())
                            continue
                        if pygame.Rect(WIDTH - 225, 26, 100, 44).collidepoint(mx, my):
                            self.sfx.play("click")
                            asyncio.create_task(self.fetch_admin_data())
                            continue
                        if pygame.Rect(WIDTH - 115, 26, 75, 44).collidepoint(mx, my):
                            self.sfx.play("click")
                            self.state = "AUTH"
                            continue

                        users = self.admin_data.get("users", [])
                        per_page = 6
                        max_page = max(0, (len(users) - 1) // per_page)
                        if pygame.Rect(WIDTH - 250, 642, 95, 36).collidepoint(mx, my) and self.admin_page > 0:
                            self.sfx.play("click")
                            self.admin_page -= 1
                            continue
                        if pygame.Rect(WIDTH - 145, 642, 95, 36).collidepoint(mx, my) and self.admin_page < max_page:
                            self.sfx.play("click")
                            self.admin_page += 1
                            continue

                        page_users = users[self.admin_page * per_page : (self.admin_page + 1) * per_page]
                        ry = 274
                        for u in page_users:
                            uname = u.get("username", "")
                            urole = u.get("role", "player")
                            if pygame.Rect(855, ry + 10, 115, 34).collidepoint(mx, my):
                                asyncio.create_task(self.admin_user_action("reset", uname))
                                break
                            if pygame.Rect(980, ry + 10, 130, 34).collidepoint(mx, my):
                                next_role = "player" if urole == "admin" else "admin"
                                asyncio.create_task(self.admin_user_action("role", uname, next_role))
                                break
                            if pygame.Rect(1120, ry + 10, 95, 34).collidepoint(mx, my):
                                asyncio.create_task(self.admin_user_action("delete", uname))
                                break
                            ry += 60

                    elif self.state == "MAP":
                        if pygame.Rect(780, 22, 130, 42).collidepoint(mx, my):
                            self.sfx.play("click")
                            self.state = "ACHIEVEMENTS"
                            continue
                        if pygame.Rect(1085, 22, 75, 42).collidepoint(mx, my):
                            self.sfx.enabled = not self.sfx.enabled
                            self.sfx.play("click")
                            continue
                        if pygame.Rect(1170, 22, 75, 42).collidepoint(mx, my):
                            self.sfx.play("click")
                            if self.user_role == "admin":
                                self.state = "ADMIN"
                                asyncio.create_task(self.fetch_admin_data())
                            else:
                                self.state = "AUTH"
                            continue
                        if pygame.Rect(820, 132, 420, 36).collidepoint(mx, my):
                            self.start_arena_mode()
                            continue

                        clicked_pair = None
                        for idx, ev in enumerate(self.events):
                            dx, dy = self.pin_offsets.get(str(ev["year"]), (0, 0))
                            if math.hypot(mx - (ev["x"] + dx), my - (ev["y"] + dy)) < 20:
                                clicked_pair = (idx, ev)
                                break

                        if not clicked_pair:
                            start_idx = max(0, min(self.unlocked_count - 2, len(self.events) - 4))
                            visible_events = list(enumerate(self.events))[start_idx:start_idx + 4]
                            ny = 178
                            for idx, ev in visible_events:
                                if pygame.Rect(820, ny, 420, 62).collidepoint(mx, my):
                                    clicked_pair = (idx, ev)
                                    break
                                ny += 67

                        if clicked_pair:
                            self.open_event_story(clicked_pair[0], clicked_pair[1])

                    elif self.state == "ACHIEVEMENTS":
                        modal = pygame.Rect(WIDTH // 2 - 390, 95, 780, 530)
                        if pygame.Rect(modal.centerx - 130, modal.bottom - 68, 260, 46).collidepoint(mx, my):
                            self.sfx.play("click")
                            self.state = "MAP"

                    elif self.state == "STORY_MODAL":
                        modal = pygame.Rect(WIDTH // 2 - 420, 75, 840, 570)
                        if pygame.Rect(modal.x + 32, modal.bottom - 76, 190, 50).collidepoint(mx, my):
                            self.sfx.play("click")
                            self.state = "MAP"
                        elif pygame.Rect(modal.right - 392, modal.bottom - 76, 360, 50).collidepoint(mx, my):
                            self.begin_quiz_questions()

                    elif self.state == "QUIZ":
                        modal_x = WIDTH // 2 - 430
                        modal_y = 55
                        opt_start_y = modal_y + (260 if self.active_hint_text else 210)
                        for i in range(4):
                            col = i % 2
                            row = i // 2
                            btn = pygame.Rect(modal_x + 30 + col * 410, opt_start_y + row * 108, 390, 94)
                            if btn.collidepoint(mx, my):
                                self.submit_answer(i)
                        if pygame.Rect(modal_x + 30, modal_y + 610 - 62, 220, 44).collidepoint(mx, my):
                            self.use_story_hint()
                        if pygame.Rect(modal_x + 262, modal_y + 610 - 62, 210, 44).collidepoint(mx, my):
                            self.use_hint_5050()
                        if not self.arena_mode and pygame.Rect(modal_x + 484, modal_y + 610 - 62, 185, 44).collidepoint(mx, my):
                            self.sfx.play("click")
                            self.state = "STORY_MODAL"
                        if pygame.Rect(modal_x + 860 - 180, modal_y + 610 - 62, 150, 44).collidepoint(mx, my):
                            self.sfx.play("click")
                            self.arena_mode = False
                            self.state = "MAP"

                    elif self.state == "RESULT_MODAL":
                        modal = pygame.Rect(WIDTH // 2 - 380, 120, 760, 480)
                        if pygame.Rect(modal.centerx - 175, modal.bottom - 76, 350, 52).collidepoint(mx, my):
                            self.sfx.play("click")
                            if self.stage_passed:
                                self.state = "MAP"
                            else:
                                self.state = "STORY_MODAL"

                    elif self.state == "GAMEOVER":
                        modal = pygame.Rect(WIDTH // 2 - 320, 180, 640, 360)
                        if pygame.Rect(modal.centerx - 150, modal.bottom - 95, 300, 54).collidepoint(mx, my):
                            self.reset_run()

                elif event.type == pygame.KEYDOWN:
                    if self.state == "AUTH":
                        if event.key == pygame.K_RETURN and not self.loading:
                            asyncio.create_task(self.handle_auth_submit())
                        elif event.key == pygame.K_BACKSPACE:
                            if self.active_field == "username":
                                self.username = self.username[:-1]
                            elif self.active_field == "password":
                                self.password = self.password[:-1]
                            elif self.active_field == "confirm":
                                self.confirm_password = self.confirm_password[:-1]
                        elif event.unicode and event.unicode.isprintable():
                            if self.active_field == "username" and len(self.username) < 20:
                                self.username += event.unicode
                            elif self.active_field == "password" and len(self.password) < 20:
                                self.password += event.unicode
                            elif self.active_field == "confirm" and len(self.confirm_password) < 20:
                                self.confirm_password += event.unicode

            if self.state == "AUTH":
                self.draw_auth()
            elif self.state == "ADMIN":
                self.draw_admin_view()
            else:
                self.draw_map_view()
                if self.state == "ACHIEVEMENTS":
                    self.draw_achievements_modal()
                elif self.state == "STORY_MODAL":
                    self.draw_story_modal()
                elif self.state == "QUIZ":
                    self.draw_quiz_overlay()
                elif self.state == "RESULT_MODAL":
                    self.draw_result_modal()
                elif self.state == "GAMEOVER":
                    self.draw_gameover_modal()

            for p in self.particles:
                p.draw(self.screen)

            self.draw_toast()
            pygame.display.flip()
            await asyncio.sleep(0)

        pygame.quit()


async def main():
    game = VietnamHistoryGame()
    await game.run()


asyncio.run(main())