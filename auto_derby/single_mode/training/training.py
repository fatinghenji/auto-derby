# -*- coding=UTF-8 -*-
# pyright: strict
from __future__ import annotations

import logging
import os
from typing import Tuple

import cast_unknown as cast
import cv2
import numpy as np
from auto_derby import imagetools
from PIL.Image import Image
from PIL.Image import fromarray as image_from_array

from ... import mathtools, ocr, template, templates
from ..context import Context
from .globals import g
from .partner import Partner
from . import training_score

_LOGGER = logging.getLogger(__name__)


def _gradient(colors: Tuple[Tuple[Tuple[int, int, int], int], ...]) -> np.ndarray:
    ret = np.linspace((0, 0, 0), colors[0][0], colors[0][1])
    for index, i in enumerate(colors[1:], 1):
        color, stop = i
        prev_color, prev_stop = colors[index - 1]
        g = np.linspace(prev_color, color, stop - prev_stop + 1)
        ret = np.concatenate((ret, g[1:]))
    return ret


def _ocr_training_effect(img: Image) -> int:
    cv_img = imagetools.cv_image(imagetools.resize(img, height=32))
    sharpened_img = cv2.filter2D(
        cv_img,
        8,
        np.array(
            (
                (0, -1, 0),
                (-1, 5, -1),
                (0, -1, 0),
            )
        ),
    )
    sharpened_img = imagetools.mix(sharpened_img, cv_img, 0.5)

    white_outline_img = imagetools.constant_color_key(
        sharpened_img,
        (255, 255, 255),
        (234, 245, 240),
    )
    white_outline_img = cv2.dilate(
        white_outline_img,
        cv2.getStructuringElement(
            cv2.MORPH_DILATE,
            (2, 2),
        ),
    )

    bg_mask_img = imagetools.bg_mask_by_outline(white_outline_img)

    masked_img = cv2.copyTo(cv_img, 255 - bg_mask_img)

    brown_outline_img = imagetools.constant_color_key(
        masked_img,
        (29, 62, 194),
        (24, 113, 218),
        (30, 109, 216),
        (69, 104, 197),
        (119, 139, 224),
        (103, 147, 223),
    )

    bg_mask_img = imagetools.bg_mask_by_outline(brown_outline_img)
    masked_img = cv2.copyTo(masked_img, 255 - bg_mask_img)

    fill_gradient = _gradient(
        (
            ((140, 236, 255), 0),
            ((140, 236, 255), round(cv_img.shape[0] * 0.25)),
            ((114, 229, 255), round(cv_img.shape[0] * 0.35)),
            ((113, 198, 255), round(cv_img.shape[0] * 0.55)),
            ((95, 179, 255), round(cv_img.shape[0] * 0.63)),
            ((74, 157, 255), round(cv_img.shape[0] * 0.70)),
            ((74, 117, 255), round(cv_img.shape[0] * 0.83)),
            ((74, 117, 255), cv_img.shape[0]),
        )
    ).astype(np.uint8)
    fill_img = np.repeat(np.expand_dims(fill_gradient, 1), cv_img.shape[1], axis=1)
    assert fill_img.shape == cv_img.shape

    text_img = imagetools.color_key(masked_img, fill_img)
    imagetools.fill_area(text_img, (0,), size_lt=8)

    text_img_extra = imagetools.constant_color_key(
        masked_img, (175, 214, 255), threshold=0.95
    )
    text_img = np.array(np.maximum(text_img, text_img_extra))
    h = cv_img.shape[0]
    imagetools.fill_area(text_img, (0,), size_lt=round(h * 0.2 ** 2))

    if os.getenv("DEBUG") == __name__:
        cv2.imshow("cv_img", cv_img)
        cv2.imshow("sharpened_img", sharpened_img)
        cv2.imshow("white_outline_img", white_outline_img)
        cv2.imshow("brown_outline_img", brown_outline_img)
        cv2.imshow("bg_mask_img", bg_mask_img)
        cv2.imshow("masked_img", masked_img)
        cv2.imshow("text_img_extra", text_img_extra)
        cv2.imshow("text_img", text_img)
        cv2.waitKey()
        cv2.destroyAllWindows()

    text = ocr.text(image_from_array(text_img))
    if not text:
        return 0
    return int(text.lstrip("+"))


