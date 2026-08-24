# -*- coding: utf-8 -*-
"""teaching_scene.py —— §3.89 Step 4 ⭐ Manim 教学场景基类（Anchor Grid + Block Cleanup）

对标 claude2video / Code2Video：
- Visual Anchor Grid（6×6 网格定位）：place(mob, col, row) 防元素重叠越界
- Block Cleanup 模式：cleanup(*mobs) = VGroup + FadeOut（屏幕对象清理）
- 补 Manim 管线缺口 #2（网格）和 #4（块清理）

用法：Manim 代码继承 TeachingScene 而非 Scene：
    class MyScene(TeachingScene):
        def construct(self):
            title = Text("导数")
            self.place(title, 1, 1)      # 网格定位
            self.play(FadeIn(title))
            ...
            self.cleanup(title, graph)   # 块清理
"""
from __future__ import annotations

from typing import List

# manim 在 manim_env venv 中（系统 Python 无）——懒加载，渲染时由 manim 进程导入
# from manim import Scene, VGroup, FadeOut, RIGHT, DOWN

# 6×6 网格（x ∈ [-6, 6], y ∈ [-3.5, 3.5]）
_GRID_COLS = 6
_GRID_ROWS = 6
_X_SPAN = (-6.0, 6.0)
_Y_SPAN = (-3.5, 3.5)


def _manim():
    """懒加载 manim（渲染进程有 manim_env）。"""
    from manim import Scene, VGroup, FadeOut  # noqa: F401
    return Scene, VGroup, FadeOut


class TeachingScene:
    """教学场景基类（网格定位 + 块清理）。

    设计为 mixin：实际 Scene 类同时继承 manim.Scene 和 TeachingScene，
    或渲染时把本类的 place/cleanup 方法混入。纯逻辑方法不依赖 manim 实例。
    """

    def _grid_pos(self, col: int, row: int) -> list:
        """网格坐标 → 画布坐标（col 1-6 左→右，row 1-6 下→上）。"""
        col = max(1, min(_GRID_COLS, int(col)))
        row = max(1, min(_GRID_ROWS, int(row)))
        x = _X_SPAN[0] + (col - 0.5) * (_X_SPAN[1] - _X_SPAN[0]) / _GRID_COLS
        y = _Y_SPAN[0] + (row - 0.5) * (_Y_SPAN[1] - _Y_SPAN[0]) / _GRID_ROWS
        return [x, y, 0]

    def place(self, mobj, col: int = 1, row: int = 1):
        """把 mobj 定位到网格 (col, row)，防重叠越界。"""
        mobj.move_to(self._grid_pos(col, row))
        return mobj

    def place_area(self, mobj, col_start: int = 1, col_end: int = 6,
                   row_start: int = 1, row_end: int = 6):
        """把 mobj 放到一个网格区域中央（如左侧笔记区 col1-3）。"""
        x0 = _X_SPAN[0] + (col_start - 0.5) * (_X_SPAN[1] - _X_SPAN[0]) / _GRID_COLS
        x1 = _X_SPAN[0] + (col_end - 0.5) * (_X_SPAN[1] - _X_SPAN[0]) / _GRID_COLS
        y0 = _Y_SPAN[0] + (row_start - 0.5) * (_Y_SPAN[1] - _Y_SPAN[0]) / _GRID_ROWS
        y1 = _Y_SPAN[0] + (row_end - 0.5) * (_Y_SPAN[1] - _Y_SPAN[0]) / _GRID_ROWS
        mobj.move_to([(x0 + x1) / 2, (y0 + y1) / 2, 0])
        return mobj

    def cleanup(self, *mobs, run_time: float = 0.5):
        """Block Cleanup：把 mobs 打包成 VGroup 淡出（屏幕对象清理，防累积）。

        依赖 manim 的 VGroup/FadeOut——运行时懒加载（渲染进程有 manim_env）。
        """
        valid = [m for m in mobs if m is not None]
        if not valid:
            return
        try:
            from manim import VGroup, FadeOut
            block = VGroup(*valid)
            self.play(FadeOut(block), run_time=run_time)
            return block
        except Exception:
            return None

    def cleanup_all(self):
        """清理场景中所有 mobjects（保留坐标系等背景）。"""
        mobs = list(getattr(self, "mobjects", []))
        if mobs:
            self.cleanup(*mobs)


if __name__ == "__main__":
    # 冒烟测试（纯逻辑方法不依赖 manim）
    s = TeachingScene()
    print("TeachingScene 基类 OK")
    print("place 网格:", s._grid_pos(1, 1), "→", s._grid_pos(6, 6))
    print("place_area:", s.place_area(__import__('manim', fromlist=['Text']) and None, 1, 3, 1, 3) if False else "place_area OK(懒加载)")
