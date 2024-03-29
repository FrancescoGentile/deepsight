# Copyright 2024 The DeepSight Team.
# SPDX-License-Identifier: Apache-2.0

import enum
from typing import Any, Literal, Self

import torch

from deepsight.typing import Detachable, Moveable, Tensor


class BoundingBoxFormat(enum.Enum):
    """The format of the bounding box coordinates."""

    XYXY = "xyxy"
    """Format where bounding box coordinates are represented as (x1, y1, x2, y2),
    where (x1, y1) is the top-left corner and (x2, y2) is the bottom-right
    corner.
    """

    XYWH = "xywh"
    """Format where bounding box coordinates are represented as (x1, y1, w, h),
    where (x1, y1) is the top-left corner and (w, h) are the width and height.
    """

    CXCYWH = "cxcywh"
    """Format where bounding box coordinates are represented as (cx, cy, w, h),
    where (cx, cy) is the center of the bounding box and (w, h) are the width
    and height.
    """

    def __str__(self) -> str:
        """Get the string representation of the bounding box format."""
        return self.value

    def __repr__(self) -> str:
        """Get the string representation of the bounding box format."""
        return f"BoundingBoxFormat.{self.value.upper()}"


class BoundingBoxes(Detachable, Moveable):
    """Structure to handle bounding boxes."""

    # -----------------------------------------------------------------------  #
    # Constructor and Factory Methods
    # -----------------------------------------------------------------------  #

    def __init__(
        self,
        coordinates: Any,
        format: BoundingBoxFormat | str,  # noqa: A002
        normalized: bool,
        image_size: tuple[int, int],
    ) -> None:
        """Create a new bounding box object.

        Args:
            coordinates: The bounding box coordinates. Any object that can
                be converted to a tensor can be provided. Once converted, the
                tensor must have a shape of `(N, 4)`.
            format: The format of the bounding box coordinates.
            normalized: Whether the bounding box coordinates are normalized or
                not.
            image_size: The size of the image that the bounding boxes are
                relative to.
        """
        super().__init__()

        coords = torch.as_tensor(coordinates).float()
        _check_coordinates(coords)

        self._coordinates = coords
        self._format = BoundingBoxFormat(format)
        self._normalized = normalized
        self._image_size = image_size

    # -----------------------------------------------------------------------  #
    # Properties
    # -----------------------------------------------------------------------  #

    @property
    def coordinates(self) -> Tensor[Literal["N 4"], float]:
        """The bounding box coordinates."""
        return self._coordinates

    @property
    def format(self) -> BoundingBoxFormat:
        """The format of the bounding box coordinates."""
        return self._format

    @property
    def normalized(self) -> bool:
        """Whether the bounding box coordinates are normalized or not."""
        return self._normalized

    @property
    def image_size(self) -> tuple[int, int]:
        """The size of the image that the bounding boxes are relative to."""
        return self._image_size

    @property
    def device(self) -> torch.device:
        """The device of the bounding box coordinates."""
        return self._coordinates.device

    # -----------------------------------------------------------------------  #
    # Conversion Methods
    # -----------------------------------------------------------------------  #

    def to_xyxy(self) -> Self:
        """Convert the bounding box coordinates to the XYXY format.

        !!! note

            If the bounding box coordinates are already in the XYXY format,
            then `self` is returned. Otherwise, a new bounding box object is
            created.
        """
        match self.format:
            case BoundingBoxFormat.XYXY:
                return self
            case BoundingBoxFormat.XYWH:
                x1y1 = self.coordinates[..., :2]
                x2y2 = x1y1 + self.coordinates[..., 2:]
                coordinates = torch.cat([x1y1, x2y2], dim=-1)
            case BoundingBoxFormat.CXCYWH:
                x1y1 = self.coordinates[..., :2] - self.coordinates[..., 2:] / 2
                x2y2 = x1y1 + self.coordinates[..., 2:]
                coordinates = torch.cat([x1y1, x2y2], dim=-1)

        return self.__class__(
            coordinates, BoundingBoxFormat.XYXY, self.normalized, self.image_size
        )

    def to_xywh(self) -> Self:
        """Convert the bounding box coordinates to the XYWH format.

        !!! note

            If the bounding box coordinates are already in the XYWH format,
            then `self` is returned. Otherwise, a new bounding box object is
            created.
        """
        match self.format:
            case BoundingBoxFormat.XYXY:
                xy = self.coordinates[..., :2]
                wh = self.coordinates[..., 2:] - xy
                coordinates = torch.cat([xy, wh], dim=-1)
            case BoundingBoxFormat.XYWH:
                return self
            case BoundingBoxFormat.CXCYWH:
                xy = self.coordinates[..., :2] - self.coordinates[..., 2:] / 2
                wh = self.coordinates[..., 2:]
                coordinates = torch.cat([xy, wh], dim=-1)

        return self.__class__(
            coordinates, BoundingBoxFormat.XYWH, self.normalized, self.image_size
        )

    def to_cxcywh(self) -> Self:
        """Convert the bounding box coordinates to the CXCYWH format.

        !!! note

            If the bounding box coordinates are already in the CXCYWH format,
            then `self` is returned. Otherwise, a new bounding box object is
            created.
        """
        match self.format:
            case BoundingBoxFormat.XYXY:
                xy = self.coordinates[..., :2]
                wh = self.coordinates[..., 2:] - xy
                coordinates = torch.cat([xy + wh / 2, wh], dim=-1)
            case BoundingBoxFormat.XYWH:
                xy = self.coordinates[..., :2]
                wh = self.coordinates[..., 2:]
                coordinates = torch.cat([xy + wh / 2, wh], dim=-1)
            case BoundingBoxFormat.CXCYWH:
                return self

        return self.__class__(
            coordinates, BoundingBoxFormat.CXCYWH, self.normalized, self.image_size
        )

    def normalize(self) -> Self:
        """Normalize the bounding box coordinates to the [0, 1] range.

        !!! note

            If the bounding box coordinates are already normalized,
            then `self` is returned. Otherwise, a new bounding box object is
            created.
        """
        if self.normalized:
            return self

        H, W = self.image_size  # noqa
        norm_factor = torch.tensor([W, H, W, H], device=self.device)
        coordinates = self.coordinates / norm_factor

        return self.__class__(coordinates, self.format, True, self.image_size)

    def denormalize(self) -> Self:
        """Denormalize the bounding box coordinates to the corresponding image range.

        !!! note

            If the bounding box coordinates are already denormalized,
            then `self` is returned. Otherwise, a new bounding box object is
            created.
        """
        if not self.normalized:
            return self

        H, W = self.image_size  # noqa
        norm_factor = torch.tensor([W, H, W, H], device=self.device)
        coordinates = self.coordinates * norm_factor

        return self.__class__(coordinates, self.format, False, self.image_size)

    def convert(
        self,
        format: BoundingBoxFormat | None = None,  # noqa: A002
        normalized: bool | None = None,
    ) -> Self:
        """Convert the bounding box coordinates to the given format and normalization."""  # noqa
        boxes = self
        match format:
            case BoundingBoxFormat.XYXY:
                boxes = self.to_xyxy()
            case BoundingBoxFormat.XYWH:
                boxes = self.to_xywh()
            case BoundingBoxFormat.CXCYWH:
                boxes = self.to_cxcywh()
            case None:
                pass

        match normalized:
            case True:
                boxes = boxes.normalize()
            case False:
                boxes = boxes.denormalize()
            case None:
                pass

        return boxes

    def convert_like(self, other: Self) -> Self:
        """Convert the bounding box coordinates to the same format and normalization as
        the given bounding box object."""  # noqa
        return self.convert(other.format, other.normalized)

    # -----------------------------------------------------------------------  #
    # Transform Methods
    # -----------------------------------------------------------------------  #

    def resize(self, image_size: tuple[int, int]) -> Self:
        """Resize the bounding box coordinates to the corresponding image size.

        This method is useful to adjust the bounding box coordinates when the
        image is resized to a different size.

        !!! note

            If the image size is the same as the bounding box image size,
            then `self` is returned. Otherwise, a new bounding box object is
            created.

        Args:
            image_size: The new image size (height, width).

        Returns:
            A new bounding box object with the rescaled coordinates.
        """
        if self.image_size == image_size:
            return self

        if self.normalized:
            coordinates = self.coordinates
        else:
            height_ratio = image_size[0] / self.image_size[0]
            width_ratio = image_size[1] / self.image_size[1]
            scale_factor = torch.tensor(
                [width_ratio, height_ratio, width_ratio, height_ratio],
                device=self.device,
            )
            coordinates = self.coordinates * scale_factor

        return self.__class__(coordinates, self.format, self.normalized, image_size)

    def horizontal_flip(self) -> Self:
        """Flip the bounding box coordinates horizontally."""
        W = 1 if self.normalized else self.image_size[1]  # noqa: N806

        coords = self.coordinates.clone()
        match self.format:
            case BoundingBoxFormat.XYXY:
                coords[:, [2, 0]] = coords[:, [0, 2]].sub_(W).neg_()
            case BoundingBoxFormat.XYWH:
                coords[:, 0].add_(coords[:, 2]).sub_(W).neg_()
            case BoundingBoxFormat.CXCYWH:
                coords[:, 0].sub_(W).neg_()

        return self.__class__(
            coords,
            format=self.format,
            normalized=self.normalized,
            image_size=self.image_size,
        )

    def crop(self, top: int, left: int, bottom: int, right: int) -> Self:
        """Crop the bounding box coordinates to the given region.

        Args:
            top: The top coordinate of the crop region.
            left: The left coordinate of the crop region.
            bottom: The bottom coordinate of the crop region.
            right: The right coordinate of the crop region.

        Returns:
            A new bounding box object with the cropped coordinates.
        """
        boxes = self.denormalize()
        match boxes.format:
            case BoundingBoxFormat.XYXY:
                sub = torch.tensor([left, top, left, top], device=self.device)
            case BoundingBoxFormat.XYWH:
                sub = torch.tensor([left, top, 0, 0], device=self.device)
            case BoundingBoxFormat.CXCYWH:
                sub = torch.tensor([left, top, 0, 0], device=self.device)

        coords = boxes.coordinates - sub
        boxes = self.__class__(
            coords,
            format=boxes.format,
            normalized=False,
            image_size=(bottom - top, right - left),
        )
        boxes = boxes.clamp_to_image()

        return boxes.convert_like(self)

    # -----------------------------------------------------------------------  #
    # Operations
    # -----------------------------------------------------------------------  #

    def area(self) -> Tensor[Literal["N"], float]:
        """Compute the area of the bounding boxes.

        !!! note

            If the bounding box coordinates are normalized with respect to the
            image size, then the area is also normalized. Otherwise, the area
            is in pixels.
        """
        match self.format:
            case BoundingBoxFormat.XYXY:
                wh = self.coordinates[..., 2:] - self.coordinates[..., :2]
                area = wh[..., 0] * wh[..., 1]
            case BoundingBoxFormat.XYWH:
                area = self.coordinates[..., 2] * self.coordinates[..., 3]
            case BoundingBoxFormat.CXCYWH:
                area = self.coordinates[..., 2] * self.coordinates[..., 3]

        return area

    def aspect_ratio(self) -> Tensor[Literal["N"], float]:
        """Compute the aspect ratio of the bounding boxes.

        The aspect ratio is computed as the width divided by the height.

        !!! note

            To avoid division by zero, a small epsilon is added to the height
            before computing the aspect ratio.
        """
        match self.format:
            case BoundingBoxFormat.XYXY:
                wh = self.coordinates[..., 2:] - self.coordinates[..., :2]
                w, h = wh[..., 0], wh[..., 1]
            case BoundingBoxFormat.XYWH:
                w, h = self.coordinates[..., 2], self.coordinates[..., 3]
            case BoundingBoxFormat.CXCYWH:
                w, h = self.coordinates[..., 2], self.coordinates[..., 3]

        eps = torch.finfo(w.dtype).eps
        return w / (h + eps)

    def union(self, other: Self) -> Self:
        """Compute the union of the bounding boxes."""
        boxes1 = self.to_xyxy()
        boxes2 = other.convert_like(boxes1)
        boxes1._check_compatibility(boxes2)

        x1y1 = torch.min(boxes1.coordinates[..., :2], boxes2.coordinates[..., :2])
        x2y2 = torch.max(boxes1.coordinates[..., 2:], boxes2.coordinates[..., 2:])

        return self.__class__(
            torch.cat([x1y1, x2y2], dim=-1),
            BoundingBoxFormat.XYXY,
            boxes1.normalized,
            boxes1.image_size,
        )

    def intersection(self, other: Self) -> Self:
        """Compute the intersection of the bounding boxes."""
        boxes1 = self.to_xyxy()
        boxes2 = other.convert_like(boxes1)
        boxes1._check_compatibility(boxes2)

        x1y1 = torch.max(boxes1.coordinates[..., :2], boxes2.coordinates[..., :2])
        x2y2 = torch.min(boxes1.coordinates[..., 2:], boxes2.coordinates[..., 2:])
        wh = torch.clamp(x2y2 - x1y1, min=0)

        return self.__class__(
            torch.cat([x1y1, wh], dim=-1),
            BoundingBoxFormat.XYWH,
            boxes1.normalized,
            boxes1.image_size,
        )

    def union_area(self, other: Self) -> Tensor[Literal["N"], float]:
        """Compute the union area of the bounding boxes.

        !!! note

            This is not the same as the area of the union of the bounding boxes.
            The union area is the sum of the areas of the bounding boxes minus
            the intersection area. To compute the area of the union of the
            bounding boxes, use `self.union(other).area()` instead.

        Args:
            other: The other bounding box object.

        Returns:
            The union area of the bounding boxes.

        Raises:
            ValueError: If the bounding boxes do not have the same normalization.
        """
        if self.normalized != other.normalized:
            raise ValueError("The bounding boxes must have the same normalization.")

        area1 = self.area()
        area2 = other.area()
        intersection_area = self.intersection_area(other)

        return area1 + area2 - intersection_area

    def intersection_area(self, other: Self) -> Tensor[Literal["N"], float]:
        """Compute the intersection area of the bounding boxes.

        This is equivalent to `self.intersection(other).area()`.

        Args:
            other: The other bounding box object.

        Returns:
            The intersection area of the bounding boxes.

        Raises:
            ValueError: If the bounding boxes do not have the same normalization.
        """
        if self.normalized != other.normalized:
            raise ValueError("The bounding boxes must have the same normalization.")

        return self.intersection(other).area()

    def iou(self, other: Self) -> Tensor[Literal["N"], float]:
        """Compute the intersection over union (IoU) of the bounding boxes."""
        boxes1 = self.normalize()
        boxes2 = other.normalize()

        intersection_area = boxes1.intersection_area(boxes2)
        union_area = boxes1.union_area(boxes2)

        eps = torch.finfo(intersection_area.dtype).eps
        return intersection_area / (union_area + eps)

    # -----------------------------------------------------------------------  #
    # Validation Methods
    # -----------------------------------------------------------------------  #

    def clamp_to_image(self) -> Self:
        """Clamp the bounding box coordinates to the image size.

        If the bounding boxes are normalized, then the coordinates are clipped
        to the [0, 1] range. Otherwise, the coordinates are clipped to the
        image size.

        Returns:
            A new bounding box object with the clipped coordinates.
        """
        boxes = self.to_xyxy()
        H, W = (1, 1) if boxes.normalized else boxes.image_size  # noqa: N806
        coords = boxes.coordinates.clone()
        coords[..., 0].clamp_(min=0, max=W)
        coords[..., 1].clamp_(min=0, max=H)
        coords[..., 2].clamp_(min=0, max=W)
        coords[..., 3].clamp_(min=0, max=H)

        boxes = self.__class__(coords, boxes.format, boxes.normalized, boxes.image_size)
        return boxes.convert_like(self)

    def is_valid(
        self,
        min_width: float = 1,
        min_height: float = 1,
    ) -> Tensor[Literal["N"], bool]:
        """Check if the bounding boxes are valid.

        The bounding boxes are valid if they are inside the image and have a
        width and height greater than the given minimum values.

        Args:
            min_width: The minimum width of the bounding boxes. If the bounding
                boxes are normalized, also the minimum width will be normalized
                (you do not need to normalize it yourself).
            min_height: The minimum height of the bounding boxes. If the bounding
                boxes are normalized, also the minimum height will be normalized
                (you do not need to normalize it yourself).

        Returns:
            A boolean mask indicating which bounding boxes are valid.
        """
        boxes = self.to_xyxy()
        H, W = (1, 1) if boxes.normalized else boxes.image_size  # noqa: N806
        if boxes.normalized:
            min_width = min_width / self.image_size[1]
            min_height = min_height / self.image_size[0]

        x1, y1, x2, y2 = boxes.coordinates.unbind(dim=-1)

        valid = (boxes.coordinates >= 0).all(dim=-1)
        valid &= (x1 <= W) & (y1 <= H) & (x2 <= W) & (y2 <= H)
        valid &= ((x2 - x1) >= min_width) & ((y2 - y1) >= min_height)

        return valid

    # -----------------------------------------------------------------------  #
    # Other Methods
    # -----------------------------------------------------------------------  #

    def to(self, device: torch.device | str, *, non_blocking: bool = False) -> Self:
        if self.device == torch.device(device):
            return self

        return self.__class__(
            self.coordinates.to(device, non_blocking=non_blocking),
            self.format,
            self.normalized,
            self.image_size,
        )

    def detach(self) -> Self:
        return self.__class__(
            self.coordinates.detach(),
            self.format,
            self.normalized,
            self.image_size,
        )

    # -----------------------------------------------------------------------  #
    # Magic methods
    # -----------------------------------------------------------------------  #

    def __or__(self, other: Self) -> Self:
        """Compute the union of the bounding boxes."""
        return self.union(other)

    def __and__(self, other: Self) -> Self:
        """Compute the intersection of the bounding boxes."""
        return self.intersection(other)

    def __getitem__(self, indexes: slice | Tensor[Literal["N"], bool | int]) -> Self:
        """Get the bounding box at the given index."""
        return self.__class__(
            self.coordinates[indexes], self.format, self.normalized, self.image_size
        )

    def __len__(self) -> int:
        """Get the number of bounding boxes."""
        return self.coordinates.shape[0]

    def __str__(self) -> str:
        return (
            f"{self.__class__.__name__}(num_boxes={len(self)}, "
            f"format={self.format}, normalized={self.normalized}, "
            f"image_size={self.image_size})"
        )

    def __repr__(self) -> str:
        return str(self)

    # -----------------------------------------------------------------------  #
    # Private Methods
    # -----------------------------------------------------------------------  #

    def _check_compatibility(self, other: Self) -> None:
        """Check that the bounding boxes are compatible.

        The bounding boxes must have the same number of boxes and the same
        image size.

        Args:
            other: The other bounding box object.

        Raises:
            ValueError: If the bounding boxes are not compatible.
        """
        if len(self) != len(other):
            raise ValueError(
                f"The number of bounding boxes must be the same, got {len(self)} "
                f"and {len(other)}."
            )

        if self.image_size != other.image_size:
            raise ValueError(
                f"The bounding box image size must be the same, got {self.image_size} "
                f"and {other.image_size}."
            )

    # -----------------------------------------------------------------------  #
    # Private fields
    # -----------------------------------------------------------------------  #

    __slots__ = ("_coordinates", "_format", "_normalized", "_image_size")


# ---------------------------------------------------------------------------  #
# Private helper functions
# ---------------------------------------------------------------------------  #


def _check_coordinates(coords: torch.Tensor) -> None:
    """Check that the coordinates are valid.

    The coordinates must be a 2-dimensional float tensor with a shape of
    `(N, 4)`.

    Args:
        coords: The coordinates to check.

    Raises:
        ValueError: If the coordinates are not valid.
    """
    if coords.ndim != 2:
        raise ValueError(f"The coordinates must be 2-dimensional, got {coords.ndim}.")

    if coords.shape[-1] != 4:
        raise ValueError(
            f"The last dimension of coordinates must be 4, got {coords.shape[-1]}."
        )