def _recognize_level(rgb_color: Tuple[int, ...]) -> int:
    if imagetools.compare_color((49, 178, 22), rgb_color) > 0.9:
        return 1
    if imagetools.compare_color((46, 139, 244), rgb_color) > 0.9:
        return 2
    if imagetools.compare_color((255, 134, 0), rgb_color) > 0.9:
        return 3
    if imagetools.compare_color((244, 69, 132), rgb_color) > 0.9:
        return 4
    if imagetools.compare_color((165, 78, 255), rgb_color) > 0.9:
        return 5
    raise ValueError("_recognize_level: unknown level color: %s" % (rgb_color,))


class Training:
    TYPE_SPEED: int = 1
    TYPE_STAMINA: int = 2
    TYPE_POWER: int = 3
    TYPE_GUTS: int = 4
    TYPE_WISDOM: int = 5

    ALL_TYPES = (
        TYPE_SPEED,
        TYPE_STAMINA,
        TYPE_POWER,
        TYPE_GUTS,
        TYPE_WISDOM,
    )

    @staticmethod
    def new() -> Training:
        return g.training_class()

    def __init__(self):
        self.level = 0
        self.type = 0

        self.speed: int = 0
        self.stamina: int = 0
        self.power: int = 0
        self.guts: int = 0
        self.wisdom: int = 0
        self.skill: int = 0
        # self.friendship: int = 0
        # self.failure_rate: float = 0.0
        self.confirm_position: Tuple[int, int] = (0, 0)
        self.partners: Tuple[Partner, ...] = tuple()

    @classmethod
    def from_training_scene(cls, img: Image) -> Training:
        if g.image_path:
            image_id = imagetools.md5(
                imagetools.cv_image(img.convert("RGB")),
                save_path=g.image_path,
                save_mode="RGB",
            )
            _LOGGER.debug("from_training_scene: image=%s", image_id)
        rp = mathtools.ResizeProxy(img.width)

        self = cls.new()
        self.confirm_position = next(
            template.match(
                img,
                template.Specification(
                    templates.SINGLE_MODE_TRAINING_CONFIRM, threshold=0.8
                ),
            )
        )[1]
        radius = rp.vector(30, 540)
        for t, center in zip(
            Training.ALL_TYPES,
            (
                rp.vector2((78, 850), 540),
                rp.vector2((171, 850), 540),
                rp.vector2((268, 850), 540),
                rp.vector2((367, 850), 540),
                rp.vector2((461, 850), 540),
            ),
        ):
            if mathtools.distance(self.confirm_position, center) < radius:
                self.type = t
                break
        else:
            raise ValueError(
                "unknown type for confirm position: %s" % self.confirm_position
            )

        self.level = _recognize_level(
            tuple(cast.list_(img.getpixel(rp.vector2((10, 200), 540)), int))
        )

        t, b = 503, 532
        self.speed = _ocr_training_effect(img.crop(rp.vector4((18, t, 91, b), 466)))
        self.stamina = _ocr_training_effect(img.crop(rp.vector4((91, t, 163, b), 466)))
        self.power = _ocr_training_effect(img.crop(rp.vector4((163, t, 237, b), 466)))
        self.guts = _ocr_training_effect(img.crop(rp.vector4((237, t, 309, b), 466)))
        self.wisdom = _ocr_training_effect(img.crop(rp.vector4((309, t, 382, b), 466)))
        self.skill = _ocr_training_effect(img.crop(rp.vector4((387, t, 450, b), 466)))
        self.partners = tuple(Partner.from_training_scene(img))
        return self

    def __str__(self):

        named_data = (
            ("spd", self.speed),
            ("sta", self.stamina),
            ("pow", self.power),
            ("gut", self.guts),
            ("wis", self.wisdom),
            ("ski", self.skill),
        )
        partner_text = ",".join(
            f"{i.type_text(i.type)}@{i.level}{'!' if i.has_hint else ''}"
            for i in self.partners
        )
        return (
            "Training<"
            f"lv={self.level} "
            + " ".join(
                (
                    f"{name}={value}"
                    for name, value in sorted(
                        named_data, key=lambda x: x[1], reverse=True
                    )
                    if value
                )
            )
            + (f" ptn={partner_text}" if partner_text else "")
            + ">"
        )

    def score(self, ctx: Context) -> float:
        return training_score.compute(ctx, self)


g.training_class = Training
