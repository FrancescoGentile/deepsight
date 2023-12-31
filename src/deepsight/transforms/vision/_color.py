##
##
##

import math
import random
from typing import overload

from deepsight.structures.vision import BoundingBoxes, Image
from deepsight.typing import Configs

from ._base import Transform


class ColorJitter(Transform):
    """Randomly change the brightness, contrast, saturation and hue of an image."""

    def __init__(
        self,
        brightness: float | tuple[float, float] | None = None,
        contrast: float | tuple[float, float] | None = None,
        saturation: float | tuple[float, float] | None = None,
        hue: float | tuple[float, float] | None = None,
    ) -> None:
        """Initialize a color jitter transform.

        Args:
            brightness: The brightness factor. If `brightness` is a `float`, then the
                brightness of the image is changed by a factor drawn randomly from the
                range `[max(0, 1 - brightness), 1 + brightness]`. If `brightness` is a
                tuple `(min_factor, max_factor)`, then the brightness of the image is
                changed by a factor drawn randomly from the range `[min_factor,
                max_factor]`. Should be non negative numbers. If `brightness` is `None`,
                then the brightness is not changed.
            contrast: The contrast factor. If `contrast` is a `float`, then the contrast
                of the image is changed by a factor drawn randomly from the range
                `[max(0, 1 - contrast), 1 + contrast]`. If `contrast` is a tuple
                `(min_factor, max_factor)`, then the contrast of the image is changed by
                a factor drawn randomly from the range `[min_factor, max_factor]`.
                Should be non negative numbers. If `contrast` is `None`, then the
                contrast is not changed.
            saturation: The saturation factor. If `saturation` is a `float`, then the
                saturation of the image is changed by a factor drawn randomly from the
                range `[max(0, 1 - saturation), 1 + saturation]`. If `saturation` is a
                tuple `(min_factor, max_factor)`, then the saturation of the image is
                changed by a factor drawn randomly from the range `[min_factor,
                max_factor]`. Should be non negative numbers. If `saturation` is `None`,
                then the saturation is not changed.
            hue: The hue factor. If `hue` is a `float`, then the hue of the image is
                changed by a factor drawn randomly from the range `[-hue, hue]`. If
                `hue` is a tuple `(min_factor, max_factor)`, then the hue of the image
                is changed by a factor drawn randomly from the range `[min_factor,
                max_factor]`. Should be numbers between `-0.5` and `0.5`. If `hue` is
                `None`, then the hue is not changed.
        """
        super().__init__()

        self._brightness = _check_jitter_properties("brightness", brightness)
        self._contrast = _check_jitter_properties("contrast", contrast)
        self._saturation = _check_jitter_properties("saturation", saturation)
        self._hue = _check_jitter_properties(
            "hue", hue, center=0.0, bounds=(-0.5, 0.5), clip_first_on_zero=False
        )

    # ----------------------------------------------------------------------- #
    # Public Methods
    # ----------------------------------------------------------------------- #

    def get_configs(self, recursive: bool) -> Configs:
        return {
            "brightness": self._brightness,
            "contrast": self._contrast,
            "saturation": self._saturation,
            "hue": self._hue,
        }

    # ----------------------------------------------------------------------- #
    # Magic Methods
    # ----------------------------------------------------------------------- #

    @overload
    def __call__(self, image: Image) -> Image: ...

    @overload
    def __call__(
        self,
        image: Image,
        boxes: BoundingBoxes,
    ) -> tuple[Image, BoundingBoxes]: ...

    def __call__(
        self,
        image: Image,
        boxes: BoundingBoxes | None = None,
    ) -> Image | tuple[Image, BoundingBoxes]:
        perm = random.sample(range(4), 4)

        for idx in perm:
            match idx:
                case 0:
                    if self._brightness is not None:
                        brightness_factor = random.uniform(*self._brightness)
                        image = image.adjust_brightness(brightness_factor)
                case 1:
                    if self._contrast is not None:
                        contrast_factor = random.uniform(*self._contrast)
                        image = image.adjust_contrast(contrast_factor)
                case 2:
                    if self._saturation is not None:
                        saturation_factor = random.uniform(*self._saturation)
                        image = image.adjust_saturation(saturation_factor)
                case 3:
                    if self._hue is not None:
                        hue_factor = random.uniform(*self._hue)
                        image = image.adjust_hue(hue_factor)
                case _:
                    raise RuntimeError("This should never happen.")

        match boxes:
            case None:
                return image
            case BoundingBoxes():
                return image, boxes


# --------------------------------------------------------------------------- #
# Private Functions
# --------------------------------------------------------------------------- #


def _check_jitter_properties(
    property_name: str,
    value: float | tuple[float, float] | None,
    center: float = 1.0,
    bounds: tuple[float, float] = (0.0, math.inf),
    clip_first_on_zero: bool = True,
) -> tuple[float, float] | None:
    match value:
        case None:
            return None
        case float() | int():
            if value < 0:
                raise ValueError(
                    f"If {property_name} is a single number, it must be non negative."
                )
            value = float(value)
            value = (center - value, center + value)
            if clip_first_on_zero:
                value = (max(0, value[0]), value[1])
        case tuple():
            pass

    if not bounds[0] <= value[0] <= value[1] <= bounds[1]:
        raise ValueError(
            f"{property_name} values should be between {bounds[0]} and {bounds[1]}, "
            f"but got {value}."
        )

    return value
