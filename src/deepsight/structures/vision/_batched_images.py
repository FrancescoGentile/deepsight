##
##
##

from collections.abc import Sequence
from typing import Literal, Self

import torch

from deepsight.typing import Moveable, Number, Tensor

from ._batched_sequences import BatchedSequences


class BatchedImages(Moveable):
    """Structure to hold a batch of images as a single tensor.

    The tensor is obtained by padding the images to the largest height and
    width in the batch. Since the images are padded, a mask is also stored
    to indicate which pixels are padded and which not. The mask is True for
    padded pixels and False for valid pixels.
    """

    # ----------------------------------------------------------------------- #
    # Constructor and Factory methods
    # ----------------------------------------------------------------------- #

    def __init__(
        self,
        data: Tensor[Literal["B C H W"], Number],
        image_sizes: tuple[tuple[int, int], ...] | None = None,
        mask: Tensor[Literal["B H W"], bool] | None = None,
        *,
        check_validity: bool = True,
    ) -> None:
        """Initialize the batched images.

        !!! note

            If neither `image_sizes` nor `mask` are provided, it is assumed
            that the images are not padded (i.e., the images in the batch
            have the same height and width).

        Args:
            data: The tensor containing the batched images.
            image_sizes: The sizes of the images in the batch. If not
                provided, the sizes are computed from the mask.
            mask: The mask indicating which pixels are padded and which
                not. The mask is `True` for padded pixels and `False` for
                valid pixels. If not provided, the mask is computed from
                the image sizes.
            check_validity: Whether to check the validity of the inputs.

        Raises:
            ValueError: raised under the following conditions:
                - If `image_sizes` and `mask` are provided and are incompatible.
                - If the `data` and `mask` (thus `image_sizes`) are incompatible.
        """
        match image_sizes, mask:
            case None, None:
                image_sizes = tuple((data.shape[2], data.shape[3]) for _ in data)
                mask = torch.zeros(
                    (len(data), data.shape[2], data.shape[3]),
                    dtype=torch.bool,
                    device=data.device,
                )
                check_validity = False
            case None, _:
                image_sizes = _compute_sizes_from_mask(mask)  # type: ignore
            case _, None:
                mask = _compute_mask_from_sizes(
                    image_sizes, data.shape[2], data.shape[3], data.device
                )
            case _, _:
                if check_validity:
                    mask_image_sizes = _compute_sizes_from_mask(mask)
                    if image_sizes != mask_image_sizes:
                        raise ValueError("The image_sizes and mask are incompatible.")

        if check_validity:
            if mask.device != data.device:  # type: ignore
                raise ValueError("The data and mask must be on the same device.")
            if mask.dtype != torch.bool:  # type: ignore
                raise ValueError("The mask must be of dtype bool.")
            _check_data_mask(data, mask)  # type: ignore

        self._data = data
        self._image_sizes = image_sizes
        self._mask: Tensor = mask  # type: ignore

    @classmethod
    def batch(
        cls,
        images: Sequence[Tensor[Literal["C H W"], Number]],
        padding_value: float = 0,
    ) -> Self:
        """Batch a list of images into a single tensor.

        Args:
            images: The images to batch.
            padding_value: The value to pad the images with. Defaults to 0.

        Returns:
            The batched images.
        """
        _check_images(images)

        image_sizes = tuple((img.size(1), img.size(2)) for img in images)
        max_height = max(s[0] for s in image_sizes)
        max_width = max(s[1] for s in image_sizes)

        data = torch.full(
            (len(images), images[0].shape[0], max_height, max_width),
            padding_value,
            dtype=images[0].dtype,
            device=images[0].device,
        )

        for i, image in enumerate(images):
            data[i, :, : image.shape[1], : image.shape[2]].copy_(image)

        return cls(data, image_sizes=image_sizes, check_validity=False)

    # ----------------------------------------------------------------------- #
    # Properties
    # ----------------------------------------------------------------------- #

    @property
    def data(self) -> Tensor[Literal["B C H W"], Number]:
        """The tensor containing the batched images.

        The tensor has shape `(B, C, H, W)`, where `B` is the batch size, `C` is
        the number of channels, `H` is the maximum height of the images in the
        batch, and `W` is the maximum width of the images in the batch.
        """
        return self._data

    @property
    def image_sizes(self) -> tuple[tuple[int, int], ...]:
        """The sizes of the images in the batch before padding."""
        return self._image_sizes

    @property
    def mask(self) -> Tensor[Literal["B H W"], bool]:
        """The mask indicating which pixels are padded and which not.

        The mask is a boolean tensor of shape `(B, H, W)`, where `B` is the
        batch size, `H` is the maximum height of the images in the batch, and
        `W` is the maximum width of the images in the batch. The entries of the
        mask are `True` for padded pixels and `False` for valid pixels.
        """
        return self._mask

    @property
    def shape(self) -> torch.Size:
        """The shape of the batched images."""
        return self._data.shape

    @property
    def dtype(self) -> torch.dtype:
        """The dtype of the batched images."""
        return self._data.dtype

    @property
    def device(self) -> torch.device:
        """The device of the batched images."""
        return self._data.device

    # ----------------------------------------------------------------------- #
    # Public methods
    # ----------------------------------------------------------------------- #

    def unbatch(self) -> tuple[Tensor[Literal["C H W"], Number], ...]:
        """Unbatch the images into a list of tensors."""
        return tuple(
            self._data[i, :, :h, :w] for i, (h, w) in enumerate(self._image_sizes)
        )

    def replace(self, data: Tensor[Literal["B C H W"], Number]) -> Self:
        """Replace the data tensor.

        Raises:
            ValueError: If the shape of the new data tensor is incompatible
                with the mask.
        """
        _check_data_mask(data, self._mask)

        return self.__class__(
            data, image_sizes=self._image_sizes, mask=self._mask, check_validity=False
        )

    def to_sequences(self) -> BatchedSequences:
        """Convert the batched images to a batch of sequences."""
        data = self._data.flatten(2).permute(0, 2, 1)
        mask = self._mask.flatten(1)
        sizes = tuple(s[0] * s[1] for s in self._image_sizes)

        return BatchedSequences(data, sizes, mask, check_validity=False)

    def to(self, device: torch.device | str, *, non_blocking: bool = False) -> Self:
        if self.device == torch.device(device):
            return self

        return self.__class__(
            self._data.to(device, non_blocking=non_blocking),
            image_sizes=self._image_sizes,
            mask=self._mask.to(device, non_blocking=non_blocking),
            check_validity=False,
        )

    # ----------------------------------------------------------------------- #
    # Magic methods
    # ----------------------------------------------------------------------- #

    def __len__(self) -> int:
        """Get the number of images in the batch."""
        return self._data.shape[0]

    def __getitem__(self, index: int) -> Tensor[Literal["C H W"], Number]:
        """Get the image in the batch at the given index."""
        h, w = self._image_sizes[index]
        return self._data[index, :, :h, :w]

    def __str__(self) -> str:
        """Get the string representation of the batched images."""
        return (
            f"{self.__class__.__name__}("
            f"shape={self.shape}, dtype={self.dtype}, device={self.device})"
        )

    def __repr__(self) -> str:
        """Get the string representation of the batched images."""
        return str(self)

    # ----------------------------------------------------------------------- #
    # Private fields
    # ----------------------------------------------------------------------- #

    __slots__ = ("_data", "_image_sizes", "_mask")


