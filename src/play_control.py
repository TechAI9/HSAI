"""Play-button control with optional传说段位 OCR 检查.

在点击“开始/匹配”按钮前，使用 OCR 判断屏幕右上角的段位数值是否超过阈值，
若超过则不进行下一把点击。截图 ROI 由调用方传入（参数 roi_bbox），
位置/大小留给用户在运行时配置。

用法示例：
    from src.play_control import start_next_match_with_legend_check

    # roi_bbox = (left, top, right, bottom) 由你补充/校准
    started = start_next_match_with_legend_check(
        play_x=1200, play_y=700, roi_bbox=(1700, 10, 1910, 110), threshold=10)
    if started:
        print("已点击开始")
    else:
        print("检测到传说，未开始下一把")
"""

from types import SimpleNamespace
import hashlib
import uuid
import time
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import ImageGrab

from src.recommendation_config import RecommendationConfig
from src.ocr.paddle_adapter import PaddleOcrAdapter
from src.ocr.stable_reader import StableRecommendationReader

import click as click_module  # repo's click.py


def _capture_bbox_to_bgr(bbox: Tuple[int, int, int, int]) -> np.ndarray:
    rgb = np.asarray(ImageGrab.grab(bbox=bbox, all_screens=False))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def start_next_match_with_legend_check(
    play_x: int,
    play_y: int,
    roi_bbox: Optional[Tuple[int, int, int, int]] = None,
    threshold: int = 10,
    retry_interval_seconds: Optional[float] = None,
) -> bool:
    """在点击开始按钮前进行 OCR 传说检查。

    参数:
      play_x, play_y: 要点击的开始/匹配按钮屏幕坐标（像素）
      roi_bbox: 要 OCR 的区域 (left, top, right, bottom)。如果为 None 则
        跳过 OCR 检查直接点击。
      threshold: 数字阈值，大于该值视为传说（默认 10）。因为未上传说，都是 0~9 的数字，Todo：这里有bug：隐藏分很高的选手，上传说后，可能排名10以内，下个版本修改成基于上传说后的像素点颜色，黄色背景来判断，效率更高。
      retry_interval_seconds: 覆盖 config.retry_interval_seconds（可选）。

    返回 True 表示已点击开始；False 表示因传说判定或出错没有点击。
    """
    # 如果调用方没有传 roi_bbox，则直接点击
    if roi_bbox is None:
        click_module.left_click(play_x, play_y)
        return True

    config = RecommendationConfig()
    if retry_interval_seconds is not None:
        # 临时覆盖重试间隔
        config.retry_interval_seconds = retry_interval_seconds

    # OCR 后端与 reader（惰性加载 Paddle OCR）
    backend = PaddleOcrAdapter()
    reader = StableRecommendationReader(config, backend)

    def frame_supplier():
        img = _capture_bbox_to_bgr(roi_bbox)
        # 构造一个轻量 frame stub，供 reader 使用
        h = hashlib.sha256(img.tobytes()).hexdigest()
        frame = SimpleNamespace()
        frame.frame_id = f"frame-{uuid.uuid4()}"
        frame.exact_hash = h
        frame.pixels = img
        return frame

    def roi_supplier(frame):
        # 我们已经只截取了 roi_bbox 区域，因此直接返回 frame.pixels
        return frame.pixels

    try:
        legend = reader.is_legend_state(frame_supplier, roi_supplier, threshold)
    except Exception:
        # OCR 失败时为安全起见不开始下一把
        return False

    if legend:
        return False

    # 非传说状态，点击开始
    click_module.left_click(play_x, play_y)
    # 给点时间让界面切换
    time.sleep(0.5)
    return True