# --------------------------------------------------------------------------- #
# Private helper functions
# --------------------------------------------------------------------------- #


def _compute_sizes_from_mask(
    mask: Tensor[Literal["B H W"], bool],
) -> tuple[tuple[int, int], ...]:
    """Get the sizes of the images from the mask.

    Args:
        mask: The mask indicating which pixels are padded and which not.
            The mask is `True` for padded pixels and `False` for valid pixels.

    Returns:
        The sizes of the images.
    """
    sizes: list[tuple[int, int]] = []
    for m in mask:
        # TODO: check this code
        h = m.shape[0] - m.sum(0).sum(0).item()
        w = m.shape[1] - m.sum(0).sum(0).item()

        sizes.append((h, w))  # type: ignore

    return tuple(sizes)


def _compute_mask_from_sizes(
    sizes: tuple[tuple[int, int], ...],
    max_height: int,
    max_width: int,
    device: torch.device,
) -> Tensor[Literal["B H W"], bool]:
    """Get the mask from the image sizes.

    Args:
        sizes: The sizes of the images.
        max_height: The maximum height of the images.
        max_width: The maximum width of the images.
        device: The device to put the mask on.

    Returns:
        The mask indicating which pixels are padded and which not.
        The mask is `True` for padded pixels and `False` for valid pixels.
    """
    mask = torch.ones(
        (len(sizes), max_height, max_width), dtype=torch.bool, device=device
    )

    for i, size in enumerate(sizes):
        mask[i, : size[0], : size[1]] = False

    return mask


def _check_images(images: Sequence[torch.Tensor]) -> None:
    """Check that the images are valid.

    Args:
        images: The images to check.

    Raises:
        ValueError: If no tensors are provided.
        ValueError: If any tensor is not three-dimensional.
        ValueError: If any tensor does not have the same number of channels.
        ValueError: If any tensor does not have the same dtype.
        ValueError: If any tensor is not on the same device.
    """
    if len(images) == 0:
        raise ValueError("At least one image must be provided.")

    if any(image.ndim != 3 for image in images):
        raise ValueError("All images must have 3 dimensions.")

    if any(image.shape[0] != images[0].shape[0] for image in images):
        raise ValueError("All images must have the same number of channels.")

    if any(image.dtype != images[0].dtype for image in images):
        raise ValueError("All images must have the same dtype.")

    if any(image.device != images[0].device for image in images):
        raise ValueError("All images must be on the same device.")


def _check_data_mask(data: torch.Tensor, mask: torch.Tensor) -> None:
    """Check that the data and mask are compatible.

    Args:
        data: The data tensor.
        mask: The mask tensor.

    Raises:
        ValueError: If the data and mask are incompatible.
    """
    if data.shape[0] != mask.shape[0] or data.shape[2:] != mask.shape[1:]:
        raise ValueError("The data and mask are incompatible.")
